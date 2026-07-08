from __future__ import annotations

from app.db.models import GeneratedIdea
from app.i18n.es import CATEGORY_LABELS, LANGUAGE_LABELS_ES, MARKET_LABELS, STATUS_LABELS, label_for


def score_badge(score: int) -> str:
    if score >= 75:
        return "Alto"
    if score >= 55:
        return "Medio"
    return "Bajo"


def risk_badge(risk: int) -> str:
    if risk >= 7:
        return "Alto"
    if risk >= 4:
        return "Medio"
    return "Bajo"


def generated_idea_card_data(idea: GeneratedIdea) -> dict[str, object]:
    return {
        "id": idea.id,
        "titulo": idea.title,
        "angulo": idea.angle,
        "score": idea.total_score,
        "score_badge": score_badge(idea.total_score),
        "estado": label_for(STATUS_LABELS, idea.status),
        "categoria": label_for(CATEGORY_LABELS, idea.category),
        "idioma": label_for(LANGUAGE_LABELS_ES, idea.target_language),
        "mercado": label_for(MARKET_LABELS, idea.target_market),
        "duracion": idea.suggested_duration,
        "formato": idea.suggested_format,
        "hook": idea.suggested_hook_type,
        "riesgo_copyright": risk_badge(idea.copyright_risk),
        "riesgo_monetizacion": risk_badge(idea.monetization_risk),
    }
