from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from app.core.constants import SAFE_AUDIO_EXTENSIONS
from app.tts.base import VoiceOption, VoiceoverResult
from app.utils.files import copy_file
from app.utils.safe_paths import ensure_allowed_extension
from app.utils.slugs import slugify


class ManualVoiceProvider:
    name = "manual_recording"

    def is_available(self) -> bool:
        return True

    def availability_reason(self) -> str:
        return "Disponible: importa un audio grabado manualmente."

    def list_voices(self, language: str = "es") -> list[VoiceOption]:
        return [
            VoiceOption(
                id="manual_upload",
                name="Grabacion manual",
                language=language,
                provider=self.name,
                is_free=True,
                notes="Sube o indica la ruta de un archivo de voz local.",
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
            ok=False,
            provider=self.name,
            voice_id=voice_id,
            voice_name="Grabacion manual",
            error_message="El proveedor manual no sintetiza voz; importa un archivo de audio.",
            metadata={"language": language, "input_chars": len(text), **dict(metadata or {})},
        )

    def import_audio(
        self,
        *,
        source_path: str | Path,
        destination_dir: str | Path,
        overwrite: bool = False,
        duration_seconds: float | None = None,
    ) -> VoiceoverResult:
        source = Path(source_path).expanduser()
        ensure_allowed_extension(source, SAFE_AUDIO_EXTENSIONS)
        if not source.exists():
            raise FileNotFoundError(source)
        destination_root = Path(destination_dir)
        destination_name = f"{slugify(source.stem)}{source.suffix.lower()}"
        destination = destination_root / destination_name
        copied = copy_file(source, destination, overwrite=overwrite)
        return VoiceoverResult(
            ok=True,
            provider=self.name,
            voice_id="manual_upload",
            voice_name="Grabacion manual",
            audio_path=str(copied),
            duration_seconds=duration_seconds,
            metadata={"source_path": str(source)},
        )
