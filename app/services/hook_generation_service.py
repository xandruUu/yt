from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.ai.llm_orchestrator import get_llm_provider
from app.core.enums import HookType
from app.db import models
from app.db.repositories import add_and_commit
from app.llm.base import LLMProviderUnavailable
from app.utils.json_parsing import safe_int_score

HOOK_TYPES: tuple[str, ...] = (
    HookType.MYSTERY.value,
    HookType.MISTAKE.value,
    HookType.UTILITY.value,
    HookType.SURPRISE.value,
    HookType.MONEY.value,
)


@dataclass(frozen=True)
class GeneratedHookCandidate:
    text: str
    hook_type: str
    why_it_works: str
    first_second_visual: str
    clarity_score: int
    curiosity_score: int
    emotion_score: int
    risk_score: int
    total_score: int

    def as_hook_payload(self, language: str) -> dict[str, Any]:
        return {
            "language": language,
            "text": self.text,
            "hook_type": self.hook_type,
            "clarity_score": float(self.clarity_score),
            "curiosity_score": float(self.curiosity_score),
            "emotion_score": float(self.emotion_score),
            "risk_score": float(self.risk_score),
            "notes": json.dumps(
                {
                    "why_it_works": self.why_it_works,
                    "first_second_visual": self.first_second_visual,
                    "total_score": self.total_score,
                },
                ensure_ascii=False,
            ),
        }


@dataclass(frozen=True)
class GeneratedHooksResult:
    candidates: list[GeneratedHookCandidate]
    provider_name: str
    prompt: str
    warnings: list[str]
    saved_hook_ids: list[int]


def generate_hooks_for_topic(
    session: Session,
    topic: models.Topic,
    *,
    language: str,
    market: str,
    provider_name: str = "manual",
    style: str = "balanced",
    save: bool = True,
) -> GeneratedHooksResult:
    result = generate_hook_candidates(
        topic_title=topic.title,
        topic_summary=topic.summary,
        language=language,
        market=market,
        category=topic.category,
        provider_name=provider_name,
        style=style,
    )
    saved_hook_ids: list[int] = []
    if save:
        for candidate in result.candidates:
            hook = add_and_commit(
                session,
                models.Hook(topic_id=topic.id, **candidate.as_hook_payload(language)),
            )
            saved_hook_ids.append(hook.id)
    return GeneratedHooksResult(
        candidates=result.candidates,
        provider_name=result.provider_name,
        prompt=result.prompt,
        warnings=result.warnings,
        saved_hook_ids=saved_hook_ids,
    )


def generate_hook_candidates(
    *,
    topic_title: str,
    topic_summary: str,
    language: str,
    market: str,
    category: str = "other",
    provider_name: str = "manual",
    style: str = "balanced",
) -> GeneratedHooksResult:
    system_prompt, user_prompt = build_hook_generation_prompt(
        topic_title=topic_title,
        topic_summary=topic_summary,
        language=language,
        market=market,
        category=category,
        style=style,
    )
    provider = get_llm_provider(provider_name)
    prompt = provider.generate_text(system_prompt, user_prompt) if provider.name == "manual" else user_prompt
    warnings: list[str] = []
    llm_candidates: list[GeneratedHookCandidate] = []

    if provider.name != "manual":
        try:
            payload = provider.generate_json(system_prompt, user_prompt, schema_name="hook_candidates")
            llm_candidates = _candidates_from_payload(payload)
        except (LLMProviderUnavailable, ValueError, TypeError) as exc:
            warnings.append(f"{provider.name} no genero hooks validos; se uso fallback heuristico: {exc}")

    heuristic_candidates = generate_heuristic_hook_candidates(
        topic_title=topic_title,
        topic_summary=topic_summary,
        language=language,
        category=category,
        style=style,
    )
    candidates = _dedupe_candidates([*llm_candidates, *heuristic_candidates])[:25]
    return GeneratedHooksResult(
        candidates=candidates,
        provider_name=provider.name,
        prompt=prompt,
        warnings=warnings,
        saved_hook_ids=[],
    )


def build_hook_generation_prompt(
    *,
    topic_title: str,
    topic_summary: str,
    language: str,
    market: str,
    category: str,
    style: str,
) -> tuple[str, str]:
    system_prompt = (
        "Eres un estratega experto en YouTube Shorts, retencion y seguridad de contenido. "
        "Genera hooks originales, cortos y verificables. No copies titulares."
    )
    user_prompt = f"""
Genera 25 hooks para un Short.

Idea:
{topic_title}

Resumen:
{topic_summary}

Idioma objetivo: {language}
Mercado objetivo: {market}
Categoria: {category}
Estilo solicitado: {style}

Requisitos:
- 5 hooks de misterio.
- 5 hooks de error.
- 5 hooks de utilidad.
- 5 hooks de sorpresa.
- 5 hooks de impacto/dinero si aplica.
- Maximo recomendado: 12 palabras por hook.
- Sin clickbait falso.
- Sin promesas imposibles.
- Sin contenido sensible innecesario.

Devuelve JSON:
[
  {{
    "text": "...",
    "hook_type": "mystery",
    "why_it_works": "...",
    "first_second_visual": "...",
    "clarity_score": 8,
    "curiosity_score": 9,
    "emotion_score": 7,
    "risk_score": 2,
    "total_score": 86
  }}
]
""".strip()
    return system_prompt, user_prompt


def generate_heuristic_hook_candidates(
    *,
    topic_title: str,
    topic_summary: str,
    language: str,
    category: str,
    style: str = "balanced",
) -> list[GeneratedHookCandidate]:
    subject = _short_subject(topic_title)
    templates = _templates_for_language(language)
    candidates: list[GeneratedHookCandidate] = []
    for hook_type in HOOK_TYPES:
        for template in templates[hook_type]:
            text = _trim_words(template.format(x=subject), limit=8 if style == "shorter" else 12)
            candidates.append(
                _scored_candidate(
                    text=text,
                    hook_type=hook_type,
                    topic_summary=topic_summary,
                    category=category,
                    style=style,
                )
            )
    return candidates


def _scored_candidate(
    *,
    text: str,
    hook_type: str,
    topic_summary: str,
    category: str,
    style: str,
) -> GeneratedHookCandidate:
    clarity = 8 if len(text.split()) <= 12 else 6
    curiosity = 8 if hook_type in {HookType.MYSTERY.value, HookType.SURPRISE.value} else 7
    emotion = 8 if hook_type in {HookType.MISTAKE.value, HookType.MONEY.value} else 6
    risk = 2
    if category in {"finance_educational", "internet_culture_explained"}:
        risk += 1
    if any(word in f"{text} {topic_summary}".lower() for word in ("scam", "guaranteed", "crime")):
        risk += 2
    if style == "safer":
        risk = max(0, risk - 1)
        emotion = max(0, emotion - 1)
    elif style == "aggressive":
        curiosity = min(10, curiosity + 1)
        emotion = min(10, emotion + 1)
        risk = min(10, risk + 1)
    elif style == "documentary":
        clarity = min(10, clarity + 1)
        risk = max(0, risk - 1)
    total = _total_hook_score(clarity, curiosity, emotion, risk)
    return GeneratedHookCandidate(
        text=text,
        hook_type=hook_type,
        why_it_works=_why_it_works(hook_type),
        first_second_visual=_first_second_visual(hook_type, category),
        clarity_score=clarity,
        curiosity_score=curiosity,
        emotion_score=emotion,
        risk_score=risk,
        total_score=total,
    )


def _candidates_from_payload(payload: dict[str, object] | list[object]) -> list[GeneratedHookCandidate]:
    raw_items = payload.get("hooks", []) if isinstance(payload, dict) else payload
    candidates: list[GeneratedHookCandidate] = []
    if not isinstance(raw_items, list):
        return candidates
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or item.get("hook") or "").strip()
        if not text:
            continue
        clarity = safe_int_score(item.get("clarity_score"), default=7)
        curiosity = safe_int_score(item.get("curiosity_score"), default=7)
        emotion = safe_int_score(item.get("emotion_score"), default=6)
        risk = safe_int_score(item.get("risk_score"), default=2)
        candidates.append(
            GeneratedHookCandidate(
                text=_trim_words(text, 12),
                hook_type=str(item.get("hook_type") or item.get("type") or HookType.MYSTERY.value),
                why_it_works=str(item.get("why_it_works") or "Crea curiosidad sin depender de contexto."),
                first_second_visual=str(item.get("first_second_visual") or item.get("suggested_visual") or "Texto grande en pantalla."),
                clarity_score=clarity,
                curiosity_score=curiosity,
                emotion_score=emotion,
                risk_score=risk,
                total_score=_safe_total_score(
                    item.get("total_score"),
                    default=_total_hook_score(clarity, curiosity, emotion, risk),
                ),
            )
        )
    return candidates


def _templates_for_language(language: str) -> dict[str, tuple[str, ...]]:
    if language == "en":
        return {
            HookType.MYSTERY.value: (
                "The hidden reason {x} works",
                "Nobody explains this part of {x}",
                "The weird detail behind {x}",
                "This is what makes {x} surprising",
                "The part of {x} most people miss",
            ),
            HookType.MISTAKE.value: (
                "The mistake that changes everything about {x}",
                "Most people get {x} wrong",
                "This tiny error breaks {x}",
                "The risky assumption behind {x}",
                "The problem nobody spots in {x}",
            ),
            HookType.UTILITY.value: (
                "Here is how {x} actually works",
                "Use this simple model to understand {x}",
                "In 40 seconds, {x} makes sense",
                "The easiest way to explain {x}",
                "Watch this before you ignore {x}",
            ),
            HookType.SURPRISE.value: (
                "{x} is stranger than it looks",
                "This sounds impossible, but {x} explains it",
                "The surprising truth about {x}",
                "This changes how you see {x}",
                "The twist inside {x} is simple",
            ),
            HookType.MONEY.value: (
                "Why {x} could matter for your work",
                "The business impact of {x} is easy to miss",
                "{x} quietly changes the economics",
                "This is why companies care about {x}",
                "The real value hidden in {x}",
            ),
        }
    return {
        HookType.MYSTERY.value: (
            "La razon oculta por la que {x} funciona",
            "Nadie explica esta parte de {x}",
            "El detalle raro detras de {x}",
            "Esto es lo que vuelve sorprendente a {x}",
            "La parte de {x} que casi todos ignoran",
        ),
        HookType.MISTAKE.value: (
            "El error que cambia todo sobre {x}",
            "Casi todos entienden mal {x}",
            "Este fallo pequeno rompe {x}",
            "La suposicion peligrosa detras de {x}",
            "El problema que nadie ve en {x}",
        ),
        HookType.UTILITY.value: (
            "Asi funciona realmente {x}",
            "Usa este modelo simple para entender {x}",
            "En 40 segundos, {x} tiene sentido",
            "La forma mas facil de explicar {x}",
            "Mira esto antes de ignorar {x}",
        ),
        HookType.SURPRISE.value: (
            "{x} es mas raro de lo que parece",
            "Suena imposible, pero {x} lo explica",
            "La verdad sorprendente sobre {x}",
            "Esto cambia como ves {x}",
            "El giro dentro de {x} es simple",
        ),
        HookType.MONEY.value: (
            "Por que {x} puede afectar tu trabajo",
            "El impacto economico de {x} se suele ignorar",
            "{x} cambia la economia en silencio",
            "Por esto las empresas miran {x}",
            "El valor real escondido en {x}",
        ),
    }


def _short_subject(title: str) -> str:
    cleaned = " ".join(title.replace(":", " ").replace("|", " ").split())
    return cleaned[:72].strip() or "esta idea"


def _trim_words(text: str, limit: int) -> str:
    words = text.split()
    if len(words) <= limit:
        return text
    return " ".join(words[:limit])


def _why_it_works(hook_type: str) -> str:
    return {
        HookType.MYSTERY.value: "Abre una laguna de informacion y promete resolverla rapido.",
        HookType.MISTAKE.value: "Activa miedo a estar entendiendo mal el tema.",
        HookType.UTILITY.value: "Promete utilidad inmediata y una explicacion clara.",
        HookType.SURPRISE.value: "Rompe una expectativa y empuja a ver el giro.",
        HookType.MONEY.value: "Conecta la idea con valor, trabajo o impacto practico.",
    }.get(hook_type, "Crea curiosidad con bajo riesgo.")


def _first_second_visual(hook_type: str, category: str) -> str:
    if category in {"ai_tools", "tech_explained"}:
        base = "texto grande sobre fondo tech con zoom suave"
    elif category in {"business_case", "finance_educational"}:
        base = "numero grande, flecha y alerta visual"
    else:
        base = "palabras clave grandes con corte rapido"
    return f"{base}; enfoque {hook_type}"


def _total_hook_score(clarity: int, curiosity: int, emotion: int, risk: int) -> int:
    positive = clarity * 0.30 + curiosity * 0.35 + emotion * 0.20 + (10 - risk) * 0.15
    return int(max(0, min(100, positive * 10)))


def _safe_total_score(value: object, default: int) -> int:
    try:
        numeric = int(round(float(value)))
    except (TypeError, ValueError):
        numeric = default
    return max(0, min(100, numeric))


def _dedupe_candidates(candidates: list[GeneratedHookCandidate]) -> list[GeneratedHookCandidate]:
    seen: set[str] = set()
    deduped: list[GeneratedHookCandidate] = []
    for candidate in sorted(candidates, key=lambda item: item.total_score, reverse=True):
        key = " ".join(candidate.text.lower().split())
        if key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)
    return deduped
