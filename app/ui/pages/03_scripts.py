from __future__ import annotations

import streamlit as st
from sqlalchemy import select

from app.core.enums import ScriptStatus
from app.db import models
from app.db.database import new_session
from app.db.repositories import create_script_with_lines
from app.i18n.es import LANGUAGE_LABELS_ES, STATUS_LABELS, label_for
from app.services.localization_service import build_localization_prompt
from app.services.script_service import build_script_prompt, parse_script_response


def render() -> None:
    st.title("Guiones")
    topic, hook = _select_topic_and_hook()
    if topic is None:
        st.info("Crea ideas y ganchos primero.")
        return

    st.subheader("Prompt para guion")
    language = st.selectbox(
        "Idioma",
        ["en", "es", "hi_hinglish"],
        format_func=lambda value: label_for(LANGUAGE_LABELS_ES, value),
    )
    market = st.text_input("Mercado", value=topic["target_markets"] or "global")
    duration = st.slider("Duración objetivo en segundos", 25, 60, 38)
    selected_hook = hook["text"] if hook else st.text_input("Texto del gancho elegido")
    prompt = build_script_prompt(
        topic_title=topic["title"],
        selected_hook=selected_hook,
        language=language,
        market=market,
        duration_seconds=duration,
    )
    st.text_area("Copia este prompt", prompt, height=320)

    st.subheader("Pegar guion")
    response = st.text_area("Guion JSON o texto línea por línea", height=260)
    if st.button("Parsear y guardar guion"):
        parsed = parse_script_response(response, language=language)
        if not parsed["lines"]:
            st.error("No se detectaron líneas de guion.")
        else:
            with new_session() as session:
                create_script_with_lines(
                    session,
                    {
                        "topic_id": topic["id"],
                        "hook_id": hook["id"] if hook else None,
                        "language": language,
                        "version": 1,
                        "script_text": parsed["script_text"],
                        "estimated_duration_seconds": sum(
                            float(line.get("duration_seconds", 2.5)) for line in parsed["lines"]
                        ),
                        "status": ScriptStatus.NEEDS_REVIEW.value,
                        "title_suggestion": parsed.get("title_suggestion"),
                        "description_suggestion": parsed.get("description_suggestion"),
                        "hashtags": " ".join(parsed.get("hashtags", [])),
                        "needs_native_review": parsed.get("needs_native_review", False),
                    },
                    parsed["lines"],
                )
            st.success("Guion guardado para revisión.")

    st.divider()
    _scripts_table(topic["id"])


def _select_topic_and_hook() -> tuple[dict[str, object] | None, dict[str, object] | None]:
    with new_session() as session:
        topics = session.scalars(select(models.Topic).order_by(models.Topic.created_at.desc())).all()
        if not topics:
            return None, None
        topic_options = {f"#{topic.id} {topic.title}": topic.id for topic in topics}
        selected_topic = st.selectbox("Idea", list(topic_options))
        topic = session.get(models.Topic, topic_options[selected_topic])
        hooks = session.scalars(
            select(models.Hook).where(models.Hook.topic_id == topic.id).order_by(models.Hook.selected.desc())
        ).all()
        hook = hooks[0] if hooks else None
        return (
            {"id": topic.id, "title": topic.title, "target_markets": topic.target_markets},
            {"id": hook.id, "text": hook.text} if hook else None,
        )


def _scripts_table(topic_id: int) -> None:
    with new_session() as session:
        scripts = session.scalars(
            select(models.Script).where(models.Script.topic_id == topic_id).order_by(models.Script.created_at.desc())
        ).all()
        if not scripts:
            st.info("Todavía no hay guiones para esta idea.")
            return
        st.subheader("Guiones guardados")
        st.dataframe(
            [
                {
                    "id": script.id,
                    "idioma": label_for(LANGUAGE_LABELS_ES, script.language),
                    "estado": label_for(STATUS_LABELS, script.status),
                    "duración": script.estimated_duration_seconds,
                    "necesita_fact_check": script.needs_fact_check,
                    "necesita_revisión_nativa": script.needs_native_review,
                }
                for script in scripts
            ],
            use_container_width=True,
            hide_index=True,
        )
        options = {f"#{script.id} {script.language} {script.status}": script.id for script in scripts}
        selected = st.selectbox("Guion", list(options))
        action = st.selectbox(
            "Cambiar estado",
            [item.value for item in ScriptStatus],
            format_func=lambda value: label_for(STATUS_LABELS, value),
        )
        if st.button("Guardar estado del guion"):
            script = session.get(models.Script, options[selected])
            if script:
                script.status = action
                session.commit()
                st.success("Estado del guion actualizado.")

        script = session.get(models.Script, options[selected])
        if script:
            st.subheader("Prompt de localización")
            target_language = st.selectbox(
                "Idioma destino",
                ["es", "en", "hi_hinglish"],
                format_func=lambda value: label_for(LANGUAGE_LABELS_ES, value),
            )
            target_market = st.text_input("Mercado destino", value="global")
            localization_prompt = build_localization_prompt(
                source_language=script.language,
                target_language=target_language,
                target_market=target_market,
                topic_title=script.topic.title,
                script_text=script.script_text,
            )
            st.text_area("Copia el prompt de localización", localization_prompt, height=260)
