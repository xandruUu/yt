from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from app.tts.base import VoiceOption, VoiceoverResult


class PlaceholderVoiceProvider:
    name = "placeholder"

    def is_available(self) -> bool:
        return True

    def availability_reason(self) -> str:
        return "Disponible: continua sin voz y renderiza con audio silencioso."

    def list_voices(self, language: str = "es") -> list[VoiceOption]:
        return [
            VoiceOption(
                id="no_voice",
                name="Sin voz",
                language=language,
                provider=self.name,
                is_free=True,
                notes="Usa subtitulos y audio silencioso como placeholder.",
            )
        ]

    def synthesize(
        self,
        *,
        text: str,
        voice_id: str | None,
        output_path: str | Path,
        language: str = "es",
        metadata: Mapping[str, object] | None = None,
    ) -> VoiceoverResult:
        return VoiceoverResult(
            ok=True,
            provider=self.name,
            voice_id=voice_id or "no_voice",
            voice_name="Sin voz",
            audio_path=None,
            duration_seconds=None,
            metadata={"language": language, "placeholder": True, "input_chars": len(text), **dict(metadata or {})},
        )
