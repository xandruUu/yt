from __future__ import annotations

import importlib
from dataclasses import dataclass

try:
    import streamlit as st
    from sqlalchemy import func, select
except ImportError as exc:  # pragma: no cover - visible only without UI deps.
    raise RuntimeError(
        "Streamlit and SQLAlchemy are required. Install dependencies with: "
        "python -m pip install -r requirements.txt"
    ) from exc

from app.db import models
from app.db.database import init_db, new_session
from app.db.seed import seed_defaults
from app.i18n.es import (
    APP_NAME,
    CATEGORY_LABELS,
    LANGUAGE_LABELS_ES,
    MARKET_LABELS,
    NAVIGATION,
    STATUS_LABELS,
    label_for,
)


@dataclass(frozen=True)
class Page:
    label: str
    module: str


PAGES = (
    *(Page(label, module) for label, module in NAVIGATION),
)


def render_dashboard() -> None:
    st.set_page_config(page_title=APP_NAME, page_icon="SF", layout="wide")
    init_db()
    with new_session() as session:
        seed_defaults(session)

    st.sidebar.title(APP_NAME)
    st.sidebar.caption("Asistente de producción de Shorts")
    selected_label = st.sidebar.radio(
        "Navegación",
        [page.label for page in PAGES],
        label_visibility="collapsed",
    )
    selected_page = next(page for page in PAGES if page.label == selected_label)

    if selected_page.module == "home":
        render_home()
        return

    module = importlib.import_module(f"app.ui.pages.{selected_page.module}")
    module.render()


def render_home() -> None:
    st.title("Inicio")
    st.caption("Vista rápida del estado de producción y accesos para crear Shorts paso a paso.")
    filters = _render_filters()
    metrics = _load_metrics(filters)

    columns = st.columns(7)
    columns[0].metric("Ideas", metrics["topics"])
    columns[1].metric("Ganchos", metrics["hooks"])
    columns[2].metric("Guiones", metrics["scripts"])
    columns[3].metric("Renders", metrics["renders"])
    columns[4].metric("Pendientes de revisión", metrics["review_pending"])
    columns[5].metric("Aprobados", metrics["approved"])
    columns[6].metric("Exportados", metrics["exported"])

    st.subheader("Atajos")
    quick_cols = st.columns(3)
    quick_cols[0].info("Usa Crear Short paso a paso para seguir la receta completa.")
    quick_cols[1].info("Usa Investigador de tendencias para preparar ideas nuevas.")
    quick_cols[2].info("Usa Revisión antes de exportar cualquier vídeo.")

    st.subheader("Tablero de ideas")
    rows = _load_topic_rows(filters)
    if not rows:
        st.info("Crea la primera idea desde Ideas o desde el flujo guiado.")
        return

    statuses = sorted({row["status"] for row in rows})
    board_columns = st.columns(max(1, len(statuses)))
    for column, status in zip(board_columns, statuses, strict=False):
        with column:
            st.markdown(f"**{label_for(STATUS_LABELS, status)}**")
            for row in [item for item in rows if item["status"] == status]:
                st.caption(f"{row['título']} | score {row['score_total']:.1f}")

    st.dataframe(rows, use_container_width=True, hide_index=True)


def _render_filters() -> dict[str, str]:
    with st.expander("Filtros", expanded=False):
        col1, col2, col3 = st.columns(3)
        language_options = ["all", "en", "es", "hi_hinglish"]
        language = col1.selectbox(
            "Idioma",
            language_options,
            format_func=lambda value: "Todos" if value == "all" else label_for(LANGUAGE_LABELS_ES, value),
        )
        category_options = [
            "all",
            "ai_tools",
            "tech_explained",
            "science_explained",
            "business_case",
            "internet_culture_explained",
            "engineering",
            "psychology",
            "productivity",
            "finance_educational",
            "history_explained",
            "mystery_explained",
            "other",
        ]
        category = col2.selectbox(
            "Categoría",
            category_options,
            format_func=lambda value: "Todas" if value == "all" else label_for(CATEGORY_LABELS, value),
        )
        status_options = ["all", "idea", "approved_for_hooks", "rejected", "archived"]
        status = col3.selectbox(
            "Estado",
            status_options,
            format_func=lambda value: "Todos" if value == "all" else label_for(STATUS_LABELS, value),
        )
    return {"language": language, "category": category, "status": status}


def _load_metrics(filters: dict[str, str]) -> dict[str, int]:
    with new_session() as session:
        topic_query = select(func.count(models.Topic.id))
        if filters["language"] != "all":
            topic_query = topic_query.where(models.Topic.language_origin == filters["language"])
        if filters["category"] != "all":
            topic_query = topic_query.where(models.Topic.category == filters["category"])
        if filters["status"] != "all":
            topic_query = topic_query.where(models.Topic.status == filters["status"])

        return {
            "topics": session.scalar(topic_query) or 0,
            "hooks": session.scalar(select(func.count(models.Hook.id))) or 0,
            "scripts": session.scalar(select(func.count(models.Script.id))) or 0,
            "renders": session.scalar(select(func.count(models.Render.id))) or 0,
            "review_pending": session.scalar(
                select(func.count(models.Render.id)).where(models.Render.status == "rendered")
            )
            or 0,
            "approved": session.scalar(
                select(func.count(models.Render.id)).where(models.Render.status == "approved")
            )
            or 0,
            "exported": session.scalar(
                select(func.count(models.Render.id)).where(models.Render.status == "exported")
            )
            or 0,
        }


def _load_topic_rows(filters: dict[str, str]) -> list[dict[str, object]]:
    with new_session() as session:
        query = select(models.Topic).order_by(models.Topic.created_at.desc())
        if filters["language"] != "all":
            query = query.where(models.Topic.language_origin == filters["language"])
        if filters["category"] != "all":
            query = query.where(models.Topic.category == filters["category"])
        if filters["status"] != "all":
            query = query.where(models.Topic.status == filters["status"])
        topics = session.scalars(query).all()
        return [
            {
                "id": topic.id,
                "título": topic.title,
                "categoría": label_for(CATEGORY_LABELS, topic.category),
                "idioma": label_for(LANGUAGE_LABELS_ES, topic.language_origin),
                "mercado": label_for(MARKET_LABELS, topic.target_markets),
                "estado": label_for(STATUS_LABELS, topic.status),
                "status": topic.status,
                "score_total": topic.total_score,
            }
            for topic in topics
        ]
