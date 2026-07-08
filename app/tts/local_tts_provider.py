from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from app.config.settings import get_settings
from app.tts.base import VoiceOption, VoiceoverResult


class LocalTTSProvider:
    name = "local_tts"

    def is_available(self) -> bool:
        settings = get_settings()
        return settings.enable_local_tts and (bool(settings.piper_tts_path) or settings.pyttsx3_enabled)

    def availability_reason(self) -> str:
        if self.is_available():
            return "Disponible: TTS local configurado."
        return "Desactivado. Configura ENABLE_LOCAL_TTS y un motor local si quieres usarlo."

    def list_voices(self, language: str = "es") -> list[VoiceOption]:
        return [
            VoiceOption(
                id="local_default",
                name="Voz local por defecto",
                language=language,
                provider=self.name,
                is_free=True,
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
                voice_name="Voz local por defecto",
                error_message=self.availability_reason(),
                metadata={"language": language, "input_chars": len(text), **dict(metadata or {})},
            )
        return VoiceoverResult(
            ok=False,
            provider=self.name,
            voice_id=voice_id or "local_default",
            voice_name="Voz local por defecto",
            error_message="El motor local esta configurado como opcion futura; importa audio manual por ahora.",
            metadata={"language": language, "output_path": str(output_path), **dict(metadata or {})},
        )
