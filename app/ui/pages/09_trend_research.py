from __future__ import annotations

import json

import streamlit as st
from sqlalchemy import select

from app.db import models
from app.db.database import new_session
from app.services.pipeline_service import run_general_research, send_idea_to_creation


def render() -> None:
    st.title("Investigacion")
    st.caption("Busca viralidad general sin selector de categoria. La UI esta en espanol; las ideas salen en ingles.")
    _research_panel()
    st.divider()
    _latest_research_panel()


def _research_panel() -> None:
    with st.form("general_research_form"):
        idea_count = st.slider("Cantidad de ideas a generar", min_value=1, max_value=15, value=5)
        with st.expander("Opciones avanzadas", expanded=False):
            col1, col2 = st.columns(2)
            market = col1.selectbox("Mercado", ["global", "us", "uk", "es"], index=0)
            lookback = col2.selectbox("Lookback", [7, 14, 30], index=2, format_func=lambda value: f"Ultimos {value} dias")
            include_youtube = st.checkbox("Incluir YouTube si hay credenciales", value=False)
            include_rss = st.checkbox("Incluir RSS/noticias", value=True)
            include_hackernews = st.checkbox("Incluir Hacker News", value=True)
            manual_input = st.text_area(
                "Senales manuales opcionales",
                height=120,
                placeholder="Pega titulares, URLs o temas. Si lo dejas vacio uso senales semilla.",
            )
        submitted = st.form_submit_button("Investigar viralidad general", type="primary")
        if submitted:
            with new_session() as session:
                result = run_general_research(
                    session,
                    idea_count=int(idea_count),
                    market=market,
                    lookback_days=int(lookback),
                    include_youtube=include_youtube,
                    include_rss=include_rss,
                    include_hackernews=include_hackernews,
                    manual_input=manual_input,
                )
                st.session_state["latest_research_run_id"] = result.research_run.id
                st.success(f"Investigacion completada: {len(result.ideas)} ideas nuevas.")
                for warning in result.warnings:
                    st.warning(warning)


def _latest_research_panel() -> None:
    with new_session() as session:
        runs = list(
            session.scalars(select(models.ResearchRun).order_by(models.ResearchRun.created_at.desc()).limit(10)).all()
        )
        if not runs:
            st.info("Todavia no hay investigaciones guardadas.")
            return
        selected_run_id = st.selectbox(
            "Investigaciones recientes",
            [run.id for run in runs],
            format_func=lambda run_id: _run_label(next(run for run in runs if run.id == run_id)),
        )
        run = session.get(models.ResearchRun, int(selected_run_id))
        if run is None:
            return
        _run_metrics(run)
        ideas = list(
            session.scalars(
                select(models.IdeaCandidate)
                .where(models.IdeaCandidate.research_run_id == run.id)
                .order_by(models.IdeaCandidate.created_at.desc())
            ).all()
        )
        if not ideas:
            st.warning("Esta investigacion no tiene ideas.")
            return
        st.subheader("Ideas candidatas")
        for idea in ideas:
            _idea_card(session, idea)


def _run_metrics(run: models.ResearchRun) -> None:
    summary = _json_loads(run.provider_summary_json)
    cols = st.columns(4)
    cols[0].metric("Ideas pedidas", run.idea_count_requested)
    cols[1].metric("Lookback", f"{run.lookback_days} dias")
    cols[2].metric("Mercado", run.target_market)
    cols[3].metric("Estado", run.status)
    with st.expander("Resumen tecnico", expanded=False):
        st.json(summary)


def _idea_card(session, idea: models.IdeaCandidate) -> None:
    with st.container(border=True):
        st.markdown(f"**{idea.title}**")
        st.caption(f"Estado: {idea.status} | Riesgo: {idea.risk_level} | {idea.estimated_duration_seconds}s")
        st.write(idea.short_description)
        st.write(f"**Viral angle:** {idea.viral_angle}")
        st.write(f"**Why now:** {idea.why_now}")
        st.write(f"**Visual potential:** {idea.visual_potential}")
        with st.expander("Fuentes y riesgo"):
            st.json(
                {
                    "source_item_ids": _json_loads(idea.source_item_ids_json),
                    "risk_notes": idea.risk_notes,
                }
            )
        disabled = idea.status == "sent_to_creation"
        if st.button("Enviar a Creacion", key=f"send_idea_{idea.id}", disabled=disabled):
            send_idea_to_creation(session, idea.id)
            st.success("Idea enviada a Creacion.")
            st.rerun()


def _run_label(run: models.ResearchRun) -> str:
    return f"#{run.id} | {run.status} | {run.idea_count_requested} ideas | {run.created_at:%Y-%m-%d %H:%M}"


def _json_loads(value: str | None):
    try:
        return json.loads(value or "{}")
    except json.JSONDecodeError:
        return {}
