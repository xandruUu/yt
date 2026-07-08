from __future__ import annotations

import streamlit as st
from sqlalchemy import select

from app.db import models
from app.db.database import new_session
from app.i18n.es import LANGUAGE_LABELS_ES, label_for
from app.services.localization_service import build_localization_prompt


def render() -> None:
    st.title("Localización")
    script = _select_script()
    if script is None:
        st.info("Crea un guion antes de preparar versiones localizadas.")
        return

    col1, col2 = st.columns(2)
    target_language = col1.selectbox(
        "Idioma destino",
        ["en", "es", "hi_hinglish"],
        format_func=lambda value: label_for(LANGUAGE_LABELS_ES, value),
    )
    target_market = col2.text_input("Mercado destino", value=script["target_market"])
    prompt = build_localization_prompt(
        source_language=script["language"],
        target_language=target_language,
        target_market=target_market,
        topic_title=script["topic_title"],
        script_text=script["script_text"],
    )
    st.text_area("Prompt de localización", prompt, height=320)
    if target_language == "hi_hinglish":
        st.warning("Hindi/Hinglish queda marcado para revisión nativa obligatoria.")


def _select_script() -> dict[str, object] | None:
    with new_session() as session:
        scripts = session.scalars(select(models.Script).order_by(models.Script.created_at.desc())).all()
        if not scripts:
            return None
        options = {f"#{script.id} {script.topic.title} [{script.language}]": script.id for script in scripts}
        selected = st.selectbox("Guion", list(options))
        script = session.get(models.Script, options[selected])
        return {
            "language": script.language,
            "target_market": script.topic.target_markets,
            "topic_title": script.topic.title,
            "script_text": script.script_text,
        }

