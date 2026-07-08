from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.external_tools.elevenlabs.schemas import AlignmentResult


def try_generate_alignment(
    audio_path: str,
    script_text: str,
    language: str,
) -> AlignmentResult:
    alignment_path = Path(audio_path).with_suffix(".alignment.json")
    if not alignment_path.exists():
        return AlignmentResult(
            ok=False,
            error_message="No hay alignment de ElevenLabs; usar fallback por duracion del guion.",
        )
    try:
        payload = json.loads(alignment_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return AlignmentResult(ok=False, error_message=f"Alignment corrupto: {exc}")
    duration = _duration_from_alignment(payload)
    return AlignmentResult(
        ok=True,
        alignment_json={
            "language": language,
            "script_chars": len(script_text),
            "elevenlabs_alignment": payload,
        },
        duration_seconds=duration,
    )


def alignment_to_subtitle_rows(
    alignment_result: AlignmentResult,
    script_lines: list[Any],
) -> list[dict[str, object]]:
    if not alignment_result.ok or alignment_result.duration_seconds is None:
        raise ValueError("Alignment result is not available.")
    total_duration = max(1.0, alignment_result.duration_seconds)
    line_durations = [max(0.1, float(getattr(line, "duration_seconds", 2.5) or 2.5)) for line in script_lines]
    base = sum(line_durations) or 1.0
    scale = total_duration / base
    cursor = 0.0
    rows = []
    for line, duration in zip(script_lines, line_durations, strict=False):
        end = cursor + duration * scale
        rows.append(
            {
                "start_seconds": cursor,
                "end_seconds": end,
                "text": str(getattr(line, "subtitle_text", None) or getattr(line, "text", "")),
            }
        )
        cursor = end
    return rows


def _duration_from_alignment(payload: dict[str, Any]) -> float | None:
    alignment = payload.get("normalized_alignment") or payload.get("alignment") or {}
    if not isinstance(alignment, dict):
        return None
    end_times = alignment.get("character_end_times_seconds")
    if not isinstance(end_times, list) or not end_times:
        return None
    try:
        return float(max(end_times))
    except (TypeError, ValueError):
        return None
