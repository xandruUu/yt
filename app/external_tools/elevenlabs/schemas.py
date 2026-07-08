from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AlignmentResult:
    ok: bool
    alignment_json: dict[str, object] | None = None
    duration_seconds: float | None = None
    error_message: str | None = None


@dataclass(frozen=True)
class ElevenLabsSpeechResult:
    ok: bool
    audio_path: str | None = None
    duration_seconds: float | None = None
    alignment_path: str | None = None
    error_message: str | None = None
    estimated_cost: float | None = None
    actual_cost: float | None = None
    metadata: dict[str, object] = field(default_factory=dict)
