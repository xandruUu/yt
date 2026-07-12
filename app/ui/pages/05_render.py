from __future__ import annotations

import streamlit as st
from sqlalchemy import func, select

from app.config.settings import get_settings
from app.core.enums import RenderStatus, ScriptStatus
from app.db import models
from app.db.database import new_session
from app.db.repositories import create_render
from app.i18n.es import LANGUAGE_LABELS_ES, STATUS_LABELS, label_for
from app.render.templates import TEMPLATES
from app.services.render_service import render_script_preview


def render() -> None:
    st.title("Renderizar")
    script = _select_approved_script()
    if script is None:
        st.info("Aprueba un guion antes de renderizar.")
        return

    settings = get_settings()
    _render_canonical_clip_guard()
    template_name = st.selectbox("Plantilla", list(TEMPLATES))
    channel_id = _select_channel()
    st.subheader("Estructura previa")
    st.dataframe(
        [
            {
                "texto": line["text"],
                "visual_sugerido": line.get("visual_suggestion"),
                "duración_segundos": line.get("duration_seconds"),
                "subtítulo": line.get("subtitle_text"),
            }
            for line in script["lines"]
        ],
        use_container_width=True,
        hide_index=True,
    )

    if st.button("Renderizar vídeo vertical", type="primary"):
        result = render_script_preview(
            output_dir=settings.output_dir,
            topic_title=script["topic_title"],
            script_lines=script["lines"],
            template_name=template_name,
            overwrite=True,
        )
        with new_session() as session:
            render_row = create_render(
                session,
                script_id=script["id"],
                channel_id=channel_id,
                language=script["language"],
                template_name=template_name,
                video_path=result.output_path,
                duration_seconds=script["duration"],
                resolution=f"{settings.default_video_width}x{settings.default_video_height}",
                status=RenderStatus.RENDERED.value if result.ok else RenderStatus.FAILED.value,
                error_message=result.error_message,
            )
        if result.ok:
            st.success(f"Render #{render_row.id} creado.")
            st.video(result.output_path)
        else:
            st.error(result.error_message)

    _render_table()


def _select_approved_script() -> dict[str, object] | None:
    with new_session() as session:
        scripts = session.scalars(
            select(models.Script)
            .where(models.Script.status == ScriptStatus.APPROVED.value)
            .order_by(models.Script.created_at.desc())
        ).all()
        if not scripts:
            return None
        options = {
            f"#{script.id} {script.topic.title} [{script.language}]": script.id
            for script in scripts
        }
        selected = st.selectbox("Guion aprobado", list(options))
        script = session.get(models.Script, options[selected])
        return {
            "id": script.id,
            "language": script.language,
            "topic_title": script.topic.title,
            "duration": script.estimated_duration_seconds,
            "lines": [
                {
                    "text": line.text,
                    "visual_suggestion": line.visual_suggestion,
                    "duration_seconds": line.duration_seconds,
                    "subtitle_text": line.subtitle_text or line.text,
                }
                for line in script.lines
            ],
        }


def _select_channel() -> int | None:
    with new_session() as session:
        channels = session.scalars(select(models.Channel).order_by(models.Channel.name)).all()
        if not channels:
            return None
        options = {f"{channel.name} [{channel.language}]": channel.id for channel in channels}
        selected = st.selectbox("Canal", list(options))
        return options[selected]


def _render_table() -> None:
    st.subheader("Renders")
    with new_session() as session:
        renders = session.scalars(
            select(models.Render).order_by(models.Render.created_at.desc())
        ).all()
        rows = [
            {
                "id": item.id,
                "guion_id": item.script_id,
                "idioma": label_for(LANGUAGE_LABELS_ES, item.language),
                "plantilla": item.template_name,
                "estado": label_for(STATUS_LABELS, item.status),
                "video": item.video_path,
                "error": item.error_message,
            }
            for item in renders
        ]
    if rows:
        st.dataframe(rows, use_container_width=True, hide_index=True)


def _render_canonical_clip_guard() -> None:
    with new_session() as session:
        project = session.scalar(
            select(models.VideoProject).order_by(models.VideoProject.created_at.desc())
        )
        if project is None:
            st.warning(
                "Este render pertenece al flujo legacy y puede usar visuales fallback/placeholder. "
                "No debe considerarse render final de produccion sin clips reales mapeados."
            )
            return

        selected_scene_ids = list(
            session.scalars(
                select(models.SelectedScene.id)
                .where(models.SelectedScene.video_project_id == project.id)
                .order_by(models.SelectedScene.sort_order)
            ).all()
        )
        if not selected_scene_ids:
            st.warning(
                f"Proyecto canonico #{project.id}: no hay escenas seleccionadas. "
                "El render actual usara fallback/placeholder si continuas."
            )
            return

        mapped_count = (
            session.scalar(
                select(func.count(func.distinct(models.GeneratedClip.selected_scene_id))).where(
                    models.GeneratedClip.selected_scene_id.in_(selected_scene_ids),
                    models.GeneratedClip.status != "discarded",
                )
            )
            or 0
        )
        missing_count = max(0, len(selected_scene_ids) - int(mapped_count))
        if missing_count:
            st.warning(
                f"Proyecto canonico #{project.id}: faltan clips reales en "
                f"{missing_count}/{len(selected_scene_ids)} escenas. "
                "El render usara fallback/placeholder y no es final."
            )
            return

        st.success(f"Proyecto canonico #{project.id}: todas las escenas tienen clips registrados.")
