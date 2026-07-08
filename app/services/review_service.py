from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.core.validation import REQUIRED_REVIEW_FLAGS, missing_review_flags, review_is_approved
from app.utils.time import utc_now_iso


def build_review_payload(**flags: Any) -> dict[str, Any]:
    payload = {flag: bool(flags.get(flag, False)) for flag in REQUIRED_REVIEW_FLAGS}
    payload["review_notes"] = flags.get("review_notes")
    payload["approved"] = bool(flags.get("approved", False)) and not missing_review_flags(payload)
    payload["reviewed_at"] = utc_now_iso() if payload["approved"] else None
    return payload


def checklist_missing_items(payload: Mapping[str, Any]) -> list[str]:
    return missing_review_flags(payload)


def checklist_can_export(payload: Mapping[str, Any]) -> bool:
    return review_is_approved(payload)

