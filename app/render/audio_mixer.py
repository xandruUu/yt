from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from app.config.settings import get_settings


@dataclass(frozen=True)
class AudioMixResult:
    ok: bool
    output_path: str | None = None
    error_message: str | None = None
    command: list[str] | None = None


def mix_voice_and_music(
    *,
    voice_path: str | Path | None,
    music_path: str | Path | None,
    output_path: str | Path,
    duration_seconds: float | None = None,
    voice_volume: float | None = None,
    music_volume: float | None = None,
    overwrite: bool = False,
) -> AudioMixResult:
    voice = _existing_path(voice_path)
    music = _existing_path(music_path)
    if voice is None and music is None:
        return AudioMixResult(ok=True, output_path=None)
    if not _ffmpeg_available():
        return AudioMixResult(ok=False, error_message="FFmpeg no esta disponible para mezclar audio.")

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists() and not overwrite:
        return AudioMixResult(ok=False, error_message=f"Output already exists: {output}")

    settings = get_settings()
    voice_volume = settings.default_voice_volume if voice_volume is None else voice_volume
    music_volume = settings.default_music_volume if music_volume is None else music_volume

    if voice and music:
        command = [
            settings.ffmpeg_path,
            "-y" if overwrite else "-n",
            "-i",
            str(voice),
            "-stream_loop",
            "-1",
            "-i",
            str(music),
            "-filter_complex",
            (
                f"[0:a]volume={voice_volume}[voice];"
                f"[1:a]volume={music_volume}[music];"
                "[voice][music]amix=inputs=2:duration=first:dropout_transition=2[a]"
            ),
            "-map",
            "[a]",
            "-c:a",
            "aac",
        ]
        if duration_seconds:
            command.extend(["-t", f"{duration_seconds:.2f}"])
        command.append(str(output))
        return _run_ffmpeg(command, output)

    source = voice or music
    volume = voice_volume if voice else music_volume
    command = [
        settings.ffmpeg_path,
        "-y" if overwrite else "-n",
        "-i",
        str(source),
        "-filter:a",
        f"volume={volume}",
        "-c:a",
        "aac",
    ]
    if duration_seconds:
        command.extend(["-t", f"{duration_seconds:.2f}"])
    command.append(str(output))
    return _run_ffmpeg(command, output)


def mux_audio_to_video(
    *,
    video_path: str | Path,
    audio_path: str | Path,
    output_path: str | Path,
    overwrite: bool = False,
) -> AudioMixResult:
    if not _ffmpeg_available():
        return AudioMixResult(ok=False, error_message="FFmpeg no esta disponible para unir audio y video.")
    video = Path(video_path)
    audio = Path(audio_path)
    if not video.exists():
        return AudioMixResult(ok=False, error_message=f"Video not found: {video}")
    if not audio.exists():
        return AudioMixResult(ok=False, error_message=f"Audio not found: {audio}")
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    command = [
        get_settings().ffmpeg_path,
        "-y" if overwrite else "-n",
        "-i",
        str(video),
        "-i",
        str(audio),
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-shortest",
        str(output),
    ]
    return _run_ffmpeg(command, output)


def _existing_path(path: str | Path | None) -> Path | None:
    if not path:
        return None
    candidate = Path(path)
    return candidate if candidate.exists() else None


def _ffmpeg_available() -> bool:
    return shutil.which(get_settings().ffmpeg_path) is not None


def _run_ffmpeg(command: list[str], output: Path) -> AudioMixResult:
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        return AudioMixResult(
            ok=False,
            error_message=completed.stderr.strip() or "FFmpeg audio command failed.",
            command=command,
        )
    return AudioMixResult(ok=True, output_path=str(output), command=command)
