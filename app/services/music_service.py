from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.constants import SAFE_AUDIO_EXTENSIONS
from app.db import models
from app.utils.licenses import music_license_ready
from app.utils.safe_paths import ensure_allowed_extension


def build_music_payload(
    *,
    title: str,
    artist: str | None,
    file_path: str,
    source: str,
    source_url: str | None,
    license_type: str,
    mood: str,
    energy: int,
    bpm: int | None,
    duration_seconds: float | None,
    attribution_required: bool,
    attribution_text: str | None,
    safe_for_monetization: bool,
    notes: str | None = None,
) -> dict[str, Any]:
    ensure_allowed_extension(Path(file_path), SAFE_AUDIO_EXTENSIONS)
    payload = {
        "title": title.strip(),
        "artist": artist or None,
        "file_path": file_path,
        "source": source.strip(),
        "source_url": source_url or None,
        "license_type": license_type.strip(),
        "mood": mood,
        "energy": max(1, min(5, int(energy))),
        "bpm": bpm,
        "duration_seconds": duration_seconds,
        "attribution_required": bool(attribution_required),
        "attribution_text": attribution_text or None,
        "safe_for_monetization": bool(safe_for_monetization),
        "notes": notes,
    }
    if not music_license_ready(payload):
        raise ValueError("Music license data is incomplete or not marked safe for monetization.")
    return payload


def suggest_music_for_script(
    session: Session,
    *,
    script_id: int,
    mood: str | None = None,
    energy: int | None = None,
    duration_seconds: float | None = None,
    include_unsafe: bool = False,
    limit: int = 10,
) -> list[models.MusicTrack]:
    script = session.get(models.Script, script_id)
    if script is None:
        raise ValueError(f"Script not found: {script_id}")
    preferred_mood = mood or _mood_from_script(script)
    preferred_energy = energy or _energy_from_script(script)
    target_duration = duration_seconds or script.estimated_duration_seconds

    statement = select(models.MusicTrack)
    if not include_unsafe:
        statement = statement.where(models.MusicTrack.safe_for_monetization.is_(True))
    tracks = list(session.scalars(statement).all())
    tracks.sort(
        key=lambda track: (
            0 if track.mood == preferred_mood else 1,
            abs(int(track.energy or 3) - preferred_energy),
            _duration_distance(track.duration_seconds, target_duration),
            track.title.lower(),
        )
    )
    return tracks[:limit]


def _mood_from_script(script: models.Script) -> str:
    category = script.topic.category if script.topic else ""
    if category in {"ai_tools", "tech_explained", "engineering"}:
        return "tech"
    if category in {"business_case", "history_explained", "mystery_explained"}:
        return "dramatic"
    if category in {"science_explained", "productivity", "finance_educational"}:
        return "educational"
    return "neutral"


def _energy_from_script(script: models.Script) -> int:
    text = f"{script.tone} {script.script_text}".lower()
    if "rapido" in text or "fast" in text or "urgente" in text:
        return 4
    if "calm" in text or "pausado" in text:
        return 2
    return 3


def _duration_distance(track_duration: float | None, target_duration: float | None) -> float:
    if track_duration is None or target_duration is None:
        return 999.0
    return abs(float(track_duration) - float(target_duration))
