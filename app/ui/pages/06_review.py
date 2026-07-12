from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import streamlit as st
from sqlalchemy import select

from app.db import models
from app.db.database import new_session
from app.services.project_status_service import refresh_video_project_status

CANONICAL_REVIEW_FLAGS = {
    "hook_strong": "Hook fuerte",
    "script_fact_checked": "Script fact-checked",
    "voice_clear": "Voz clara",
    "clips_complete": "Clips completos",
    "no_text_or_watermark": "Sin texto/watermark accidental",
    "no_sensitive_content": "Sin contenido sensible",
    "duration_correct": "Duracion correcta",
    "vertical_format": "Formato vertical",
}


def render() -> None:
    st.title("Revision")
    with new_session() as session:
        job = _select_render_job(session)
        if job is None:
            st.info("Crea un RenderJob primero.")
            return

        _render_job_summary(job)
        _render_video(job)
        script = _script_for_render_job(session, job)
        if script is not None:
            st.subheader("Guion")
            st.text_area("Texto del guion", script.voiceover_text, height=220, disabled=True)

        if job.status == "placeholder_preview":
            st.warning("Este preview usa placeholders. No es render final de produccion.")
            return

        _review_form(session, job)


def _select_render_job(session) -> models.RenderJob | None:
    jobs = list(
        session.scalars(select(models.RenderJob).order_by(models.RenderJob.created_at.desc())).all()
    )
    if not jobs:
        return None
    options = {
        f"RenderJob #{job.id} | Proyecto #{job.video_project_id} | {job.status}": job.id
        for job in jobs
    }
    selected = st.selectbox("RenderJob", list(options))
    return session.get(models.RenderJob, options[selected])


def _render_job_summary(job: models.RenderJob) -> None:
    cols = st.columns(5)
    cols[0].metric("RenderJob", job.id)
    cols[1].metric("VideoProject", job.video_project_id)
    cols[2].metric("status", job.status)
    cols[3].metric("Duracion", f"{job.duration_seconds or 0:g}s")
    cols[4].metric("Aprobado", "si" if job.approved else "no")
    st.caption(f"output_path: {job.output_path or '-'}")
    st.caption(f"created_at: {job.created_at}")
    if job.error_message:
        st.warning(job.error_message)


def _render_video(job: models.RenderJob) -> None:
    if job.output_path and Path(job.output_path).exists():
        st.video(job.output_path)
    elif job.output_path:
        st.warning("El output_path no existe localmente.")


def _review_form(session, job: models.RenderJob) -> None:
    st.subheader("Checklist de revision")
    current = _review_metadata(job)
    with st.form(f"canonical_review_{job.id}"):
        flags = {
            flag: st.checkbox(label, value=bool(current.get(flag, False)))
            for flag, label in CANONICAL_REVIEW_FLAGS.items()
        }
        review_notes = st.text_area("Notas de revision", value=job.review_notes or "")
        approved_requested = st.checkbox(
            "Aprobar render canonico para exportacion",
            value=job.approved,
        )
        submitted = st.form_submit_button("Guardar revision")
    if not submitted:
        return

    missing = [label for flag, label in CANONICAL_REVIEW_FLAGS.items() if not flags[flag]]
    job.review_notes = review_notes
    metadata = _metadata(job.metadata_json)
    metadata["review_checklist"] = flags
    metadata["review_missing"] = missing
    job.metadata_json = json.dumps(metadata, ensure_ascii=False)
    job.approved = approved_requested and not missing and job.status == "rendered"
    job.reviewed_at = datetime.now(UTC) if job.approved else None
    session.commit()
    refresh_video_project_status(session, job.video_project_id)
    if job.approved:
        st.success("Render canonico aprobado. Ya puede exportarse.")
    elif missing:
        st.warning("Revision guardada, pero falta: " + ", ".join(missing))
    else:
        st.warning("Revision guardada sin aprobar el render.")
    st.rerun()


def _script_for_render_job(session, job: models.RenderJob) -> models.ScriptDraft | None:
    metadata = _metadata(job.metadata_json)
    script_id = metadata.get("script_draft_id")
    if isinstance(script_id, int):
        script = session.get(models.ScriptDraft, script_id)
        if script is not None:
            return script
    return session.scalar(
        select(models.ScriptDraft)
        .where(models.ScriptDraft.video_project_id == job.video_project_id)
        .order_by(models.ScriptDraft.created_at.desc())
    )


def _review_metadata(job: models.RenderJob) -> dict[str, Any]:
    metadata = _metadata(job.metadata_json)
    checklist = metadata.get("review_checklist")
    return checklist if isinstance(checklist, dict) else {}


def _metadata(raw: str | None) -> dict[str, Any]:
    try:
        value = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}
