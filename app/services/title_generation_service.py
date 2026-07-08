from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.ai.llm_orchestrator import get_llm_provider
from app.core.enums import GeneratedTitleStatus
from app.db import models
from app.db.repositories import create_generated_title, set_selected_title
from app.llm.base import LLMProviderUnavailable
from app.utils.json_parsing import safe_int_score

TITLE_TYPES: tuple[str, ...] = ("short", "curiosity", "seo", "documentary", "direct")


@dataclass(frozen=True)
class GeneratedTitleCandidate:
    title: str
    title_type: str
    why_it_works: str
    clarity_score: int
    curiosity_score: int
    seo_score: int
    ctr_estimate_score: int
    clickbait_risk: int
    total_score: int

    @property
    def length_chars(self) -> int:
        return len(self.title)

    def as_payload(
        self,
        *,
        generated_idea_id: int | None,
        topic_id: int | None,
        hook_id: int,
        language: str,
        market: str,
    ) -> dict[str, Any]:
        return {
            "generated_idea_id": generated_idea_id,
            "topic_id": topic_id,
            "hook_id": hook_id,
            "language": language,
            "market": market,
            "title": self.title,
            "title_type": self.title_type,
            "clarity_score": self.clarity_score,
            "curiosity_score": self.curiosity_score,
            "seo_score": self.seo_score,
            "ctr_estimate_score": self.ctr_estimate_score,
            "clickbait_risk": self.clickbait_risk,
            "total_score": self.total_score,
            "length_chars": self.length_chars,
            "why_it_works": self.why_it_works,
            "selected": False,
            "status": GeneratedTitleStatus.SUGGESTED.value,
        }


@dataclass(frozen=True)
class GeneratedTitlesResult:
    candidates: list[GeneratedTitleCandidate]
    provider_name: str
    prompt: str
    warnings: list[str]
    saved_title_ids: list[int]


def generate_titles_for_hook(
    session: Session,
    *,
    generated_idea_id: int | None,
    topic_id: int | None,
    hook_id: int,
    language: str,
    market: str,
    provider_name: str = "manual",
    mode: str = "balanced",
    save: bool = True,
) -> GeneratedTitlesResult:
    topic = session.get(models.Topic, topic_id) if topic_id else None
    idea = session.get(models.GeneratedIdea, generated_idea_id) if generated_idea_id else None
    hook = session.get(models.Hook, hook_id)
    if hook is None:
        raise ValueError("No se encontro el hook elegido.")
    if topic is None and idea is None:
        raise ValueError("Se necesita idea o topic para generar titulos.")

    result = generate_title_candidates(
        idea_title=idea.title if idea else topic.title,
        idea_summary=idea.summary if idea else topic.summary,
        idea_angle=idea.angle if idea else topic.notes or "",
        selected_hook=hook.text,
        language=language,
        market=market,
        category=idea.category if idea else topic.category,
        provider_name=provider_name,
        mode=mode,
    )
    saved_title_ids: list[int] = []
    if save:
        for candidate in result.candidates:
            title = create_generated_title(
                session,
                **candidate.as_payload(
                    generated_idea_id=generated_idea_id,
                    topic_id=topic_id,
                    hook_id=hook_id,
                    language=language,
                    market=market,
                ),
            )
            saved_title_ids.append(title.id)
    return GeneratedTitlesResult(
        candidates=result.candidates,
        provider_name=result.provider_name,
        prompt=result.prompt,
        warnings=result.warnings,
        saved_title_ids=saved_title_ids,
    )


def select_title(session: Session, title_id: int) -> models.GeneratedTitle:
    title = session.get(models.GeneratedTitle, title_id)
    if title is None:
        raise ValueError("No se encontro el titulo elegido.")
    return set_selected_title(session, title)


def generate_title_candidates(
    *,
    idea_title: str,
    idea_summary: str,
    idea_angle: str,
    selected_hook: str,
    language: str,
    market: str,
    category: str,
    provider_name: str = "manual",
    mode: str = "balanced",
) -> GeneratedTitlesResult:
    system_prompt, user_prompt = build_title_generation_prompt(
        idea_title=idea_title,
        idea_summary=idea_summary,
        idea_angle=idea_angle,
        selected_hook=selected_hook,
        language=language,
        market=market,
        category=category,
        mode=mode,
    )
    provider = get_llm_provider(provider_name)
    prompt = provider.generate_text(system_prompt, user_prompt) if provider.name == "manual" else user_prompt
    warnings: list[str] = []
    llm_candidates: list[GeneratedTitleCandidate] = []
    if provider.name != "manual":
        try:
            payload = provider.generate_json(system_prompt, user_prompt, schema_name="generated_titles")
            llm_candidates = _candidates_from_payload(payload, mode)
        except (LLMProviderUnavailable, ValueError, TypeError) as exc:
            warnings.append(f"{provider.name} no genero titulos validos; se uso fallback heuristico: {exc}")

    heuristic = generate_heuristic_title_candidates(
        concept=idea_title,
        selected_hook=selected_hook,
        language=language,
        category=category,
        mode=mode,
    )
    candidates = _dedupe_candidates([*llm_candidates, *heuristic])[:25]
    return GeneratedTitlesResult(candidates, provider.name, prompt, warnings, [])


def build_title_generation_prompt(
    *,
    idea_title: str,
    idea_summary: str,
    idea_angle: str,
    selected_hook: str,
    language: str,
    market: str,
    category: str,
    mode: str,
) -> tuple[str, str]:
    system_prompt = "Eres experto en titulos para YouTube Shorts: claros, curiosos y sin clickbait falso."
    user_prompt = f"""
Genera titulos para YouTube Shorts.

Idea:
{idea_title}

Resumen:
{idea_summary}

Angulo:
{idea_angle}

Gancho elegido:
{selected_hook}

Idioma: {language}
Mercado: {market}
Categoria: {category}
Modo: {mode}

Reglas:
- Maximo recomendado: 70 caracteres.
- No uses clickbait falso.
- No uses mayusculas excesivas.
- No uses hashtags en el titulo.
- Devuelve JSON valido.
- Genera 5 cortos, 5 curiosos, 5 SEO, 5 documentales y 5 directos.

Formato:
[
  {{
    "title": "...",
    "title_type": "curiosity",
    "why_it_works": "...",
    "clarity_score": 8,
    "curiosity_score": 9,
    "seo_score": 6,
    "ctr_estimate_score": 8,
    "clickbait_risk": 2
  }}
]
""".strip()
    return system_prompt, user_prompt


def generate_heuristic_title_candidates(
    *,
    concept: str,
    selected_hook: str,
    language: str,
    category: str,
    mode: str = "balanced",
) -> list[GeneratedTitleCandidate]:
    subject = _short_subject(concept)
    templates = _templates_for_language(language)
    candidates: list[GeneratedTitleCandidate] = []
    for title_type in TITLE_TYPES:
        for template in templates[title_type]:
            title = _clean_title(template.format(x=subject), mode)
            candidates.append(
                _scored_title(
                    title=title,
                    title_type=title_type,
                    selected_hook=selected_hook,
                    category=category,
                    mode=mode,
                )
            )
    return candidates


def _scored_title(
    *,
    title: str,
    title_type: str,
    selected_hook: str,
    category: str,
    mode: str,
) -> GeneratedTitleCandidate:
    length = len(title)
    clarity = 9 if length <= 70 else 6
    curiosity = 8 if title_type in {"curiosity", "documentary"} else 6
    seo = 8 if title_type == "seo" or category in {"ai_tools", "tech_explained"} else 6
    ctr = 8 if title_type in {"curiosity", "short"} else 7
    risk = 2
    lowered = title.lower()
    if any(word in lowered for word in ("nunca", "siempre", "garantizado", "millones")):
        risk += 2
    if mode == "safer":
        risk = max(0, risk - 1)
        clarity = min(10, clarity + 1)
    elif mode == "more_curiosity":
        curiosity = min(10, curiosity + 1)
    elif mode == "more_seo":
        seo = min(10, seo + 2)
    elif mode == "shorter":
        clarity = min(10, clarity + 1)
    elif mode == "more_documentary":
        ctr = max(0, ctr - 1)
        risk = max(0, risk - 1)
    total = _total_title_score(clarity, curiosity, seo, ctr, risk)
    return GeneratedTitleCandidate(
        title=title,
        title_type=title_type,
        why_it_works=_why_title_works(title_type, selected_hook),
        clarity_score=clarity,
        curiosity_score=curiosity,
        seo_score=seo,
        ctr_estimate_score=ctr,
        clickbait_risk=risk,
        total_score=total,
    )


def _candidates_from_payload(payload: dict[str, object] | list[object], mode: str) -> list[GeneratedTitleCandidate]:
    raw_items = payload.get("titles", []) if isinstance(payload, dict) else payload
    candidates: list[GeneratedTitleCandidate] = []
    if not isinstance(raw_items, list):
        return candidates
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        if not title:
            continue
        clarity = safe_int_score(item.get("clarity_score"), default=7)
        curiosity = safe_int_score(item.get("curiosity_score"), default=7)
        seo = safe_int_score(item.get("seo_score"), default=6)
        ctr = safe_int_score(item.get("ctr_estimate_score"), default=7)
        risk = safe_int_score(item.get("clickbait_risk"), default=2)
        title_type = str(item.get("title_type") or "curiosity")
        candidates.append(
            GeneratedTitleCandidate(
                title=_clean_title(title, mode),
                title_type=title_type,
                why_it_works=str(item.get("why_it_works") or "Combina claridad y curiosidad."),
                clarity_score=clarity,
                curiosity_score=curiosity,
                seo_score=seo,
                ctr_estimate_score=ctr,
                clickbait_risk=risk,
                total_score=_total_title_score(clarity, curiosity, seo, ctr, risk),
            )
        )
    return candidates


def _templates_for_language(language: str) -> dict[str, tuple[str, ...]]:
    if language == "en":
        return {
            "short": ("{x} in 40 seconds", "How {x} really works", "{x}, explained fast", "Understand {x} quickly", "The simple version of {x}"),
            "curiosity": ("The hidden reason behind {x}", "What nobody explains about {x}", "The weird detail inside {x}", "Why {x} works this way", "The surprise behind {x}"),
            "seo": ("How {x} works", "{x} explained", "Why {x} matters", "The science of {x}", "The real problem with {x}"),
            "documentary": ("The invisible system behind {x}", "The story behind {x}", "The detail that changed {x}", "Inside the logic of {x}", "The mechanism behind {x}"),
            "direct": ("This is how {x} works", "Here is the point of {x}", "The reason {x} matters", "The mistake in {x}", "The truth about {x}"),
        }
    return {
        "short": ("{x} en 40 segundos", "Asi funciona {x}", "{x}, explicado rapido", "Entiende {x} rapido", "La version simple de {x}"),
        "curiosity": ("La razon oculta detras de {x}", "Lo que nadie explica sobre {x}", "El detalle raro dentro de {x}", "Por que {x} funciona asi", "La sorpresa detras de {x}"),
        "seo": ("Como funciona {x}", "{x} explicado", "Por que importa {x}", "La ciencia de {x}", "El problema real de {x}"),
        "documentary": ("El sistema invisible detras de {x}", "La historia detras de {x}", "El detalle que cambio {x}", "Dentro de la logica de {x}", "El mecanismo detras de {x}"),
        "direct": ("Esto es lo importante de {x}", "Este es el punto de {x}", "La razon por la que importa {x}", "El error en {x}", "La verdad sobre {x}"),
    }


def _short_subject(title: str) -> str:
    cleaned = " ".join(title.replace(":", " ").replace("|", " ").split())
    return cleaned[:64].strip() or "esta idea"


def _clean_title(title: str, mode: str) -> str:
    cleaned = " ".join(title.replace("#", "").split())
    limit = 58 if mode == "shorter" else 78
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[:limit].rsplit(" ", 1)[0]


def _why_title_works(title_type: str, selected_hook: str) -> str:
    return {
        "short": "Promete una explicacion rapida y clara.",
        "curiosity": "Abre una pregunta que conecta con el gancho elegido.",
        "seo": "Incluye el concepto central y mantiene busqueda clara.",
        "documentary": "Suena explicativo y reduce riesgo de clickbait.",
        "direct": "Dice exactamente que va a recibir el espectador.",
    }.get(title_type, f"Se alinea con el gancho: {selected_hook[:80]}")


def _total_title_score(clarity: int, curiosity: int, seo: int, ctr: int, risk: int) -> int:
    positive = clarity * 0.25 + curiosity * 0.25 + seo * 0.20 + ctr * 0.20 + (10 - risk) * 0.10
    return int(max(0, min(100, positive * 10)))


def _dedupe_candidates(candidates: list[GeneratedTitleCandidate]) -> list[GeneratedTitleCandidate]:
    seen: set[str] = set()
    deduped: list[GeneratedTitleCandidate] = []
    for candidate in sorted(candidates, key=lambda item: item.total_score, reverse=True):
        key = candidate.title.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)
    return deduped
