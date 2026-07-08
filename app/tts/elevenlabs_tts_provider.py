from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from app.config.settings import get_settings
from app.external_tools.elevenlabs.provider import ElevenLabsProvider
from app.tts.base import VoiceOption, VoiceoverResult


class ElevenLabsTTSProvider:
    name = "elevenlabs_tts"

    def is_available(self) -> bool:
        return ElevenLabsProvider().is_available()

    def availability_reason(self) -> str:
        return ElevenLabsProvider().get_status().detail

    def list_voices(self, language: str = "es") -> list[VoiceOption]:
        voice_id = get_settings().elevenlabs_default_voice_id or "default"
        return [
            VoiceOption(
                id=voice_id,
                name=f"ElevenLabs {voice_id}",
                language=language,
                provider=self.name,
                is_free=False,
                notes=self.availability_reason(),
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
        metadata_dict = dict(metadata or {})
        result = ElevenLabsProvider().synthesize_text(
            text=text,
            language=language,
            voice_id=voice_id,
            model_id=str(metadata_dict.get("model_id") or get_settings().elevenlabs_model_id),
            output_path=output_path,
            confirmed_paid=bool(metadata_dict.get("confirmed_paid", False)),
            with_timestamps=bool(metadata_dict.get("with_timestamps", True)),
        )
        return VoiceoverResult(
            ok=result.ok,
            provider=self.name,
            voice_id=voice_id or get_settings().elevenlabs_default_voice_id,
            voice_name=f"ElevenLabs {voice_id or get_settings().elevenlabs_default_voice_id or 'default'}",
            audio_path=result.audio_path,
            duration_seconds=result.duration_seconds,
            error_message=result.error_message,
            metadata={**result.metadata, **metadata_dict},
        )
