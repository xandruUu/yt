from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.config.settings import get_settings
from app.render.subtitle_renderer import ass_force_style
from app.render.templates import get_template


@dataclass(frozen=True)
class FFmpegRenderResult:
    ok: bool
    output_path: str | None
    error_message: str | None = None
    command: list[str] | None = None


def ffmpeg_available() -> bool:
    return shutil.which(get_settings().ffmpeg_path) is not None


def render_basic_vertical_video(
    *,
    output_path: str | Path,
    srt_path: str | Path,
    script_lines: list[dict[str, Any]],
    template_name: str,
    overwrite: bool = False,
    width: int = 1080,
    height: int = 1920,
    fps: int = 30,
) -> FFmpegRenderResult:
    output = Path(output_path)
    srt = Path(srt_path)
    if output.exists() and not overwrite:
        return FFmpegRenderResult(False, None, f"Output already exists: {output}")
    if not ffmpeg_available():
        return FFmpegRenderResult(False, None, "FFmpeg is not installed or not in PATH.")
    duration = max(1.0, sum(float(line.get("duration_seconds") or 2.5) for line in script_lines))
    template = get_template(template_name)
    output.parent.mkdir(parents=True, exist_ok=True)

    video_filter = _subtitles_filter(srt, template_name) if srt.exists() else "null"
    command = [
        get_settings().ffmpeg_path,
        "-y" if overwrite else "-n",
        "-f",
        "lavfi",
        "-i",
        f"color=c={template.background_color}:s={width}x{height}:r={fps}:d={duration:.2f}",
        "-f",
        "lavfi",
        "-i",
        f"anullsrc=channel_layout=stereo:sample_rate=44100:d={duration:.2f}",
        "-vf",
        video_filter,
        "-shortest",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        str(output),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        return FFmpegRenderResult(
            False,
            None,
            completed.stderr.strip() or "FFmpeg render failed.",
            command,
        )
    return FFmpegRenderResult(True, str(output), None, command)


def _subtitles_filter(srt_path: Path, template_name: str) -> str:
    # FFmpeg filter paths need forward slashes and escaped drive separators on Windows.
    normalized = srt_path.resolve().as_posix().replace(":", "\\:").replace("'", "\\'")
    style = ass_force_style(template_name).replace("'", "\\'")
    return f"subtitles='{normalized}':force_style='{style}'"
