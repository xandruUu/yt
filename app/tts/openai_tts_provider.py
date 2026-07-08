from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

from app.config.settings import get_settings
from app.tts.base import VoiceOption, VoiceoverResult


class OpenAITTSProvider:
    name = "openai_tts"

    def is_available(self) -> bool:
        settings = get_settings()
        return settings.enable_openai_tts and bool(os.getenv("OPENAI_API_KEY"))

    def availability_reason(self) -> str:
        if self.is_available():
            return "Disponible: OpenAI TTS configurado."
        return "Desactivado. Requiere ENABLE_OPENAI_TTS=true y OPENAI_API_KEY."

    def list_voices(self, language: str = "es") -> list[VoiceOption]:
        settings = get_settings()
        voice_id = settings.openai_tts_voice or "alloy"
        return [
            VoiceOption(
                id=voice_id,
                name=f"OpenAI {voice_id}",
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
        if not self.is_available():
            return VoiceoverResult(
                ok=False,
                provider=self.name,
                voice_id=voice_id,
                voice_name=voice_id or "OpenAI TTS",
                error_message=self.availability_reason(),
                metadata={"language": language, "input_chars": len(text), **dict(metadata or {})},
            )
        return VoiceoverResult(
            ok=False,
            provider=self.name,
            voice_id=voice_id,
            voice_name=voice_id or "OpenAI TTS",
            error_message="OpenAI TTS esta preparado como proveedor opcional, pero esta build no realiza llamadas externas.",
            metadata={"language": language, "output_path": str(output_path), **dict(metadata or {})},
        )
