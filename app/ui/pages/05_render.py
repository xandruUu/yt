from __future__ import annotations

import json

import streamlit as st
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.db import models
from app.db.database import new_session
from app.db.repositories import create_render_job
from app.services.canonical_render_service import (
    RenderReadiness as CanonicalRenderReadiness,
)
from app.services.canonical_render_service import (
    build_render_readiness,
    render_video_project,
)


def render() -> None:
    st.title("Renderizar")
    st.caption("Render canonico con RenderJob, clips locales, voz local y FFmpeg.")
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
        _render_final_controls(session, readiness)
        st.divider()
        _render_preview_controls(session, readiness, settings)
        st.divider()
        _render_jobs_table(session, project.id)


def canonical_render_readiness(session: Session, project_id: int) -> CanonicalRenderReadiness:
    return build_render_readiness(session, project_id)


def create_canonical_render_job(
    session: Session,
    *,
    project_id: int,
    output_path: str | None,
    preview: bool,
) -> models.RenderJob:
    if not preview:
        return render_video_project(session, video_project_id=project_id, output_path=output_path)

    readiness = canonical_render_readiness(session, project_id)
    settings = get_settings()
    metadata = {
        "render_type": "placeholder_preview",
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
        status="placeholder_preview",
        error_message="Preview con placeholders; no es render final.",
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
    cols = st.columns(5)
    cols[0].metric("Guion", readiness.script.status if readiness.script else "faltante")
    cols[1].metric("Voz", readiness.voiceover.status if readiness.voiceover else "faltante")
    cols[2].metric("Escenas", len(readiness.selected_scenes))
    cols[3].metric("Clips", f"{len(readiness.clips_by_scene)}/{len(readiness.selected_scenes)}")
    cols[4].metric(
        "FFmpeg",
        "OK" if readiness.ffmpeg_available and readiness.ffprobe_available else "faltante",
    )
    if readiness.blockers:
        for blocker in readiness.blockers:
            st.warning(blocker)
    else:
        st.success("Todo listo para render final real con FFmpeg.")


def _render_final_controls(
    session: Session,
    readiness: CanonicalRenderReadiness,
) -> None:
    st.subheader("Render final real con FFmpeg")
    default_output = (
        get_settings().output_dir / "renders" / f"project_{readiness.project.id}" / "final.mp4"
    )
    output_path = st.text_input("Ruta de salida final", value=str(default_output))
    force = st.checkbox("Sobrescribir final.mp4 si ya existe", value=False)
    if st.button(
        "Render final real con FFmpeg",
        type="primary",
        disabled=not readiness.can_render_final,
    ):
        try:
            job = render_video_project(
                session,
                video_project_id=readiness.project.id,
                output_path=output_path.strip() or None,
                force=force,
            )
        except Exception as exc:  # noqa: BLE001 - Streamlit should surface failures.
            st.error(str(exc))
            return
        if job.status == "rendered":
            st.success(f"RenderJob #{job.id} renderizado: {job.output_path}")
        else:
            st.error(job.error_message or f"RenderJob #{job.id} fallo.")
        st.rerun()


def _render_preview_controls(
    session: Session,
    readiness: CanonicalRenderReadiness,
    settings,
) -> None:
    st.subheader("Preview con placeholders")
    st.info("Este preview usa placeholders. No es render final de produccion.")
    preview_path = str(
        settings.output_dir / f"project_{readiness.project.id}_preview_placeholder.mp4"
    )
    if st.button("Crear preview placeholder"):
        job = create_canonical_render_job(
            session,
            project_id=readiness.project.id,
            output_path=preview_path,
            preview=True,
        )
        st.success(f"RenderJob preview #{job.id} registrado.")
        st.rerun()


def _render_jobs_table(session: Session, project_id: int) -> None:
    st.subheader("RenderJobs existentes")
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
                "approved": job.approved,
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


def _project_label(project: models.VideoProject) -> str:
    return f"#{project.id} | {project.title[:60]} | {project.status} | {project.content_language}"
