from __future__ import annotations

from app.db.models import GeneratedIdea
from app.i18n.es import CATEGORY_LABELS
from app.ui.components.generated_idea_cards import generated_idea_card_data, risk_badge, score_badge


def test_score_and_risk_badges() -> None:
    assert score_badge(80) == "Alto"
    assert score_badge(60) == "Medio"
    assert score_badge(30) == "Bajo"
    assert risk_badge(8) == "Alto"
    assert risk_badge(5) == "Medio"
    assert risk_badge(1) == "Bajo"


def test_generated_idea_card_data_translates_status() -> None:
    idea = GeneratedIdea(
        title="Idea",
        angle="Angulo",
        summary="Resumen",
        why_it_can_work="Funciona",
        target_language="es",
        target_market="spain_latam",
        category="tech_explained",
        viral_score=8,
        rpm_score=7,
        visual_score=8,
        narrative_clarity_score=8,
        evergreen_score=7,
        novelty_score=6,
        production_ease_score=8,
        copyright_risk=2,
        monetization_risk=2,
        total_score=78,
        status="selected",
    )

    data = generated_idea_card_data(idea)

    assert data["titulo"] == "Idea"
    assert data["estado"] == "Elegida"
    assert data["categoria"] == CATEGORY_LABELS["tech_explained"]
    assert data["score_badge"] == "Alto"
