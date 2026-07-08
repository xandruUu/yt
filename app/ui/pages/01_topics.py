from __future__ import annotations

import streamlit as st
from sqlalchemy import select

from app.core.enums import TopicCategory, TopicStatus
from app.db import models
from app.db.database import new_session
from app.db.repositories import create_topic
from app.i18n.es import CATEGORY_LABELS, LANGUAGE_LABELS_ES, STATUS_LABELS, label_for
from app.services.topic_service import build_topic_payload, describe_score


def render() -> None:
    st.title("Ideas")
    _create_topic_form()
    st.divider()
    _topic_table()


def _create_topic_form() -> None:
    st.subheader("Crear idea")
    with st.form("create_topic"):
        title = st.text_input("Título")
        summary = st.text_area("Resumen", height=120)
        col1, col2, col3 = st.columns(3)
        category = col1.selectbox(
            "Categoría",
            [item.value for item in TopicCategory],
            format_func=lambda value: label_for(CATEGORY_LABELS, value),
        )
        language_origin = col2.selectbox(
            "Idioma origen",
            ["en", "es", "hi_hinglish"],
            format_func=lambda value: label_for(LANGUAGE_LABELS_ES, value),
        )
        target_markets = col3.text_input("Mercados objetivo", value="global")
        source = st.text_input("Fuente")
        source_url = st.text_input("URL de la fuente")
        notes = st.text_area("Notas", height=80)

        st.caption("Puntuaciones manuales de 0 a 10")
        score_cols = st.columns(7)
        trend_score = score_cols[0].slider("Viralidad", 0.0, 10.0, 5.0, 0.5)
        rpm_score = score_cols[1].slider("RPM potencial", 0.0, 10.0, 5.0, 0.5)
        visual_score = score_cols[2].slider("Facilidad visual", 0.0, 10.0, 5.0, 0.5)
        evergreen_score = score_cols[3].slider("Evergreen", 0.0, 10.0, 5.0, 0.5)
        competition_score = score_cols[4].slider("Competencia", 0.0, 10.0, 5.0, 0.5)
        copyright_risk = score_cols[5].slider("Riesgo copyright", 0.0, 10.0, 2.0, 0.5)
        monetization_risk = score_cols[6].slider("Riesgo monetización", 0.0, 10.0, 2.0, 0.5)

        submitted = st.form_submit_button("Crear idea")
        if submitted:
            if not title.strip():
                st.error("El título es obligatorio.")
                return
            payload = build_topic_payload(
                title=title,
                summary=summary,
                category=category,
                source=source,
                source_url=source_url,
                language_origin=language_origin,
                target_markets=target_markets,
                trend_score=trend_score,
                rpm_score=rpm_score,
                visual_score=visual_score,
                evergreen_score=evergreen_score,
                competition_score=competition_score,
                copyright_risk=copyright_risk,
                monetization_risk=monetization_risk,
                notes=notes,
            )
            with new_session() as session:
                topic = create_topic(session, **payload)
            st.success(f"Idea #{topic.id} creada con score {topic.total_score:.1f}.")


def _topic_table() -> None:
    st.subheader("Ideas")
    with new_session() as session:
        topics = session.scalars(select(models.Topic).order_by(models.Topic.created_at.desc())).all()
        rows = [
            {
                "id": topic.id,
                "título": topic.title,
                "categoría": label_for(CATEGORY_LABELS, topic.category),
                "estado": label_for(STATUS_LABELS, topic.status),
                "score": topic.total_score,
                "lectura": describe_score(topic.total_score),
            }
            for topic in topics
        ]
    if rows:
        st.dataframe(rows, use_container_width=True, hide_index=True)
    else:
        st.info("Todavía no hay ideas.")

    st.subheader("Cambiar estado")
    with new_session() as session:
        topics = session.scalars(select(models.Topic).order_by(models.Topic.created_at.desc())).all()
        if not topics:
            return
        options = {f"#{topic.id} {topic.title}": topic.id for topic in topics}
        selected = st.selectbox("Idea", list(options))
        status = st.selectbox(
            "Estado",
            [item.value for item in TopicStatus],
            format_func=lambda value: label_for(STATUS_LABELS, value),
        )
        if st.button("Guardar estado"):
            topic = session.get(models.Topic, options[selected])
            if topic:
                topic.status = status
                session.commit()
                st.success("Estado actualizado.")
