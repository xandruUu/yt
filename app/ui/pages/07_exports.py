from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import streamlit as st
from sqlalchemy import select

from app.config.settings import get_settings
from app.db import models
from app.db.database import new_session
from app.services.export_service import create_canonical_export_package
from app.services.project_status_service import refresh_video_project_status
from app.utils.text import normalize_hashtags


def render() -> None:
    st.title("Exportaciones")
    with new_session() as session:
        render_job = _select_approved_render_job(session)
        if render_job is None:
            st.info("Aprueba un RenderJob canonico antes de exportar.")
            _manual_publish_marker(session)
            return

        st.video(render_job.output_path)
        defaults = _export_defaults(session, render_job)
        st.subheader("Metadatos del paquete")
        title = st.text_input("Titulo", value=defaults["title"])
        description = st.text_area("Descripcion", value=defaults["description"], height=140)
        hashtags = st.text_input("Hashtags", value=" ".join(defaults["hashtags"]))
        if st.button("Exportar paquete canonico", type="primary"):
            settings = get_settings()
            try:
                package = create_canonical_export_package(
                    session,
                    render_job_id=render_job.id,
                    exports_dir=settings.exports_dir,
                    title=title,
                    description=description,
                    hashtags=normalize_hashtags(hashtags),
                    overwrite=True,
                )
            except Exception as exc:  # noqa: BLE001 - Streamlit should show the failure.
                st.error(str(exc))
                return
            st.success(f"Exportado en {package['export_folder']}")
            st.rerun()

        _manual_publish_marker(session)


def _select_approved_render_job(session) -> models.RenderJob | None:
    jobs = [
        job
        for job in session.scalars(
            select(models.RenderJob)
            .where(
                models.RenderJob.status == "rendered",
                models.RenderJob.approved.is_(True),
            )
            .order_by(models.RenderJob.created_at.desc())
        ).all()
        if job.output_path and Path(job.output_path).exists()
    ]
    if not jobs:
        return None
    options = {
        f"RenderJob #{job.id} | Proyecto #{job.video_project_id} | {Path(job.output_path).name}": job.id
        for job in jobs
    }
    selected = st.selectbox("Render aprobado", list(options))
    return session.get(models.RenderJob, options[selected])


def _export_defaults(session, render_job: models.RenderJob) -> dict[str, Any]:
    project = session.get(models.VideoProject, render_job.video_project_id)
    if project is None:
        return {"title": "", "description": "", "hashtags": ["#shorts"]}
    recipe = (
        session.get(models.MetadataRecipeDraft, project.metadata_recipe_id)
        if project.metadata_recipe_id
        else None
    )
    title = recipe.selected_title if recipe and recipe.selected_title else project.title
    description = (
        recipe.selected_description
        if recipe and recipe.selected_description
        else project.description
    )
    hashtags = _json_list(recipe.selected_hashtags_json if recipe else None) or _json_list(
        project.hashtags_json
    )
    return {
        "title": title,
        "description": description,
        "hashtags": normalize_hashtags(hashtags or ["#shorts"]),
    }


def _manual_publish_marker(session) -> None:
    st.subheader("Marcador de subida manual")
    jobs = [
        job
        for job in session.scalars(
            select(models.RenderJob).order_by(models.RenderJob.created_at.desc())
        ).all()
        if _metadata(job.metadata_json).get("export_folder")
    ]
    if not jobs:
        return
    options = {
        f"RenderJob #{job.id} | {Path(_metadata(job.metadata_json)['export_folder']).name}": job.id
        for job in jobs
    }
    selected = st.selectbox("Paquete exportado", list(options))
    url = st.text_input("URL manual de YouTube")
    if st.button("Marcar como subido manualmente"):
        job = session.get(models.RenderJob, options[selected])
        if job:
            metadata = _metadata(job.metadata_json)
            metadata["manual_youtube_url"] = url
            job.metadata_json = json.dumps(metadata, ensure_ascii=False)
            session.commit()
            refresh_video_project_status(session, job.video_project_id)
            st.success("URL de subida manual guardada.")
            st.rerun()


def _json_list(raw: str | None) -> list[str]:
    try:
        value = json.loads(raw or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _metadata(raw: str | None) -> dict[str, Any]:
    try:
        value = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}
