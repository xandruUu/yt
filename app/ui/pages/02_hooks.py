from __future__ import annotations

import json

import streamlit as st
from sqlalchemy import select

from app.core.enums import HookType
from app.db import models
from app.db.database import new_session
from app.db.repositories import create_hook, set_selected_hook
from app.i18n.es import LANGUAGE_LABELS_ES, label_for
from app.services.hook_generation_service import generate_hooks_for_topic
from app.services.hook_service import build_hooks_prompt, parse_hooks_response


def render() -> None:
    st.title("Ganchos")
    topic = _select_topic()
    if topic is None:
        st.info("Crea una idea primero.")
        return

    st.subheader("Prompt para ganchos")
    language = st.selectbox(
        "Idioma",
        ["en", "es", "hi_hinglish"],
        index=0,
        format_func=lambda value: label_for(LANGUAGE_LABELS_ES, value),
    )
    market = st.text_input("Mercado", value=topic["target_markets"] or "global")
    number_of_hooks = st.slider("Número de ganchos", 3, 15, 8)
    _auto_hooks_panel(topic, language, market)
    prompt = build_hooks_prompt(
        topic_title=topic["title"],
        topic_summary=topic["summary"],
        language=language,
        market=market,
        number_of_hooks=number_of_hooks,
    )
    st.text_area("Copia este prompt", prompt, height=320)

    st.subheader("Pegar respuesta de IA")
    response = st.text_area("Respuesta con ganchos", height=180)
    if st.button("Parsear y guardar ganchos"):
        hooks = parse_hooks_response(response, default_language=language)
        if not hooks:
            st.error("No se detectaron ganchos.")
        else:
            with new_session() as session:
                for hook in hooks:
                    create_hook(session, topic_id=topic["id"], **hook)
            st.success(f"Se guardaron {len(hooks)} ganchos.")

    st.subheader("Gancho manual")
    with st.form("manual_hook"):
        text = st.text_input("Texto del gancho")
        hook_type = st.selectbox("Tipo de gancho", [item.value for item in HookType])
        scores = st.columns(4)
        clarity = scores[0].slider("Claridad", 0.0, 10.0, 5.0)
        curiosity = scores[1].slider("Curiosidad", 0.0, 10.0, 5.0)
        emotion = scores[2].slider("Emoción", 0.0, 10.0, 5.0)
        risk = scores[3].slider("Riesgo", 0.0, 10.0, 1.0)
        notes = st.text_area("Notas")
        if st.form_submit_button("Guardar gancho"):
            with new_session() as session:
                create_hook(
                    session,
                    topic_id=topic["id"],
                    language=language,
                    text=text,
                    hook_type=hook_type,
                    clarity_score=clarity,
                    curiosity_score=curiosity,
                    emotion_score=emotion,
                    risk_score=risk,
                    notes=notes,
                )
            st.success("Gancho guardado.")

    _hooks_for_topic(topic["id"])


def _auto_hooks_panel(topic: dict[str, object], language: str, market: str) -> None:
    st.subheader("Generacion automatica supervisada")
    col1, col2 = st.columns(2)
    provider_name = col1.selectbox(
        "Provider IA",
        ["manual", "ollama", "openai"],
        index=0,
        format_func=lambda value: {
            "manual": "Manual/gratis",
            "ollama": "Ollama local",
            "openai": "OpenAI opcional",
        }.get(value, value),
        key="hooks_provider",
    )
    style = col2.selectbox(
        "Modo",
        ["balanced", "safer", "shorter", "documentary", "aggressive"],
        index=0,
        format_func=lambda value: {
            "balanced": "Equilibrado",
            "safer": "Mas seguros",
            "shorter": "Mas cortos",
            "documentary": "Mas documentales",
            "aggressive": "Mas agresivos",
        }.get(value, value),
        key="hooks_style",
    )
    if provider_name == "openai":
        st.warning("OpenAI puede generar coste si ENABLE_OPENAI_LLM=true y hay API key.")
    if st.button("Generar 25 hooks automaticamente", type="primary", key="hooks_generate_auto"):
        with new_session() as session:
            topic_model = session.get(models.Topic, int(topic["id"]))
            if topic_model is None:
                st.error("No se encontro la idea seleccionada.")
                return
            result = generate_hooks_for_topic(
                session,
                topic_model,
                language=language,
                market=market,
                provider_name=provider_name,
                style=style,
                save=True,
            )
        for warning in result.warnings:
            st.warning(warning)
        with st.expander("Prompt manual opcional"):
            st.text_area("Prompt", result.prompt, height=260, key="hooks_prompt_auto")
        st.success(f"Se generaron {len(result.saved_hook_ids)} hooks.")


def _select_topic() -> dict[str, object] | None:
    with new_session() as session:
        topics = session.scalars(select(models.Topic).order_by(models.Topic.created_at.desc())).all()
        if not topics:
            return None
        options = {f"#{topic.id} {topic.title}": topic.id for topic in topics}
        selected = st.selectbox("Idea", list(options))
        topic = session.get(models.Topic, options[selected])
        return {
            "id": topic.id,
            "title": topic.title,
            "summary": topic.summary,
            "target_markets": topic.target_markets,
        }


def _hooks_for_topic(topic_id: int) -> None:
    with new_session() as session:
        hooks = session.scalars(
            select(models.Hook).where(models.Hook.topic_id == topic_id).order_by(models.Hook.created_at.desc())
        ).all()
        if not hooks:
            st.info("Todavía no hay ganchos para esta idea.")
            return
        st.subheader("Ganchos guardados")
        st.dataframe(
            [
                {
                    "id": hook.id,
                    "texto": hook.text,
                    "tipo": hook.hook_type,
                    "idioma": label_for(LANGUAGE_LABELS_ES, hook.language),
                    "elegido": hook.selected,
                    "score": _hook_total_score(hook.notes),
                    "riesgo": hook.risk_score,
                }
                for hook in hooks
            ],
            use_container_width=True,
            hide_index=True,
        )
        options = {f"#{hook.id} {hook.text[:80]}": hook.id for hook in hooks}
        selected = st.selectbox("Gancho ganador", list(options))
        if st.button("Usar este gancho"):
            hook = session.get(models.Hook, options[selected])
            if hook:
                set_selected_hook(session, hook)
                st.success("Gancho elegido.")


def _hook_total_score(notes: str | None) -> int | str:
    if not notes:
        return "-"
    try:
        payload = json.loads(notes)
    except json.JSONDecodeError:
        return "-"
    if not isinstance(payload, dict):
        return "-"
    return int(payload.get("total_score", 0) or 0)
