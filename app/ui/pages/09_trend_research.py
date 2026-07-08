from __future__ import annotations

import streamlit as st
from sqlalchemy import select

from app.core.enums import GeneratedIdeaStatus
from app.db import models
from app.db.database import new_session
from app.i18n.es import CATEGORY_LABELS, LANGUAGE_LABELS_ES, MARKET_LABELS, label_for
from app.providers.base import TrendItem
from app.services.idea_generation_service import (
    convert_generated_idea_to_topic,
    generate_ideas_from_trends,
    persist_generated_ideas,
)
from app.services.trend_research_service import TrendResearchService
from app.ui.components.generated_idea_cards import generated_idea_card_data


def render() -> None:
    st.title("Investigador de tendencias")
    st.caption("Busca señales con modo manual, RSS, Hacker News y proveedores opcionales.")

    _research_panel()
    st.divider()
    _results_panel()
    st.divider()
    _generated_ideas_panel()
    st.divider()
    _providers_panel()


def _research_panel() -> None:
    col1, col2, col3, col4 = st.columns(4)
    language = col1.selectbox(
        "Idioma objetivo",
        ["en", "es", "hi_hinglish"],
        format_func=lambda value: label_for(LANGUAGE_LABELS_ES, value),
    )
    market = col2.selectbox(
        "Mercado",
        ["global", "us", "spain", "latam", "india"],
        format_func=lambda value: label_for(MARKET_LABELS, value),
    )
    category = col3.selectbox(
        "Categoría",
        list(CATEGORY_LABELS),
        format_func=lambda value: label_for(CATEGORY_LABELS, value),
    )
    limit = col4.number_input("Ideas", min_value=3, max_value=25, value=8)

    providers = st.multiselect(
        "Fuentes",
        ["manual", "rss", "hackernews", "youtube"],
        default=["manual"],
        format_func=_provider_label,
    )
    query = st.text_input("Query opcional")
    raw_input = st.text_area(
        "Pega URLs, titulares, temas o texto libre",
        height=180,
        placeholder="Una línea por señal de tendencia...",
    )
    if st.button("Investigar ideas", type="primary"):
        service = TrendResearchService()
        result = service.research(
            providers=providers,
            query=query or None,
            market=market,
            language=language,
            category=category,
            limit=int(limit),
            manual_input=raw_input,
        )
        st.session_state["trend_research_result"] = {
            "items": [item.model_dump(mode="json") for item in result.items],
            "warnings": result.warnings,
            "providers_used": result.providers_used,
        }
        st.success(f"Investigación completada: {len(result.items)} tendencias.")


def _results_panel() -> None:
    result = st.session_state.get("trend_research_result")
    if not result:
        st.info("Todavía no hay tendencias investigadas en esta sesión.")
        return
    warnings = result.get("warnings", [])
    for warning in warnings:
        st.warning(warning)
    items = [TrendItem(**item) for item in result.get("items", [])]
    if not items:
        st.warning("No se encontraron tendencias.")
        return
    st.subheader("Tendencias detectadas")
    st.dataframe(_rows(items), use_container_width=True, hide_index=True)
    selected_titles = st.multiselect(
        "Tendencias para generar ideas",
        [item.title for item in items],
        default=[items[0].title] if items else [],
    )
    selected_items = [item for item in items if item.title in selected_titles]
    ideas_per_trend = st.slider("Ideas por tendencia", min_value=1, max_value=5, value=3)
    if st.button("Generar ideas desde tendencias seleccionadas", type="primary"):
        if not selected_items:
            st.error("Selecciona al menos una tendencia.")
            return
        first = selected_items[0]
        ideas = generate_ideas_from_trends(
            selected_items,
            target_language=first.language or "es",
            target_market=first.market or "global",
            category=first.category or "other",
            ideas_per_trend=ideas_per_trend,
        )
        with new_session() as session:
            saved = persist_generated_ideas(session, ideas)
        st.success(f"Se generaron {len(saved)} ideas originales.")

    with st.expander("Ver detalle de tendencias"):
        selected = st.selectbox("Detalle", [item.title for item in items])
        item = next(item for item in items if item.title == selected)
        st.json(item.model_dump(mode="json"), expanded=False)


def _generated_ideas_panel() -> None:
    with new_session() as session:
        ideas = session.scalars(
            select(models.GeneratedIdea).order_by(
                models.GeneratedIdea.total_score.desc(),
                models.GeneratedIdea.created_at.desc(),
            )
        ).all()
        if not ideas:
            st.info("Todavía no hay ideas generadas.")
            return
        st.subheader("Ideas originales generadas")
        for idea in ideas:
            _render_generated_idea_card(session, idea, key_prefix="research")


def _render_generated_idea_card(session, idea: models.GeneratedIdea, key_prefix: str) -> None:
    data = generated_idea_card_data(idea)
    edit_key = f"{key_prefix}_editing_{idea.id}"
    with st.container(border=True):
        st.markdown(f"**{data['titulo']}**")
        st.caption(f"{data['estado']} | Score {data['score']} ({data['score_badge']})")
        st.write(idea.summary)
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Viralidad", idea.viral_score)
        col2.metric("RPM", idea.rpm_score)
        col3.metric("Evergreen", idea.evergreen_score)
        col4.metric("Riesgo copyright", idea.copyright_risk)
        col5.metric("Riesgo monetización", idea.monetization_risk)
        with st.expander("Detalles"):
            st.write(f"Ángulo: {idea.angle}")
            st.write(f"Por qué puede funcionar: {idea.why_it_can_work}")
            st.write(f"Duración sugerida: {idea.suggested_duration}")
            st.write(f"Formato: {idea.suggested_format}")
            st.write(f"Hook sugerido: {idea.suggested_hook_type}")
            st.write(f"Visual sugerido: {idea.suggested_visual}")
            st.write(f"PÃºblico objetivo: {idea.target_audience or 'No definido'}")
            st.write(f"Fuentes: {idea.sources_json or '[]'}")
        actions = st.columns(5)
        select_clicked = actions[0].button("Elegir idea", key=f"{key_prefix}_select_{idea.id}")
        if select_clicked and idea.status == GeneratedIdeaStatus.DISCARDED.value:
            st.error("No puedes elegir una idea descartada.")
        elif select_clicked:
            idea.status = GeneratedIdeaStatus.SELECTED.value
            session.commit()
            st.session_state["wizard_selected_generated_idea_id"] = idea.id
            st.success("Idea elegida.")
            st.rerun()
        if actions[1].button("Guardar para después", key=f"{key_prefix}_save_{idea.id}"):
            idea.status = GeneratedIdeaStatus.SAVED_FOR_LATER.value
            session.commit()
            st.rerun()
        if actions[2].button("Descartar", key=f"{key_prefix}_discard_{idea.id}"):
            idea.status = GeneratedIdeaStatus.DISCARDED.value
            session.commit()
            st.rerun()
        if actions[3].button("Convertir en idea principal", key=f"{key_prefix}_topic_{idea.id}"):
            topic = convert_generated_idea_to_topic(session, idea)
            st.session_state["wizard_selected_topic_id"] = topic.id
            st.success(f"Convertida en idea principal #{topic.id}.")
            st.rerun()
        if actions[4].button("Editar", key=f"{key_prefix}_edit_{idea.id}"):
            st.session_state[edit_key] = not st.session_state.get(edit_key, False)
            st.rerun()
        if st.session_state.get(edit_key, False):
            _render_generated_idea_edit_form(session, idea, key_prefix)


def _render_generated_idea_edit_form(session, idea: models.GeneratedIdea, key_prefix: str) -> None:
    with st.form(f"{key_prefix}_edit_form_{idea.id}"):
        title = st.text_input("TÃ­tulo", value=idea.title)
        angle = st.text_area("Ãngulo", value=idea.angle)
        summary = st.text_area("Resumen", value=idea.summary)
        why_it_can_work = st.text_area("Por quÃ© puede funcionar", value=idea.why_it_can_work)
        submitted = st.form_submit_button("Guardar cambios")
        if submitted:
            if not title.strip():
                st.error("La idea necesita un tÃ­tulo.")
                return
            idea.title = title.strip()
            idea.angle = angle.strip()
            idea.summary = summary.strip()
            idea.why_it_can_work = why_it_can_work.strip()
            session.commit()
            st.success("Idea actualizada.")
            st.rerun()


def _providers_panel() -> None:
    rows = [
        {"proveedor": "YouTube Data API", "estado": "Opcional", "notas": "Requiere API key gratuita."},
        {"proveedor": "RSS", "estado": "Siguiente iteración", "notas": "Feeds públicos configurables."},
        {"proveedor": "Hacker News", "estado": "Siguiente iteración", "notas": "API pública gratuita."},
        {"proveedor": "Google Trends", "estado": "Opcional", "notas": "pytrends no oficial, puede fallar."},
        {"proveedor": "Reddit API", "estado": "Opcional", "notas": "Solo API oficial, sin copiar posts."},
        {"proveedor": "Manual", "estado": "Disponible", "notas": "Fallback sin API keys."},
    ]
    st.dataframe(rows, use_container_width=True, hide_index=True)


def _rows(items: list[TrendItem]) -> list[dict[str, object]]:
    return [
        {
            "título": item.title,
            "fuente": item.source,
            "categoría": label_for(CATEGORY_LABELS, item.category),
            "idioma": label_for(LANGUAGE_LABELS_ES, item.language),
            "mercado": label_for(MARKET_LABELS, item.market),
            "url": item.source_url,
            "señales": item.popularity_signals,
        }
        for item in items
    ]


def _provider_label(provider: str) -> str:
    return {
        "manual": "Manual",
        "rss": "RSS",
        "hackernews": "Hacker News",
        "youtube": "YouTube Data API",
    }.get(provider, provider)
