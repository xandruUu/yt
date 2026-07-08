from __future__ import annotations

from app.providers.base import TrendItem
from app.services.trend_scoring_service import score_generated_idea, score_trend_item


def test_scores_stay_in_expected_ranges() -> None:
    score = score_trend_item(
        TrendItem(
            title="How AI agents automate repetitive workflows",
            summary="A practical workflow automation explanation",
            source="manual",
            popularity_signals={"comments": 120},
        ),
        target_market="global",
        target_language="es",
        category="ai_tools",
    )

    payload = score.as_payload()
    assert 0 <= payload["total_score"] <= 100
    for key, value in payload.items():
        if key != "total_score":
            assert 0 <= value <= 10


def test_risky_clip_topic_has_higher_copyright_risk_and_lower_score() -> None:
    safe = score_trend_item(
        TrendItem(title="How QR error correction works explained", source="manual"),
        target_market="global",
        target_language="es",
        category="tech_explained",
    )
    risky = score_trend_item(
        TrendItem(title="Movie trailer football celebrity song clip", source="manual"),
        target_market="global",
        target_language="es",
        category="tech_explained",
    )

    assert risky.copyright_risk > safe.copyright_risk
    assert risky.total_score < safe.total_score


def test_tech_category_increases_rpm_score() -> None:
    trend = TrendItem(title="A useful automation tool", source="manual")

    tech = score_trend_item(trend, target_market="us", target_language="es", category="ai_tools")
    generic = score_trend_item(trend, target_market="us", target_language="es", category="other")

    assert tech.rpm_score > generic.rpm_score


def test_evergreen_explainer_has_high_evergreen_score() -> None:
    score = score_trend_item(
        TrendItem(title="How this engineering principle works explained", source="manual"),
        target_market="global",
        target_language="es",
        category="engineering",
    )

    assert score.evergreen_score >= 7


def test_generated_idea_manual_scores_are_normalized() -> None:
    score = score_generated_idea(
        {
            "title": "Why AI tools are changing boring workflows",
            "category": "ai_tools",
            "viral_score": 12,
            "copyright_risk": -4,
        }
    )

    assert score.viral_score == 10
    assert score.copyright_risk == 0
