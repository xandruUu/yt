from __future__ import annotations

from typing import Any

from app.core.scoring import calculate_topic_score, score_band


def build_topic_payload(
    *,
    title: str,
    summary: str,
    category: str,
    source: str | None,
    source_url: str | None,
    language_origin: str,
    target_markets: str,
    trend_score: float,
    rpm_score: float,
    visual_score: float,
    evergreen_score: float,
    competition_score: float,
    copyright_risk: float,
    monetization_risk: float,
    status: str = "idea",
    notes: str | None = None,
) -> dict[str, Any]:
    total_score = calculate_topic_score(
        trend_score,
        rpm_score,
        visual_score,
        evergreen_score,
        competition_score,
        copyright_risk,
        monetization_risk,
    )
    return {
        "title": title.strip(),
        "summary": summary.strip(),
        "category": category,
        "source": source or None,
        "source_url": source_url or None,
        "language_origin": language_origin,
        "target_markets": target_markets,
        "trend_score": float(trend_score),
        "rpm_score": float(rpm_score),
        "visual_score": float(visual_score),
        "evergreen_score": float(evergreen_score),
        "competition_score": float(competition_score),
        "copyright_risk": float(copyright_risk),
        "monetization_risk": float(monetization_risk),
        "total_score": total_score,
        "status": status,
        "notes": notes,
    }


def describe_score(total_score: float) -> str:
    labels = {
        "high_priority": "Prioridad alta",
        "interesting_test": "Test interesante",
        "hook_dependent": "Usar solo con buen gancho",
        "discard_or_archive": "Descartar o archivar",
    }
    return labels[score_band(total_score)]
