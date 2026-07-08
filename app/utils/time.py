from __future__ import annotations

from datetime import UTC, datetime


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def today_folder_prefix() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d")

