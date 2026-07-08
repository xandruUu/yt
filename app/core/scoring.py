from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TopicScores:
    viral_score: float
    rpm_score: float
    visual_score: float
    evergreen_score: float
    competition_score: float
    copyright_risk: float
    monetization_risk: float


def validate_score(value: float, field_name: str = "score") -> float:
    numeric = float(value)
    if numeric < 0 or numeric > 10:
        raise ValueError(f"{field_name} must be between 0 and 10.")
    return numeric


def calculate_topic_score(
    viral_score: float,
    rpm_score: float,
    visual_score: float,
    evergreen_score: float,
    competition_score: float,
    copyright_risk: float,
    monetization_risk: float,
) -> float:
    scores = TopicScores(
        viral_score=validate_score(viral_score, "viral_score"),
        rpm_score=validate_score(rpm_score, "rpm_score"),
        visual_score=validate_score(visual_score, "visual_score"),
        evergreen_score=validate_score(evergreen_score, "evergreen_score"),
        competition_score=validate_score(competition_score, "competition_score"),
        copyright_risk=validate_score(copyright_risk, "copyright_risk"),
        monetization_risk=validate_score(monetization_risk, "monetization_risk"),
    )

    raw_score = (
        scores.viral_score * 0.30
        + scores.rpm_score * 0.20
        + scores.visual_score * 0.15
        + scores.evergreen_score * 0.15
        + scores.competition_score * 0.10
        - scores.copyright_risk * 0.05
        - scores.monetization_risk * 0.05
    )
    normalized = (raw_score / 9.0) * 100
    return round(max(0.0, min(100.0, normalized)), 2)


def score_band(total_score: float) -> str:
    score = float(total_score)
    if score >= 80:
        return "high_priority"
    if score >= 60:
        return "interesting_test"
    if score >= 40:
        return "hook_dependent"
    return "discard_or_archive"

