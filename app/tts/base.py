from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class VoiceOption:
    id: str
    name: str
    language: str
    provider: str
    is_free: bool = True
    notes: str | None = None


@dataclass(frozen=True)
class VoiceoverResult:
    ok: bool
    provider: str
    voice_id: str | None
    voice_name: str | None
    audio_path: str | None = None
    duration_seconds: float | None = None
    error_message: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)


class TTSProvider(Protocol):
    name: str

    def is_available(self) -> bool:
        ...

    def availability_reason(self) -> str:
        ...

    def list_voices(self, language: str = "es") -> list[VoiceOption]:
        ...

    def synthesize(
        self,
        *,
        text: str,
        voice_id: str | None,
        output_path: str | Path,
        language: str = "es",
        metadata: Mapping[str, object] | None = None,
    ) -> VoiceoverResult:
        ...
