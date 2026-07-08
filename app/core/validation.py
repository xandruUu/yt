from __future__ import annotations

from collections.abc import Mapping

REQUIRED_REVIEW_FLAGS = (
    "hook_strong",
    "script_fact_checked",
    "language_natural",
    "music_license_ok",
    "assets_license_ok",
    "no_reused_content_risk",
    "no_sensitive_content",
    "subtitles_readable",
    "audio_clear",
    "video_not_too_repetitive",
    "metadata_not_misleading",
    "made_for_kids_false_confirmed",
    "synthetic_media_reviewed",
)


def missing_review_flags(payload: Mapping[str, object]) -> list[str]:
    return [flag for flag in REQUIRED_REVIEW_FLAGS if not bool(payload.get(flag))]


def review_is_approved(payload: Mapping[str, object]) -> bool:
    return not missing_review_flags(payload) and bool(payload.get("approved"))

