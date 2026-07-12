from __future__ import annotations

import json
from dataclasses import dataclass

import streamlit as st
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.db import models
from app.db.database import new_session
from app.db.repositories import create_render_job

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
class CanonicalRenderReadiness:
    project: models.VideoProject
    script: models.ScriptDraft | None
    voiceover: models.VoiceoverJob | None
    selected_scenes: list[models.SelectedScene]
    clips_by_scene: dict[int, models.GeneratedClip]
    blockers: list[str]

    @property
    def can_render_final(self) -> bool:
        return not self.blockers

    @property
    def missing_clip_count(self) -> int:
        return len(self.selected_scenes) - len(self.clips_by_scene)


def render() -> None:
    st.title("Renderizar")
    st.caption("Render canonico basado en VideoProject, voz, escenas seleccionadas y clips reales.")
    settings = get_settings()
    with new_session() as session:
        project = _select_project(session)
        if project is None:
            st.info("Crea tu primer proyecto desde Investigacion -> Creacion -> Ideas.")
            return

        _render_project_summary(project)
        readiness = canonical_render_readiness(session, project.id)
        _render_readiness(readiness)
        st.divider()
        _render_final_controls(session, readiness, settings)
        st.divider()
        _render_preview_controls(session, readiness, settings)
        st.divider()
        _render_jobs_table(session, project.id)


def canonical_render_readiness(session: Session, project_id: int) -> CanonicalRenderReadiness:
    project = _get_or_raise(session, models.VideoProject, project_id)
    script = _approved_script(session, project_id)
    voiceover = _ready_voiceover(session, project_id, script.id if script else None)
    selected_scenes = _selected_scenes(session, project_id)
    clips_by_scene = _clips_by_scene(session, [scene.id for scene in selected_scenes])
    blockers: list[str] = []

    if script is None:
        blockers.append("Falta guion aprobado. Ve a Produccion -> Guion.")
    if voiceover is None:
        blockers.append("Falta voz generada/aprobada. Ve a Produccion -> Voz.")
    if not selected_scenes:
        blockers.append("Faltan escenas seleccionadas. Ve a Produccion -> Escenas.")
    missing = len(selected_scenes) - len(clips_by_scene)
    if missing:
        blockers.append(
            f"Faltan clips reales en {missing}/{len(selected_scenes)} escenas. Ve a Mapeo de clips."
        )

    return CanonicalRenderReadiness(
        project=project,
        script=script,
        voiceover=voiceover,
        selected_scenes=selected_scenes,
        clips_by_scene=clips_by_scene,
        blockers=blockers,
    )


def create_canonical_render_job(
    session: Session,
    *,
    project_id: int,
    output_path: str | None,
    preview: bool,
) -> models.RenderJob:
    readiness = canonical_render_readiness(session, project_id)
    settings = get_settings()
    if not preview and not readiness.can_render_final:
        raise ValueError("No se puede crear render final: faltan piezas canonicas.")
    metadata = {
        "render_type": "placeholder_preview" if preview else "final_ready",
        "script_draft_id": readiness.script.id if readiness.script else None,
        "voiceover_job_id": readiness.voiceover.id if readiness.voiceover else None,
        "selected_scene_ids": [scene.id for scene in readiness.selected_scenes],
        "generated_clip_ids": [clip.id for clip in readiness.clips_by_scene.values()],
        "blockers": readiness.blockers,
    }
    return create_render_job(
        session,
        video_project_id=project_id,
        output_path=output_path,
        width=settings.default_video_width,
        height=settings.default_video_height,
        fps=float(settings.default_fps),
        duration_seconds=float(readiness.project.target_duration_seconds),
        status="placeholder_preview" if preview else "ready",
        error_message="Preview con placeholders; no es render final." if preview else None,
        metadata_json=json.dumps(metadata, ensure_ascii=False),
    )


def _select_project(session: Session) -> models.VideoProject | None:
    projects = list(
        session.scalars(
            select(models.VideoProject).order_by(models.VideoProject.created_at.desc())
        ).all()
    )
    if not projects:
        return None
    project_id = st.selectbox(
        "Proyecto",
        [project.id for project in projects],
        format_func=lambda value: _project_label(
            next(project for project in projects if project.id == value)
        ),
    )
    return session.get(models.VideoProject, int(project_id))


def _render_project_summary(project: models.VideoProject) -> None:
    cols = st.columns(5)
    cols[0].metric("ID", project.id)
    cols[1].metric("Estado", project.status)
    cols[2].metric("Idioma", project.content_language)
    cols[3].metric("Duracion", f"{project.target_duration_seconds}s")
    cols[4].metric("Creado", project.created_at.strftime("%Y-%m-%d"))
    st.subheader(project.title)


def _render_readiness(readiness: CanonicalRenderReadiness) -> None:
    cols = st.columns(4)
    cols[0].metric("Guion", readiness.script.status if readiness.script else "faltante")
    cols[1].metric("Voz", readiness.voiceover.status if readiness.voiceover else "faltante")
    cols[2].metric("Escenas", len(readiness.selected_scenes))
    cols[3].metric("Clips", f"{len(readiness.clips_by_scene)}/{len(readiness.selected_scenes)}")
    if readiness.blockers:
        for blocker in readiness.blockers:
            st.warning(blocker)
    else:
        st.success("Todo listo para render final con clips reales.")


def _render_final_controls(
    session: Session,
    readiness: CanonicalRenderReadiness,
    settings,
) -> None:
    st.subheader("Render final con clips reales")
    output_path = st.text_input(
        "Ruta de salida final opcional",
        value=str(settings.output_dir / f"project_{readiness.project.id}_final.mp4"),
    )
    if st.button(
        "Crear RenderJob final",
        type="primary",
        disabled=not readiness.can_render_final,
    ):
        try:
            job = create_canonical_render_job(
                session,
                project_id=readiness.project.id,
                output_path=output_path.strip() or None,
                preview=False,
            )
        except ValueError as exc:
            st.error(str(exc))
            return
        st.success(f"RenderJob #{job.id} preparado para render final.")
        st.rerun()


def _render_preview_controls(
    session: Session,
    readiness: CanonicalRenderReadiness,
    settings,
) -> None:
    st.subheader("Preview con placeholders")
    st.info("Este preview usa placeholders. No es el render final de produccion.")
    preview_path = str(
        settings.output_dir / f"project_{readiness.project.id}_preview_placeholder.mp4"
    )
    if st.button("Registrar preview placeholder"):
        job = create_canonical_render_job(
            session,
            project_id=readiness.project.id,
            output_path=preview_path,
            preview=True,
        )
        st.success(f"RenderJob preview #{job.id} registrado.")
        st.rerun()


def _render_jobs_table(session: Session, project_id: int) -> None:
    st.subheader("RenderJobs")
    jobs = list(
        session.scalars(
            select(models.RenderJob)
            .where(models.RenderJob.video_project_id == project_id)
            .order_by(models.RenderJob.created_at.desc())
        ).all()
    )
    if not jobs:
        st.info("Todavia no hay RenderJobs para este proyecto.")
        return
    st.dataframe(
        [
            {
                "id": job.id,
                "status": job.status,
                "output_path": job.output_path,
                "duration": job.duration_seconds,
                "error": job.error_message,
                "created_at": job.created_at,
            }
            for job in jobs
        ],
        use_container_width=True,
        hide_index=True,
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


def _get_or_raise(session: Session, model: type[models.Base], entity_id: int):
    entity = session.get(model, entity_id)
    if entity is None:
        raise ValueError(f"{model.__name__} not found: {entity_id}")
    return entity


def _project_label(project: models.VideoProject) -> str:
    return f"#{project.id} | {project.title[:60]} | {project.status} | {project.content_language}"
