from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SubtitleCue:
    index: int
    start_seconds: float
    end_seconds: float
    text: str


def seconds_to_srt_timestamp(seconds: float) -> str:
    if seconds < 0:
        raise ValueError("SRT timestamps cannot be negative.")
    milliseconds_total = int(round(seconds * 1000))
    hours, remainder = divmod(milliseconds_total, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, milliseconds = divmod(remainder, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{milliseconds:03}"


def cues_from_script_lines(lines: Iterable[Mapping[str, Any]]) -> list[SubtitleCue]:
    cues: list[SubtitleCue] = []
    cursor = 0.0
    for index, line in enumerate(lines, start=1):
        duration_value = (
            line["duration_seconds"]
            if line.get("duration_seconds") is not None
            else line.get("estimated_duration_seconds", 2.5)
        )
        duration = float(duration_value)
        if duration <= 0:
            raise ValueError("Subtitle durations must be positive.")
        text = str(line.get("subtitle_text") or line.get("text") or "").strip()
        if not text:
            continue
        cues.append(
            SubtitleCue(
                index=index,
                start_seconds=cursor,
                end_seconds=cursor + duration,
                text=text,
            )
        )
        cursor += duration
    return cues


def generate_srt(lines: Iterable[Mapping[str, Any]]) -> str:
    blocks = []
    for cue in cues_from_script_lines(lines):
        blocks.append(
            "\n".join(
                [
                    str(cue.index),
                    f"{seconds_to_srt_timestamp(cue.start_seconds)} --> {seconds_to_srt_timestamp(cue.end_seconds)}",
                    cue.text,
                ]
            )
        )
    return "\n\n".join(blocks) + ("\n" if blocks else "")
