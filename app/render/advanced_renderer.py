from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.core.enums import RenderPlanStatus, RenderStatus
from app.db import models
from app.db.repositories import add_and_commit, create_render
from app.render.audio_mixer import mix_voice_and_music, mux_audio_to_video
from app.render.ffmpeg_renderer import FFmpegRenderResult, render_basic_vertical_video
from app.services.render_plan_service import validate_render_plan
from app.services.subtitle_alignment_service import export_srt
from app.utils.files import write_text_file
from app.utils.safe_paths import safe_join
from app.utils.slugs import slugify
from app.utils.time import today_folder_prefix


def render_from_plan(
    session: Session,
    *,
    render_plan_id: int,
    overwrite: bool = True,
) -> FFmpegRenderResult:
    plan = session.get(models.RenderPlan, render_plan_id)
    if plan is None:
        raise ValueError(f"Render plan not found: {render_plan_id}")

    report = validate_render_plan(session, render_plan_id)
    if not report.ok:
        return _fail_plan(session, plan, "; ".join(report.errors))

    script = session.get(models.Script, plan.script_id)
    subtitles = session.get(models.SubtitleTrack, plan.subtitle_track_id)
    visual_plan = session.get(models.VisualPlan, plan.visual_plan_id)
    voiceover = session.get(models.VoiceoverJob, plan.voiceover_job_id) if plan.voiceover_job_id else None
    music = session.get(models.MusicTrack, plan.music_track_id) if plan.music_track_id else None
    if script is None or subtitles is None or visual_plan is None:
        return _fail_plan(session, plan, "El plan de render esta incompleto.")

    plan.status = RenderPlanStatus.RENDERING.value
    plan.error_message = None
    add_and_commit(session, plan)

    folder = _render_output_dir(script, plan.id)
    script_lines = _script_lines(script)
    duration = max(1.0, float(script.estimated_duration_seconds or 0))
    voice_path = voiceover.output_audio_path if voiceover else None
    music_path = music.file_path if music else None
    has_audio = bool(_existing_file(voice_path) or _existing_file(music_path))

    srt_path = _srt_path(session, subtitles, folder, overwrite)
    base_video_path = folder / ("video_silent.mp4" if has_audio else "video.mp4")
    render_result = render_basic_vertical_video(
        output_path=base_video_path,
        srt_path=srt_path,
        script_lines=script_lines,
        template_name=visual_plan.template_name,
        overwrite=overwrite,
        width=get_settings().default_video_width,
        height=get_settings().default_video_height,
        fps=get_settings().default_fps,
    )
    if not render_result.ok or not render_result.output_path:
        return _fail_plan(session, plan, render_result.error_message or "Render fallido.", render_result.command)

    final_video_path = Path(render_result.output_path)
    command = render_result.command
    if has_audio:
        mix_result = mix_voice_and_music(
            voice_path=voice_path,
            music_path=music_path,
            output_path=folder / "audio_mix.m4a",
            duration_seconds=duration,
            overwrite=overwrite,
        )
        if not mix_result.ok:
            return _fail_plan(session, plan, mix_result.error_message or "Mezcla de audio fallida.", mix_result.command)
        if mix_result.output_path:
            mux_result = mux_audio_to_video(
                video_path=render_result.output_path,
                audio_path=mix_result.output_path,
                output_path=folder / "video.mp4",
                overwrite=overwrite,
            )
            if not mux_result.ok or not mux_result.output_path:
                return _fail_plan(session, plan, mux_result.error_message or "Union de audio y video fallida.", mux_result.command)
            final_video_path = Path(mux_result.output_path)
            command = (render_result.command or []) + ["--audio-mux--"] + (mux_result.command or [])

    render_row = create_render(
        session,
        script_id=script.id,
        language=script.language,
        template_name=visual_plan.template_name,
        video_path=str(final_video_path),
        duration_seconds=duration,
        resolution=f"{get_settings().default_video_width}x{get_settings().default_video_height}",
        status=RenderStatus.RENDERED.value,
    )
    plan.output_path = str(final_video_path)
    plan.status = RenderPlanStatus.RENDERED.value
    plan.error_message = f"Render row #{render_row.id}"
    add_and_commit(session, plan)
    return FFmpegRenderResult(ok=True, output_path=str(final_video_path), command=command)


def _fail_plan(
    session: Session,
    plan: models.RenderPlan,
    message: str,
    command: list[str] | None = None,
) -> FFmpegRenderResult:
    plan.status = RenderPlanStatus.FAILED.value
    plan.error_message = message
    add_and_commit(session, plan)
    return FFmpegRenderResult(ok=False, output_path=None, error_message=message, command=command)


def _render_output_dir(script: models.Script, render_plan_id: int) -> Path:
    topic_title = script.topic.title if script.topic else f"script-{script.id}"
    folder_name = f"{today_folder_prefix()}_{slugify(topic_title)}_plan_{render_plan_id}"
    return safe_join(get_settings().output_dir, "renders", folder_name)


def _srt_path(
    session: Session,
    subtitles: models.SubtitleTrack,
    folder: Path,
    overwrite: bool,
) -> Path:
    if subtitles.srt_path and Path(subtitles.srt_path).exists():
        return Path(subtitles.srt_path)
    srt_path = folder / "subtitles.srt"
    write_text_file(srt_path, export_srt(session, subtitles.id), overwrite=overwrite)
    subtitles.srt_path = str(srt_path)
    add_and_commit(session, subtitles)
    return srt_path


def _script_lines(script: models.Script) -> list[dict[str, object]]:
    return [
        {
            "text": line.text,
            "visual_suggestion": line.visual_suggestion,
            "duration_seconds": line.duration_seconds,
            "subtitle_text": line.subtitle_text or line.text,
        }
        for line in script.lines
    ]


def _existing_file(path: str | Path | None) -> Path | None:
    if not path:
        return None
    candidate = Path(path)
    return candidate if candidate.exists() else None
