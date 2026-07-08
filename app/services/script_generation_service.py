from __future__ import annotations

import json
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.ai.llm_orchestrator import get_llm_provider
from app.core.enums import ScriptStatus
from app.db import models
from app.db.repositories import create_script_with_lines
from app.llm.base import LLMProviderUnavailable
from app.services.content_quality_service import QualityReport, analyze_script_quality
from app.services.fact_check_helper_service import (
    analyze_claims,
    claim_type_for_text,
    line_needs_source,
)
from app.utils.json_parsing import extract_json_object
from app.utils.language import needs_native_review
from app.utils.text import normalize_hashtags

SCRIPT_FORMATS = {
    "documental_rapido": "Documental rapido",
    "historia_con_giro": "Historia con giro",
    "explicacion_tecnica_simple": "Explicacion tecnica simple",
    "caso_real": "Caso real",
    "lista_rapida": "Lista rapida",
    "problema_solucion": "Problema-solucion",
    "lo_que_nadie_te_explica": "Lo que nadie te explica",
    "mini_storytelling": "Mini storytelling",
}

DURATION_OPTIONS = {
    "20-30 segundos": 25,
    "30-45 segundos": 40,
    "45-60 segundos": 55,
    "60-90 segundos": 75,
    "90-180 segundos": 120,
}


@dataclass(frozen=True)
class ScriptGenerationResult:
    script: models.Script
    provider_name: str
    prompt: str
    quality_report: QualityReport
    fact_warnings: list[dict[str, object]]
    warnings: list[str]


def generate_script(
    session: Session,
    *,
    generated_idea_id: int | None,
    topic_id: int | None,
    hook_id: int,
    title_id: int,
    language: str,
    market: str,
    format_type: str,
    target_duration_seconds: int,
    tone: str,
    provider_name: str = "manual",
) -> ScriptGenerationResult:
    topic = session.get(models.Topic, topic_id) if topic_id else None
    idea = session.get(models.GeneratedIdea, generated_idea_id) if generated_idea_id else None
    hook = session.get(models.Hook, hook_id)
    title = session.get(models.GeneratedTitle, title_id)
    if hook is None or title is None:
        raise ValueError("Se necesita hook y titulo para generar guion.")
    if topic is None and idea is None:
        raise ValueError("Se necesita idea o topic para generar guion.")

    result = generate_script_payload(
        idea_title=idea.title if idea else topic.title,
        idea_summary=idea.summary if idea else topic.summary,
        idea_angle=idea.angle if idea else topic.notes or "",
        hook_text=hook.text,
        title=title.title,
        language=language,
        market=market,
        category=idea.category if idea else topic.category,
        format_type=format_type,
        target_duration_seconds=target_duration_seconds,
        tone=tone,
        provider_name=provider_name,
    )
    lines = result["lines"]
    quality_report: QualityReport = result["quality_report"]
    fact_warnings: list[dict[str, object]] = result["fact_warnings"]
    fact_notes = json.dumps(
        {
            "quality_score": quality_report.score,
            "quality_warnings": quality_report.warnings,
            "blocking_issues": quality_report.blocking_issues,
            "fact_warnings": fact_warnings,
            "market": market,
            "format_type": format_type,
            "target_duration_seconds": target_duration_seconds,
            "selected_title_id": title_id,
        },
        ensure_ascii=False,
    )
    script = create_script_with_lines(
        session,
        {
            "topic_id": topic.id if topic else idea.converted_topic_id,
            "hook_id": hook_id,
            "language": language,
            "version": 1,
            "script_text": "\n".join(str(line["text"]) for line in lines),
            "estimated_duration_seconds": sum(float(line.get("duration_seconds", 2.5)) for line in lines),
            "tone": tone,
            "status": ScriptStatus.NEEDS_REVIEW.value,
            "needs_fact_check": bool(fact_warnings),
            "fact_check_notes": fact_notes,
            "title_suggestion": title.title,
            "description_suggestion": result.get("description_suggestion"),
            "hashtags": " ".join(result.get("hashtags", [])),
            "needs_native_review": needs_native_review(language),
        },
        lines,
    )
    return ScriptGenerationResult(
        script=script,
        provider_name=str(result["provider_name"]),
        prompt=str(result["prompt"]),
        quality_report=quality_report,
        fact_warnings=fact_warnings,
        warnings=list(result["warnings"]),
    )


def approve_script(session: Session, script_id: int) -> models.Script:
    script = session.get(models.Script, script_id)
    if script is None:
        raise ValueError("No se encontro el guion.")
    if not script.lines:
        raise ValueError("No se puede aprobar un guion vacio.")
    notes = _script_fact_notes(script)
    blocking = notes.get("blocking_issues", [])
    high_risk = [
        warning
        for warning in notes.get("fact_warnings", [])
        if isinstance(warning, dict) and warning.get("risk_level") == "high"
    ]
    if blocking or high_risk:
        raise ValueError("Hay issues bloqueantes o claims de alto riesgo pendientes.")
    script.status = ScriptStatus.APPROVED.value
    script.needs_fact_check = bool(notes.get("fact_warnings"))
    session.commit()
    session.refresh(script)
    return script


def generate_script_payload(
    *,
    idea_title: str,
    idea_summary: str,
    idea_angle: str,
    hook_text: str,
    title: str,
    language: str,
    market: str,
    category: str,
    format_type: str,
    target_duration_seconds: int,
    tone: str,
    provider_name: str = "manual",
) -> dict[str, object]:
    system_prompt, user_prompt = build_script_generation_prompt(
        idea_title=idea_title,
        idea_summary=idea_summary,
        idea_angle=idea_angle,
        hook_text=hook_text,
        title=title,
        language=language,
        market=market,
        category=category,
        format_type=format_type,
        target_duration_seconds=target_duration_seconds,
        tone=tone,
    )
    provider = get_llm_provider(provider_name)
    prompt = provider.generate_text(system_prompt, user_prompt) if provider.name == "manual" else user_prompt
    warnings: list[str] = []
    payload: dict[str, object] | None = None
    if provider.name != "manual":
        try:
            raw = provider.generate_text(system_prompt, user_prompt)
            payload = parse_generated_script_json(raw)
        except (LLMProviderUnavailable, ValueError, TypeError) as exc:
            warnings.append(f"{provider.name} no genero guion valido; se uso fallback heuristico: {exc}")
    if payload is None:
        payload = generate_heuristic_script_payload(
            idea_title=idea_title,
            idea_summary=idea_summary,
            hook_text=hook_text,
            title=title,
            language=language,
            format_type=format_type,
            target_duration_seconds=target_duration_seconds,
        )
    lines = normalize_script_lines(payload, target_duration_seconds)
    quality_report = analyze_script_quality(
        lines=lines,
        hook_text=hook_text,
        title=title,
        target_duration_seconds=target_duration_seconds,
    )
    fact_warnings = [warning.__dict__ for warning in analyze_claims(lines)]
    return {
        "provider_name": provider.name,
        "prompt": prompt,
        "warnings": warnings,
        "lines": lines,
        "quality_report": quality_report,
        "fact_warnings": fact_warnings,
        "description_suggestion": payload.get("description_suggestion"),
        "hashtags": normalize_hashtags(payload.get("hashtags", [])),
    }


def build_script_generation_prompt(
    *,
    idea_title: str,
    idea_summary: str,
    idea_angle: str,
    hook_text: str,
    title: str,
    language: str,
    market: str,
    category: str,
    format_type: str,
    target_duration_seconds: int,
    tone: str,
) -> tuple[str, str]:
    system_prompt = "Eres guionista experto en YouTube Shorts. Escribe guiones claros, seguros y visuales."
    user_prompt = f"""
Crea un guion para un Short.

Idea:
{idea_title}

Resumen:
{idea_summary}

Angulo:
{idea_angle}

Gancho elegido:
{hook_text}

Titulo elegido:
{title}

Idioma: {language}
Mercado: {market}
Categoria: {category}
Formato: {format_type}
Duracion objetivo: {target_duration_seconds} segundos
Tono: {tone}

Reglas:
- No empieces con hola.
- Frases cortas.
- Cada linea debe servir como subtitulo.
- No inventes datos.
- Marca claims que necesitan fuente.
- Incluye visual_suggestion para cada linea.
- Devuelve JSON valido.

Formato:
{{
  "estimated_duration_seconds": 40,
  "quality_notes": "...",
  "lines": [
    {{
      "order": 1,
      "text": "...",
      "subtitle_text": "...",
      "visual_suggestion": "...",
      "estimated_duration_seconds": 2.5,
      "needs_source": false,
      "source_hint": null,
      "risk_note": null,
      "claim_type": null
    }}
  ]
}}
""".strip()
    return system_prompt, user_prompt


def parse_generated_script_json(text: str) -> dict[str, object]:
    payload = extract_json_object(text)
    lines = payload.get("lines")
    if not isinstance(lines, list) or not lines:
        raise ValueError("El guion JSON debe incluir lines.")
    return payload


def normalize_script_lines(payload: dict[str, object], target_duration_seconds: int) -> list[dict[str, object]]:
    raw_lines = payload.get("lines", [])
    if not isinstance(raw_lines, list):
        raise ValueError("El guion necesita una lista de lines.")
    normalized: list[dict[str, object]] = []
    fallback_duration = max(1.8, target_duration_seconds / max(1, len(raw_lines)))
    for _index, item in enumerate(raw_lines, start=1):
        if isinstance(item, str):
            text = item.strip()
            visual = "Texto grande en pantalla con fondo limpio."
            duration = fallback_duration
        elif isinstance(item, dict):
            text = str(item.get("text") or "").strip()
            visual = str(item.get("visual_suggestion") or "Texto grande en pantalla con fondo limpio.")
            duration = float(item.get("estimated_duration_seconds") or item.get("duration_seconds") or fallback_duration)
        else:
            continue
        if not text:
            continue
        claim_type = claim_type_for_text(text)
        needs_source = line_needs_source(text)
        normalized.append(
            {
                "text": text,
                "subtitle_text": text,
                "visual_suggestion": visual,
                "duration_seconds": max(1.0, duration),
                "needs_source": needs_source,
                "source_hint": None,
                "risk_note": f"Claim: {claim_type}" if claim_type else None,
            }
        )
    if not normalized:
        raise ValueError("No se detectaron lineas de guion.")
    return normalized


def generate_heuristic_script_payload(
    *,
    idea_title: str,
    idea_summary: str,
    hook_text: str,
    title: str,
    language: str,
    format_type: str,
    target_duration_seconds: int,
) -> dict[str, object]:
    subject = _short_subject(idea_title)
    structures = {
        "problema_solucion": [
            hook_text,
            f"El problema no es {subject}, es como lo interpretamos.",
            f"La clave esta en este mecanismo: {idea_summary or subject}.",
            "Si lo ves asi, la idea deja de parecer magia.",
            f"Por eso {title.lower()} importa mas de lo que parece.",
        ],
        "historia_con_giro": [
            hook_text,
            f"Al principio, {subject} parece una historia normal.",
            "Pero el giro esta en un detalle que casi nadie mira.",
            f"Ese detalle explica {idea_summary or subject}.",
            "Y ahi es donde la historia cambia por completo.",
        ],
    }
    lines = structures.get(
        format_type,
        [
            hook_text,
            f"La explicacion obvia de {subject} se queda corta.",
            f"El contexto real es este: {idea_summary or subject}.",
            "El mecanismo funciona porque conecta causa, efecto y consecuencia.",
            f"Esa es la forma simple de entender {title.lower()}.",
        ],
    )
    per_line = max(2.0, target_duration_seconds / len(lines))
    return {
        "estimated_duration_seconds": target_duration_seconds,
        "quality_notes": "Fallback heuristico generado sin API.",
        "lines": [
            {
                "order": index,
                "text": text,
                "subtitle_text": text,
                "visual_suggestion": _visual_for_line(index, text),
                "estimated_duration_seconds": per_line,
                "needs_source": line_needs_source(text),
                "source_hint": None,
                "risk_note": None,
                "claim_type": claim_type_for_text(text),
            }
            for index, text in enumerate(lines, start=1)
        ],
        "hashtags": ["#shorts"],
    }


def _script_fact_notes(script: models.Script) -> dict[str, object]:
    if not script.fact_check_notes:
        return {}
    try:
        value = json.loads(script.fact_check_notes)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def _short_subject(title: str) -> str:
    cleaned = " ".join(title.replace(":", " ").replace("|", " ").split())
    return cleaned[:70].strip() or "esta idea"


def _visual_for_line(index: int, text: str) -> str:
    if index == 1:
        return "Texto grande con movimiento rapido y contraste alto."
    if any(word in text.lower() for word in ("mecanismo", "clave", "funciona")):
        return "Diagrama simple con flechas y palabras clave."
    return "Fondo limpio, keyword resaltada y zoom suave."
