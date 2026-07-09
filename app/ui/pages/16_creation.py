from __future__ import annotations

import json

import streamlit as st
from sqlalchemy import select

from app.db import models
from app.db.database import new_session
from app.services.pipeline_service import (
    pending_creation_inbox,
    run_deep_research,
    send_deep_idea_to_ideas,
)


def render() -> None:
    st.title("Creacion")
    st.caption("Profundiza ideas recibidas desde Investigacion y envia una subidea a Ideas.")
    with new_session() as session:
        _inbox_panel(session)
        st.divider()
        _deep_ideas_panel(session)


def _inbox_panel(session) -> None:
    st.subheader("Ideas recibidas desde Investigacion")
    inbox_items = pending_creation_inbox(session)
    if not inbox_items:
        st.info("No hay ideas pendientes. Envia una desde Investigacion.")
        return
    for inbox in inbox_items:
        idea = session.get(models.IdeaCandidate, inbox.idea_candidate_id)
        if idea is None:
            continue
        with st.container(border=True):
            st.markdown(f"**{idea.title}**")
            st.write(idea.short_description)
            st.caption(f"Viral angle: {idea.viral_angle}")
            count = st.slider("Subideas", min_value=2, max_value=6, value=4, key=f"deep_count_{idea.id}")
            if st.button("Investigar mas esta idea", key=f"deep_research_{idea.id}", type="primary"):
                run, deep_ideas = run_deep_research(session, idea_candidate_id=idea.id, count=int(count))
                inbox.status = "processed"
                session.commit()
                st.success(f"Deep research #{run.id} creado con {len(deep_ideas)} subideas.")
                st.rerun()


def _deep_ideas_panel(session) -> None:
    st.subheader("Subideas generadas")
    deep_ideas = list(
        session.scalars(
            select(models.DeepIdeaCandidate).order_by(models.DeepIdeaCandidate.created_at.desc()).limit(50)
        ).all()
    )
    if not deep_ideas:
        st.info("Todavia no hay subideas.")
        return
    for idea in deep_ideas:
        with st.container(border=True):
            st.markdown(f"**{idea.title}**")
            st.caption(f"Estado: {idea.status} | Riesgo: {idea.risk_level}")
            st.write(idea.detailed_description)
            st.write(f"**Specific angle:** {idea.specific_angle}")
            st.write(f"**Possible hook:** {idea.possible_hook}")
            with st.expander("Ver verificaciones y visuales"):
                st.json(
                    {
                        "facts_to_verify": _json_loads(idea.facts_to_verify_json),
                        "visual_opportunities": _json_loads(idea.visual_opportunities_json),
                        "risk_notes": idea.risk_notes,
                    }
                )
            disabled = idea.status == "selected"
            if st.button("Enviar a Ideas", key=f"send_deep_{idea.id}", disabled=disabled):
                recipe = send_deep_idea_to_ideas(session, idea.id)
                st.success(f"Receta de metadata #{recipe.id} creada.")
                st.rerun()


def _json_loads(value: str | None):
    try:
        return json.loads(value or "[]")
    except json.JSONDecodeError:
        return []

