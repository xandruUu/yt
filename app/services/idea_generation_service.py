from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.core.enums import GeneratedIdeaStatus, TopicStatus
from app.db import models
from app.db.repositories import add_and_commit, create_topic
from app.providers.base import TrendItem
from app.services.trend_scoring_service import score_generated_idea, score_trend_item
from app.utils.slugs import slugify

TECH_TEMPLATES = (
    "Por qué {x} está cambiando la forma de trabajar",
    "El problema oculto detrás de {x}",
    "Cómo funciona realmente {x} en 40 segundos",
    "Lo que nadie te explica sobre {x}",
    "El error que muchos cometen con {x}",
)

BUG_TEMPLATES = (
    "El error que convirtió {x} en un desastre",
    "Cómo un fallo pequeño causó un problema enorme",
    "Por qué {x} falló aunque parecía buena idea",
    "El detalle técnico que arruinó {x}",
)

SCIENCE_TEMPLATES = (
    "Por qué {x} funciona aunque parece imposible",
    "La explicación simple detrás de {x}",
    "El truco físico que hace posible {x}",
    "Cómo {x} resuelve un problema que no ves",
)

PSYCHOLOGY_TEMPLATES = (
    "Por qué {x} engancha tanto al cerebro",
    "El patrón psicológico detrás de {x}",
    "Cómo {x} cambia tu atención sin que lo notes",
)


def generate_ideas_from_trend(
    trend_item: TrendItem,
    target_language: str,
    target_market: str,
    category: str,
    ideas_per_trend: int = 3,
) -> list[dict[str, Any]]:
    templates = _templates_for(category, trend_item.title)
    seed = _short_subject(trend_item.title)
    trend_score = score_trend_item(trend_item, target_market, target_language, category)
    ideas: list[dict[str, Any]] = []
    for template in templates[:ideas_per_trend]:
        title = template.format(x=seed)
        payload = {
            "title": title,
            "angle": _angle_for(title, category),
            "summary": _summary_for(trend_item, title),
            "why_it_can_work": _why_it_can_work(trend_item, trend_score.total_score),
            "target_language": target_language,
            "target_market": target_market,
            "category": category,
            "suggested_duration": "30-45s",
            "suggested_format": _format_for(category),
            "suggested_hook_type": _hook_type_for(title),
            "suggested_visual": _visual_for(category),
            "target_audience": _audience_for(category, target_market),
            "sources_json": json.dumps([_source_payload(trend_item)], ensure_ascii=False),
            "status": GeneratedIdeaStatus.SUGGESTED.value,
        }
        score = score_generated_idea(payload, trend_item)
        ideas.append({**payload, **score.as_payload()})
    return [idea for idea in ideas if idea["title"].strip()]


def generate_ideas_from_trends(
    trend_items: list[TrendItem],
    target_language: str,
    target_market: str,
    category: str,
    ideas_per_trend: int = 3,
) -> list[dict[str, Any]]:
    ideas: list[dict[str, Any]] = []
    for trend_item in trend_items:
        if trend_item.popularity_signals.get("provider_error"):
            continue
        ideas.extend(
            generate_ideas_from_trend(
                trend_item,
                target_language=target_language,
                target_market=target_market,
                category=category,
                ideas_per_trend=ideas_per_trend,
            )
        )
    return ideas


def persist_generated_ideas(
    session: Session,
    ideas: list[dict[str, Any]],
) -> list[models.GeneratedIdea]:
    saved: list[models.GeneratedIdea] = []
    seen_titles: set[str] = set()
    for idea in ideas:
        title_key = slugify(str(idea.get("title", "")))
        if not title_key or title_key in seen_titles:
            continue
        seen_titles.add(title_key)
        saved.append(add_and_commit(session, models.GeneratedIdea(**idea)))
    return saved


def convert_generated_idea_to_topic(
    session: Session,
    generated_idea: models.GeneratedIdea,
) -> models.Topic:
    if generated_idea.converted_topic_id:
        existing = session.get(models.Topic, generated_idea.converted_topic_id)
        if existing:
            return existing

    notes = "\n".join(
        [
            "Idea generada desde tendencia.",
            f"Ángulo: {generated_idea.angle}",
            f"Por qué puede funcionar: {generated_idea.why_it_can_work}",
            f"Visual sugerido: {generated_idea.suggested_visual or 'No definido'}",
            f"Formato sugerido: {generated_idea.suggested_format}",
            f"Tipo de hook sugerido: {generated_idea.suggested_hook_type}",
            f"Fuentes: {generated_idea.sources_json or '[]'}",
        ]
    )
    topic = create_topic(
        session,
        title=generated_idea.title,
        summary=generated_idea.summary,
        category=generated_idea.category,
        source="GeneratedIdea",
        source_url=None,
        language_origin=generated_idea.target_language,
        target_markets=generated_idea.target_market,
        trend_score=float(generated_idea.viral_score),
        rpm_score=float(generated_idea.rpm_score),
        visual_score=float(generated_idea.visual_score),
        evergreen_score=float(generated_idea.evergreen_score),
        competition_score=float(max(0, 10 - generated_idea.novelty_score)),
        copyright_risk=float(generated_idea.copyright_risk),
        monetization_risk=float(generated_idea.monetization_risk),
        total_score=float(generated_idea.total_score),
        status=TopicStatus.APPROVED_FOR_HOOKS.value,
        notes=notes,
    )
    generated_idea.converted_topic_id = topic.id
    generated_idea.status = GeneratedIdeaStatus.CONVERTED_TO_TOPIC.value
    add_and_commit(session, generated_idea)
    return topic


def _templates_for(category: str, title: str) -> tuple[str, ...]:
    lowered = title.lower()
    if any(word in lowered for word in ("bug", "error", "failed", "crash", "startup")):
        return BUG_TEMPLATES
    if category in {"science_explained", "engineering"}:
        return SCIENCE_TEMPLATES
    if category in {"psychology", "productivity"}:
        return PSYCHOLOGY_TEMPLATES
    return TECH_TEMPLATES


def _short_subject(title: str) -> str:
    cleaned = " ".join(title.replace(":", " ").replace("|", " ").split())
    return cleaned[:90].strip() or "esta tendencia"


def _angle_for(title: str, category: str) -> str:
    if "problema" in title.lower() or "error" in title.lower():
        return "Revelar el fallo o riesgo que hace interesante la historia."
    if category in {"science_explained", "engineering"}:
        return "Explicar un mecanismo complejo con una imagen mental simple."
    return "Convertir una señal de tendencia en una explicación rápida y visual."


def _summary_for(trend_item: TrendItem, title: str) -> str:
    base = trend_item.summary or trend_item.title
    return f"{title}. Basado en la señal: {base}"


def _why_it_can_work(trend_item: TrendItem, total_score: int) -> str:
    if total_score >= 75:
        return "Combina curiosidad, actualidad y un ángulo fácil de explicar en formato Short."
    if trend_item.popularity_signals:
        return "Tiene señales públicas de interés y puede transformarse en una explicación breve."
    return "Parte de una idea clara que puede validarse con un buen gancho."


def _format_for(category: str) -> str:
    if category in {"business_case", "history_explained"}:
        return "caso_real"
    if category in {"science_explained", "engineering"}:
        return "explicacion_tecnica_simple"
    return "documental_rapido"


def _hook_type_for(title: str) -> str:
    lowered = title.lower()
    if "error" in lowered or "fallo" in lowered:
        return "mistake"
    if "problema" in lowered or "oculto" in lowered:
        return "mystery"
    if "cómo" in lowered or "como" in lowered:
        return "utility"
    return "surprise"


def _visual_for(category: str) -> str:
    if category in {"ai_tools", "tech_explained"}:
        return "Texto grande, diagramas simples, pantallas abstractas tipo tech y zooms suaves."
    if category in {"science_explained", "engineering"}:
        return "Diagrama simple, flechas, iconos y subtítulos grandes."
    if category == "business_case":
        return "Timeline breve, números grandes y señales de alerta visual."
    return "Fondo limpio, palabras clave en pantalla y cortes rápidos."


def _audience_for(category: str, market: str) -> str:
    if category in {"ai_tools", "tech_explained"}:
        return f"Audiencia tech y curiosa en mercado {market}."
    if category == "finance_educational":
        return f"Audiencia interesada en educación financiera sin promesas falsas en {market}."
    return f"Audiencia general interesada en explicaciones rápidas en {market}."


def _source_payload(trend_item: TrendItem) -> dict[str, Any]:
    return {
        "title": trend_item.title,
        "source": trend_item.source,
        "url": trend_item.source_url,
        "signals": trend_item.popularity_signals,
    }

