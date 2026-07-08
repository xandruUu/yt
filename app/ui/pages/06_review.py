from __future__ import annotations

from datetime import UTC, datetime

import streamlit as st
from sqlalchemy import select

from app.core.validation import REQUIRED_REVIEW_FLAGS
from app.db import models
from app.db.database import new_session
from app.db.repositories import create_or_update_checklist
from app.i18n.es import REVIEW_LABELS
from app.services.review_service import build_review_payload, checklist_missing_items


def render() -> None:
    st.title("Revisión")
    render_row = _select_render()
    if render_row is None:
        st.info("Crea un render primero.")
        return

    if render_row["video_path"]:
        st.video(render_row["video_path"])
    st.subheader("Guion")
    st.text_area("Texto del guion", render_row["script_text"], height=220, disabled=True)

    st.subheader("Checklist obligatoria")
    with st.form("review_checklist"):
        flags = {flag: st.checkbox(REVIEW_LABELS[flag]) for flag in REQUIRED_REVIEW_FLAGS}
        review_notes = st.text_area("Notas de revisión")
        approved_requested = st.checkbox("Aprobar vídeo para exportación")
        if st.form_submit_button("Guardar revisión"):
            payload = build_review_payload(**flags, review_notes=review_notes, approved=approved_requested)
            missing = checklist_missing_items(payload)
            with new_session() as session:
                create_or_update_checklist(
                    session,
                    render_id=render_row["id"],
                    **{
                        key: value
                        for key, value in payload.items()
                        if key != "reviewed_at"
                    },
                    reviewed_at=datetime.now(UTC) if payload["approved"] else None,
                )
                db_render = session.get(models.Render, render_row["id"])
                if db_render and payload["approved"]:
                    db_render.status = "approved"
                    session.commit()
            if payload["approved"]:
                st.success("Revisión aprobada. La exportación ya está disponible.")
            else:
                st.warning("Revisión guardada, pero la exportación queda bloqueada hasta completar todo.")
                if missing:
                    st.caption("Falta: " + ", ".join(missing))


def _select_render() -> dict[str, object] | None:
    with new_session() as session:
        renders = session.scalars(
            select(models.Render)
            .where(models.Render.status.in_(["rendered", "approved", "rejected"]))
            .order_by(models.Render.created_at.desc())
        ).all()
        if not renders:
            return None
        options = {f"#{item.id} guion #{item.script_id} [{item.status}]": item.id for item in renders}
        selected = st.selectbox("Render", list(options))
        item = session.get(models.Render, options[selected])
        return {
            "id": item.id,
            "video_path": item.video_path,
            "script_text": item.script.script_text,
        }
