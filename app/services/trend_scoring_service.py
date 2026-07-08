from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.providers.base import TrendItem

HIGH_CURIOSITY_WORDS = {
    "ai",
    "bug",
    "mistake",
    "failed",
    "secret",
    "hidden",
    "why",
    "how",
    "viral",
    "billion",
    "million",
    "scam",
    "tool",
    "automation",
    "code",
    "crash",
    "startup",
    "hack",
    "agents",
    "workflow",
}

HIGH_RPM_CATEGORIES = {
    "ai_tools",
    "tech_explained",
    "business_case",
    "productivity",
    "finance_educational",
    "engineering",
}

COPYRIGHT_RISK_WORDS = {
    "movie",
    "film",
    "anime",
    "series",
    "football",
    "soccer",
    "sports",
    "celebrity",
    "tiktok",
    "reels",
    "clip",
    "trailer",
    "song",
}

MONETIZATION_RISK_WORDS = {
    "violence",
    "crime",
    "drug",
    "sexual",
    "politics",
    "hate",
    "medical",
    "health",
    "trading",
    "investment",
    "guaranteed",
    "scam",
}

EVERGREEN_WORDS = {
    "why",
    "how",
    "works",
    "explained",
    "history",
    "science",
    "engineering",
    "psychology",
    "mistake",
    "error",
    "principle",
}


@dataclass(frozen=True)
class IdeaScore:
    viral_score: int
    rpm_score: int
    visual_score: int
    narrative_clarity_score: int
    evergreen_score: int
    novelty_score: int
    production_ease_score: int
    copyright_risk: int
    monetization_risk: int
    total_score: int

    def as_payload(self) -> dict[str, int]:
        return {
            "viral_score": self.viral_score,
            "rpm_score": self.rpm_score,
            "visual_score": self.visual_score,
            "narrative_clarity_score": self.narrative_clarity_score,
            "evergreen_score": self.evergreen_score,
            "novelty_score": self.novelty_score,
            "production_ease_score": self.production_ease_score,
            "copyright_risk": self.copyright_risk,
            "monetization_risk": self.monetization_risk,
            "total_score": self.total_score,
        }


def score_trend_item(
    trend_item: TrendItem,
    target_market: str,
    target_language: str,
    category: str,
) -> IdeaScore:
    text = f"{trend_item.title} {trend_item.summary or ''}".lower()
    signals = trend_item.popularity_signals
    signal_strength = _signal_strength(signals)

    viral_score = _clamp_score(4 + signal_strength + _keyword_hits(text, HIGH_CURIOSITY_WORDS))
    rpm_score = _clamp_score(7 if category in HIGH_RPM_CATEGORIES else 5)
    visual_score = _clamp_score(8 - _keyword_hits(text, COPYRIGHT_RISK_WORDS))
    narrative_clarity_score = _clamp_score(6 + (1 if any(word in text for word in ("why", "how", "explained")) else 0))
    evergreen_score = _clamp_score(5 + _keyword_hits(text, EVERGREEN_WORDS))
    novelty_score = _clamp_score(5 + signal_strength)
    production_ease_score = _clamp_score(8 if visual_score >= 6 else 5)
    copyright_risk = _clamp_score(1 + _keyword_hits(text, COPYRIGHT_RISK_WORDS) * 2)
    monetization_risk = _clamp_score(1 + _keyword_hits(text, MONETIZATION_RISK_WORDS) * 2)

    if target_market in {"us", "global"} and category in HIGH_RPM_CATEGORIES:
        rpm_score = _clamp_score(rpm_score + 1)
    if target_language == "hi_hinglish":
        narrative_clarity_score = _clamp_score(narrative_clarity_score - 1)

    return _with_total(
        viral_score=viral_score,
        rpm_score=rpm_score,
        visual_score=visual_score,
        narrative_clarity_score=narrative_clarity_score,
        evergreen_score=evergreen_score,
        novelty_score=novelty_score,
        production_ease_score=production_ease_score,
        copyright_risk=copyright_risk,
        monetization_risk=monetization_risk,
    )


def score_generated_idea(
    idea: dict[str, Any],
    trend_item: TrendItem | None = None,
) -> IdeaScore:
    category = str(idea.get("category") or (trend_item.category if trend_item else "other"))
    trend_score = score_trend_item(
        trend_item
        or TrendItem(
            title=str(idea.get("title") or idea.get("titulo") or ""),
            summary=str(idea.get("summary") or idea.get("resumen") or ""),
            source="GeneratedIdea",
            category=category,
        ),
        target_market=str(idea.get("target_market") or idea.get("target_marketet") or "global"),
        target_language=str(idea.get("target_language") or "es"),
        category=category,
    )
    payload = trend_score.as_payload()
    for key in payload:
        if key in idea:
            payload[key] = _clamp_score(idea[key])
    return _with_total(**{key: payload[key] for key in payload if key != "total_score"})


def calculate_total_score(
    *,
    viral_score: int,
    rpm_score: int,
    visual_score: int,
    narrative_clarity_score: int,
    evergreen_score: int,
    novelty_score: int,
    production_ease_score: int,
    copyright_risk: int,
    monetization_risk: int,
) -> int:
    positive = (
        viral_score * 0.25
        + rpm_score * 0.20
        + visual_score * 0.15
        + narrative_clarity_score * 0.15
        + evergreen_score * 0.10
        + novelty_score * 0.10
        + production_ease_score * 0.05
    )
    negative = copyright_risk * 0.10 + monetization_risk * 0.10
    return int(max(0, min(100, (positive - negative) * 10)))


def _with_total(**scores: int) -> IdeaScore:
    normalized = {key: _clamp_score(value) for key, value in scores.items()}
    return IdeaScore(
        **normalized,
        total_score=calculate_total_score(**normalized),
    )


def _clamp_score(value: Any, default: int = 5) -> int:
    try:
        numeric = int(round(float(value)))
    except (TypeError, ValueError):
        numeric = default
    return max(0, min(10, numeric))


def _keyword_hits(text: str, words: set[str]) -> int:
    return min(3, sum(1 for word in words if word in text))


def _signal_strength(signals: dict[str, Any]) -> int:
    raw = max(
        float(signals.get("hn_score") or 0),
        float(signals.get("points") or 0),
        float(signals.get("comments") or 0),
        float(signals.get("views") or 0) / 10_000,
    )
    if raw >= 500:
        return 3
    if raw >= 100:
        return 2
    if raw >= 10:
        return 1
    return 0

