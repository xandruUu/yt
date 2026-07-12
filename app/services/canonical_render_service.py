from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.db import models
from app.db.repositories import create_render_job
from app.services.project_status_service import refresh_video_project_status

SCRIPT_READY_STATUSES = {"script_approved", "approved"}
VOICE_READY_STATUSES = {
    "completed",
    "generated",
    "approved",
    "ready",
    "placeholder",
    "imported_manual",
}
INVALID_CLIP_STATUSES = {"discarded", "rejected", "failed"}


@dataclass(frozen=True)
class MediaProbe:
    path: str
    duration_seconds: float | None = None
    width: int | None = None
    height: int | None = None
    fps: float | None = None


@dataclass(frozen=True)
class RenderReadiness:
    project: models.VideoProject
    script: models.ScriptDraft | None
    voiceover: models.VoiceoverJob | None
    selected_scenes: list[models.SelectedScene]
    clips_by_scene: dict[int, models.GeneratedClip]
    ffmpeg_available: bool
    ffprobe_available: bool
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def can_render_final(self) -> bool:
        return not self.blockers

    @property
    def missing_clip_count(self) -> int:
        return len(self.selected_scenes) - len(self.clips_by_scene)


def build_render_readiness(session: Session, video_project_id: int) -> RenderReadiness:
    project = _get_or_raise(session, models.VideoProject, video_project_id)
    script = _approved_script(session, video_project_id)
    voiceover = _ready_voiceover(session, video_project_id, script.id if script else None)
    selected_scenes = _selected_scenes(session, video_project_id)
    clips_by_scene = _clips_by_scene(session, [scene.id for scene in selected_scenes])
    settings = get_settings()
    blockers: list[str] = []
    warnings: list[str] = []
    ffmpeg_ok = _binary_available(settings.ffmpeg_path)
    ffprobe_ok = _binary_available(settings.ffprobe_path)

    if script is None:
        blockers.append("Falta guion aprobado. Ve a Produccion -> Guion.")
    if voiceover is None:
        blockers.append("Falta voz generada/aprobada. Ve a Produccion -> Voz.")
    elif not voiceover.output_path or not _local_path_exists(voiceover.output_path):
        blockers.append("La voz debe tener output_path local existente.")
    if not selected_scenes:
        blockers.append("Faltan escenas seleccionadas. Ve a Produccion -> Escenas.")

    missing = len(selected_scenes) - len(clips_by_scene)
    if missing:
        blockers.append(
            f"Faltan clips reales en {missing}/{len(selected_scenes)} escenas. Ve a Produccion -> Higgsfield."
        )

    for scene in selected_scenes:
        clip = clips_by_scene.get(scene.id)
        if clip is None:
            continue
        if not _local_path_exists(clip.file_path):
            blockers.append(
                f"El clip de SelectedScene #{scene.id} no es un archivo local existente."
            )

    if not ffmpeg_ok:
        blockers.append("FFmpeg no esta disponible.")
    if not ffprobe_ok:
        blockers.append("FFprobe no esta disponible.")

    if (
        ffprobe_ok
        and voiceover
        and voiceover.output_path
        and _local_path_exists(voiceover.output_path)
    ):
        voice_probe = probe_media(voiceover.output_path)
        if voice_probe.duration_seconds is None:
            blockers.append("FFprobe no pudo leer la duracion de la voz.")
    if ffprobe_ok:
        for scene_id, clip in clips_by_scene.items():
            if _local_path_exists(clip.file_path):
                probe = probe_media(clip.file_path)
                if probe.duration_seconds is None:
                    blockers.append(
                        f"FFprobe no pudo leer la duracion del clip de escena #{scene_id}."
                    )

    return RenderReadiness(
        project=project,
        script=script,
        voiceover=voiceover,
        selected_scenes=selected_scenes,
        clips_by_scene=clips_by_scene,
        ffmpeg_available=ffmpeg_ok,
        ffprobe_available=ffprobe_ok,
        blockers=blockers,
        warnings=warnings,
    )


def render_video_project(
    session: Session,
    *,
    video_project_id: int,
    output_path: str | None = None,
    force: bool = False,
) -> models.RenderJob:
    readiness = build_render_readiness(session, video_project_id)
    if not readiness.can_render_final:
        raise ValueError("No se puede renderizar: " + "; ".join(readiness.blockers))

    settings = get_settings()
    render_root = settings.output_dir / "renders" / f"project_{video_project_id}"
    tmp_dir = render_root / "tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    final_path = Path(output_path) if output_path else render_root / "final.mp4"
    if final_path.exists() and not force:
        raise FileExistsError(f"Ya existe el render final: {final_path}")

    job = create_render_job(
        session,
        video_project_id=video_project_id,
        output_path=str(final_path),
        width=settings.default_video_width,
        height=settings.default_video_height,
        fps=float(settings.default_fps),
        status="rendering",
        metadata_json=json.dumps(
            {"blockers": [], "warnings": readiness.warnings}, ensure_ascii=False
        ),
    )

    commands: list[list[str]] = []
    try:
        normalized_paths = _normalize_scene_clips(
            readiness,
            tmp_dir,
            force=force,
            commands=commands,
        )
        concat_video = tmp_dir / "concat_video.mp4"
        concat_list = _write_concat_list(tmp_dir / "concat_list.txt", normalized_paths)
        _run_ffmpeg(
            [
                settings.ffmpeg_path,
                "-y" if force else "-n",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_list),
                "-c",
                "copy",
                str(concat_video),
            ],
            commands,
        )
        _run_ffmpeg(
            [
                settings.ffmpeg_path,
                "-y" if force else "-n",
                "-i",
                str(concat_video),
                "-i",
                str(readiness.voiceover.output_path),
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
                "-shortest",
                "-c:v",
                "copy",
                "-c:a",
                "aac",
                str(final_path),
            ],
            commands,
        )
    except Exception as exc:
        job.status = "failed"
        job.error_message = str(exc)
        job.metadata_json = _render_metadata(readiness, commands, warnings=[str(exc)])
        session.commit()
        session.refresh(job)
        refresh_video_project_status(session, video_project_id)
        return job

    duration = probe_media(str(final_path)).duration_seconds
    job.status = "rendered"
    job.error_message = None
    job.output_path = str(final_path)
    job.duration_seconds = duration
    job.metadata_json = _render_metadata(readiness, commands, warnings=readiness.warnings)
    session.commit()
    session.refresh(job)
    refresh_video_project_status(session, video_project_id)
    return job


def probe_media(path: str | Path) -> MediaProbe:
    settings = get_settings()
    command = [
        settings.ffprobe_path,
        "-v",
        "error",
        "-show_entries",
        "format=duration:stream=width,height,r_frame_rate",
        "-of",
        "json",
        str(path),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        return MediaProbe(path=str(path))
    try:
        payload = json.loads(completed.stdout or "{}")
    except json.JSONDecodeError:
        payload = {}
    duration = _float_or_none(payload.get("format", {}).get("duration"))
    stream = _first_video_stream(payload)
    return MediaProbe(
        path=str(path),
        duration_seconds=duration,
        width=_int_or_none(stream.get("width")),
        height=_int_or_none(stream.get("height")),
        fps=_fps_or_none(stream.get("r_frame_rate")),
    )


def _normalize_scene_clips(
    readiness: RenderReadiness,
    tmp_dir: Path,
    *,
    force: bool,
    commands: list[list[str]],
) -> list[Path]:
    settings = get_settings()
    normalized: list[Path] = []
    for index, scene in enumerate(readiness.selected_scenes, start=1):
        clip = readiness.clips_by_scene[scene.id]
        output = tmp_dir / f"scene_{index:03d}.mp4"
        command = [
            settings.ffmpeg_path,
            "-y" if force else "-n",
            "-i",
            clip.file_path,
            "-an",
            "-vf",
            "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30,format=yuv420p",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(output),
        ]
        _run_ffmpeg(command, commands)
        normalized.append(output)
    return normalized


def _run_ffmpeg(command: list[str], commands: list[list[str]]) -> None:
    commands.append(command)
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        message = completed.stderr.strip() or completed.stdout.strip() or "FFmpeg fallo."
        raise RuntimeError(message)


def _write_concat_list(path: Path, clip_paths: list[Path]) -> Path:
    lines = [f"file '{_concat_path(clip)}'" for clip in clip_paths]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _concat_path(path: Path) -> str:
    return path.resolve().as_posix().replace("'", "'\\''")


def _render_metadata(
    readiness: RenderReadiness,
    commands: list[list[str]],
    *,
    warnings: list[str],
) -> str:
    return json.dumps(
        {
            "script_draft_id": readiness.script.id if readiness.script else None,
            "voiceover_job_id": readiness.voiceover.id if readiness.voiceover else None,
            "selected_scene_ids": [scene.id for scene in readiness.selected_scenes],
            "generated_clip_ids": [clip.id for clip in readiness.clips_by_scene.values()],
            "ffmpeg_commands": commands,
            "warnings": warnings,
        },
        ensure_ascii=False,
    )


def _approved_script(session: Session, project_id: int) -> models.ScriptDraft | None:
    return session.scalar(
        select(models.ScriptDraft)
        .where(
            models.ScriptDraft.video_project_id == project_id,
            models.ScriptDraft.status.in_(SCRIPT_READY_STATUSES),
        )
        .order_by(models.ScriptDraft.created_at.desc())
    )


def _ready_voiceover(
    session: Session,
    project_id: int,
    script_draft_id: int | None,
) -> models.VoiceoverJob | None:
    statement = select(models.VoiceoverJob).where(
        models.VoiceoverJob.video_project_id == project_id,
        models.VoiceoverJob.status.in_(VOICE_READY_STATUSES),
    )
    if script_draft_id is not None:
        statement = statement.where(models.VoiceoverJob.script_draft_id == script_draft_id)
    return session.scalar(statement.order_by(models.VoiceoverJob.created_at.desc()))


def _selected_scenes(session: Session, project_id: int) -> list[models.SelectedScene]:
    return list(
        session.scalars(
            select(models.SelectedScene)
            .where(models.SelectedScene.video_project_id == project_id)
            .order_by(models.SelectedScene.sort_order)
        ).all()
    )


def _clips_by_scene(
    session: Session, selected_scene_ids: list[int]
) -> dict[int, models.GeneratedClip]:
    if not selected_scene_ids:
        return {}
    clips = list(
        session.scalars(
            select(models.GeneratedClip)
            .where(
                models.GeneratedClip.selected_scene_id.in_(selected_scene_ids),
                models.GeneratedClip.status.not_in(INVALID_CLIP_STATUSES),
            )
            .order_by(models.GeneratedClip.created_at.desc())
        ).all()
    )
    result: dict[int, models.GeneratedClip] = {}
    for clip in clips:
        result.setdefault(clip.selected_scene_id, clip)
    return result


def _binary_available(path_or_name: str) -> bool:
    path = Path(path_or_name)
    return path.exists() or shutil.which(path_or_name) is not None


def _local_path_exists(value: str | None) -> bool:
    if not value or value.startswith(("http://", "https://")):
        return False
    return Path(value).exists()


def _first_video_stream(payload: dict[str, Any]) -> dict[str, Any]:
    streams = payload.get("streams")
    if not isinstance(streams, list):
        return {}
    for stream in streams:
        if isinstance(stream, dict) and stream.get("width") and stream.get("height"):
            return stream
    return streams[0] if streams and isinstance(streams[0], dict) else {}


def _float_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _fps_or_none(value: Any) -> float | None:
    if not isinstance(value, str) or "/" not in value:
        return _float_or_none(value)
    numerator, denominator = value.split("/", 1)
    try:
        return float(numerator) / float(denominator)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def _get_or_raise(session: Session, model: type[models.Base], entity_id: int):
    entity = session.get(model, entity_id)
    if entity is None:
        raise ValueError(f"{model.__name__} not found: {entity_id}")
    return entity
