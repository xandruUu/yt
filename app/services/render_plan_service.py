from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.core.enums import (
    RenderPlanStatus,
    ScriptStatus,
    SubtitleTrackStatus,
    VisualPlanStatus,
    VoiceoverJobStatus,
)
from app.db import models
from app.db.repositories import add_and_commit, create_render_plan
from app.render.ffmpeg_renderer import ffmpeg_available
from app.services.license_manifest_service import external_assets_missing_license


@dataclass(frozen=True)
class RenderValidationReport:
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def create_short_render_plan(
    session: Session,
    *,
    script_id: int,
    voiceover_job_id: int | None,
    subtitle_track_id: int,
    visual_plan_id: int,
    music_track_id: int | None = None,
    wizard_session_id: int | None = None,
) -> models.RenderPlan:
    return create_render_plan(
        session,
        wizard_session_id=wizard_session_id,
        script_id=script_id,
        voiceover_job_id=voiceover_job_id,
        subtitle_track_id=subtitle_track_id,
        visual_plan_id=visual_plan_id,
        music_track_id=music_track_id,
        status=RenderPlanStatus.PENDING.value,
    )


def validate_render_plan(session: Session, render_plan_id: int) -> RenderValidationReport:
    plan = _get_render_plan(session, render_plan_id)
    errors: list[str] = []
    warnings: list[str] = []

    script = session.get(models.Script, plan.script_id)
    if script is None:
        errors.append("Falta el guion.")
    elif script.status != ScriptStatus.APPROVED.value:
        errors.append("El guion no esta aprobado.")

    subtitle_track = session.get(models.SubtitleTrack, plan.subtitle_track_id) if plan.subtitle_track_id else None
    if subtitle_track is None:
        errors.append("Falta la pista de subtitulos.")
    elif subtitle_track.status != SubtitleTrackStatus.APPROVED.value:
        errors.append("Los subtitulos no estan aprobados.")

    visual_plan = session.get(models.VisualPlan, plan.visual_plan_id) if plan.visual_plan_id else None
    if visual_plan is None:
        errors.append("Falta el plan visual.")
    elif visual_plan.status != VisualPlanStatus.APPROVED.value:
        errors.append("El plan visual no esta aprobado.")
    else:
        missing_license_assets = external_assets_missing_license(session, visual_plan)
        for asset in missing_license_assets:
            errors.append(f"Asset externo #{asset.id} sin licencia/uso comercial aprobado.")

    voiceover = session.get(models.VoiceoverJob, plan.voiceover_job_id) if plan.voiceover_job_id else None
    if voiceover is None:
        warnings.append("No hay voz seleccionada; se renderizara con audio silencioso.")
    elif voiceover.status not in {VoiceoverJobStatus.APPROVED.value, VoiceoverJobStatus.PLACEHOLDER.value}:
        errors.append("La voz no esta aprobada o marcada como placeholder.")

    music = session.get(models.MusicTrack, plan.music_track_id) if plan.music_track_id else None
    if music is None:
        warnings.append("No hay musica seleccionada.")
    elif not music.safe_for_monetization:
        errors.append("La musica seleccionada no esta marcada como segura para monetizacion.")

    if not ffmpeg_available():
        errors.append("FFmpeg no esta instalado o no esta en PATH.")

    return RenderValidationReport(ok=not errors, errors=errors, warnings=warnings)


def mark_render_plan_ready(session: Session, render_plan_id: int) -> models.RenderPlan:
    plan = _get_render_plan(session, render_plan_id)
    report = validate_render_plan(session, render_plan_id)
    if not report.ok:
        plan.status = RenderPlanStatus.FAILED.value
        plan.error_message = "; ".join(report.errors)
        return add_and_commit(session, plan)
    plan.status = RenderPlanStatus.READY.value
    plan.error_message = None
    return add_and_commit(session, plan)


def approve_render_plan(session: Session, render_plan_id: int) -> models.RenderPlan:
    plan = _get_render_plan(session, render_plan_id)
    if plan.status != RenderPlanStatus.RENDERED.value or not plan.output_path:
        raise ValueError("Solo se puede aprobar un render ya generado.")
    plan.status = RenderPlanStatus.APPROVED.value
    return add_and_commit(session, plan)


def _get_render_plan(session: Session, render_plan_id: int) -> models.RenderPlan:
    plan = session.get(models.RenderPlan, render_plan_id)
    if plan is None:
        raise ValueError(f"Render plan not found: {render_plan_id}")
    return plan
