from __future__ import annotations

from pathlib import Path
from typing import Any

from app.render.ffmpeg_renderer import FFmpegRenderResult, render_basic_vertical_video
from app.services.subtitle_service import generate_srt
from app.utils.files import write_text_file
from app.utils.safe_paths import safe_join
from app.utils.slugs import slugify
from app.utils.time import today_folder_prefix


def render_script_preview(
    *,
    output_dir: str | Path,
    topic_title: str,
    script_lines: list[dict[str, Any]],
    template_name: str = "clean_text_focus",
    overwrite: bool = False,
) -> FFmpegRenderResult:
    render_root = Path(output_dir).resolve()
    folder = safe_join(render_root, "renders", f"{today_folder_prefix()}_{slugify(topic_title)}")
    folder.mkdir(parents=True, exist_ok=True)
    srt_path = folder / "subtitles.srt"
    video_path = folder / "video.mp4"
    write_text_file(srt_path, generate_srt(script_lines), overwrite=overwrite)
    return render_basic_vertical_video(
        output_path=video_path,
        srt_path=srt_path,
        script_lines=script_lines,
        template_name=template_name,
        overwrite=overwrite,
    )

