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

from app.config.settings import get_settings
from app.db import models
from app.db.database import init_db, new_session
from app.db.seed import seed_defaults
from app.i18n.es import (
    APP_NAME,
    CANONICAL_NAVIGATION,
    LEGACY_NAVIGATION,
    STATUS_LABELS,
    label_for,
)


@dataclass(frozen=True)
class Page:
    label: str
    module: str


MAIN_PAGES = tuple(Page(label, module) for label, module in CANONICAL_NAVIGATION)
LEGACY_PAGES = tuple(Page(label, module) for label, module in LEGACY_NAVIGATION)
PAGES = MAIN_PAGES


def build_pages(show_legacy_modules: bool | None = None) -> tuple[Page, ...]:
    if show_legacy_modules is None:
        show_legacy_modules = get_settings().show_legacy_modules
    return MAIN_PAGES + (LEGACY_PAGES if show_legacy_modules else ())


def render_dashboard() -> None:
    st.set_page_config(page_title=APP_NAME, page_icon="SF", layout="wide")
    settings = get_settings()
    init_db()
    with new_session() as session:
        seed_defaults(session)

    st.sidebar.title(APP_NAME)
    st.sidebar.caption("Asistente de produccion de Shorts")
    selected_page = _select_page(settings.show_legacy_modules)

    if selected_page.module == "home":
        render_home()
        return

    module = importlib.import_module(f"app.ui.pages.{selected_page.module}")
    module.render()


def _select_page(show_legacy_modules: bool) -> Page:
    selected_label = st.sidebar.radio(
        "Flujo principal",
        [page.label for page in MAIN_PAGES],
        label_visibility="collapsed",
    )
    selected_page = next(page for page in MAIN_PAGES if page.label == selected_label)

    if show_legacy_modules:
        st.sidebar.divider()
        st.sidebar.caption("Legacy / Avanzado")
        legacy_labels = ["No abrir legacy", *[page.label for page in LEGACY_PAGES]]
        selected_legacy_label = st.sidebar.selectbox("Modulo legacy", legacy_labels)
        if selected_legacy_label != "No abrir legacy":
            return next(page for page in LEGACY_PAGES if page.label == selected_legacy_label)

    return selected_page


def render_home() -> None:
    st.title("Inicio")
    st.caption("Vista rapida del estado de produccion y del flujo canonico de ShortsFactory.")
    filters = _render_filters()
    metrics = _load_metrics(filters)

    columns = st.columns(8)
    columns[0].metric("Investigaciones", metrics["research_runs"])
    columns[1].metric("Ideas candidatas", metrics["idea_candidates"])
    columns[2].metric("Proyectos", metrics["video_projects"])
    columns[3].metric("Guiones", metrics["script_drafts"])
    columns[4].metric("Voces", metrics["voiceover_jobs"])
    columns[5].metric("Escenas", metrics["selected_scenes"])
    columns[6].metric("Clips", metrics["generated_clips"])
    columns[7].metric("Renders", metrics["render_jobs"])

    st.subheader("Flujo canonico")
    quick_cols = st.columns(3)
    quick_cols[0].info("Investigacion -> Creacion -> Ideas")
    quick_cols[1].info("Produccion -> Mapeo de clips -> Renderizar")
    quick_cols[2].info("Revision -> Exportaciones")

    st.subheader("Tablero de proyectos")
    rows = _load_project_rows(filters)
    if not rows:
        st.info("Crea tu primer proyecto desde Investigacion -> Creacion -> Ideas.")
        return

    statuses = sorted({str(row["status"]) for row in rows})
    board_columns = st.columns(max(1, len(statuses)))
    for column, status in zip(board_columns, statuses, strict=False):
        with column:
            st.markdown(f"**{label_for(STATUS_LABELS, status)}**")
            for row in [item for item in rows if item["status"] == status]:
                st.caption(f"#{row['id']} | {row['title']}")

    st.dataframe(rows, use_container_width=True, hide_index=True)


def _render_filters() -> dict[str, str]:
    with st.expander("Filtros", expanded=False):
        col1, col2 = st.columns(2)
        language_options = ["all", "en", "es", "hi_hinglish"]
        language = col1.selectbox(
            "Idioma contenido",
            language_options,
            format_func=lambda value: "Todos" if value == "all" else value,
        )
        status_options = [
            "all",
            "metadata_selected",
            "character_selected",
            "script_draft",
            "script_approved",
            "voiceover_generated",
            "scenes_planned",
            "created",
        ]
        status = col2.selectbox(
            "Estado proyecto",
            status_options,
            format_func=lambda value: (
                "Todos" if value == "all" else label_for(STATUS_LABELS, value)
            ),
        )
    return {"language": language, "status": status}


def _load_metrics(filters: dict[str, str]) -> dict[str, int]:
    with new_session() as session:
        project_ids = _filtered_project_ids(session, filters)

        return {
            "research_runs": session.scalar(select(func.count(models.ResearchRun.id))) or 0,
            "idea_candidates": session.scalar(select(func.count(models.IdeaCandidate.id))) or 0,
            "video_projects": len(project_ids),
            "script_drafts": _count_for_projects(session, models.ScriptDraft, project_ids),
            "voiceover_jobs": _count_for_projects(session, models.VoiceoverJob, project_ids),
            "selected_scenes": _count_for_projects(session, models.SelectedScene, project_ids),
            "generated_clips": _count_for_projects(session, models.GeneratedClip, project_ids),
            "render_jobs": _count_for_projects(session, models.RenderJob, project_ids),
        }


def _load_project_rows(filters: dict[str, str]) -> list[dict[str, object]]:
    with new_session() as session:
        query = select(models.VideoProject).order_by(models.VideoProject.created_at.desc())
        if filters["language"] != "all":
            query = query.where(models.VideoProject.content_language == filters["language"])
        if filters["status"] != "all":
            query = query.where(models.VideoProject.status == filters["status"])
        projects = session.scalars(query).all()
        return [
            {
                "id": project.id,
                "title": project.title,
                "status": project.status,
                "content_language": project.content_language,
                "target_duration_seconds": project.target_duration_seconds,
                "created_at": project.created_at,
                "script_status": _latest_status(session, models.ScriptDraft, project.id),
                "voice_status": _latest_status(session, models.VoiceoverJob, project.id),
                "selected_scenes_count": _count_for_projects(
                    session, models.SelectedScene, [project.id]
                ),
                "generated_clips_count": _count_for_projects(
                    session, models.GeneratedClip, [project.id]
                ),
                "render_jobs_count": _count_for_projects(session, models.RenderJob, [project.id]),
            }
            for project in projects
        ]


def _filtered_project_ids(session, filters: dict[str, str]) -> list[int]:
    query = select(models.VideoProject.id)
    if filters["language"] != "all":
        query = query.where(models.VideoProject.content_language == filters["language"])
    if filters["status"] != "all":
        query = query.where(models.VideoProject.status == filters["status"])
    return list(session.scalars(query).all())


def _count_for_projects(session, model, project_ids: list[int]) -> int:
    if not project_ids:
        return 0
    return (
        session.scalar(select(func.count(model.id)).where(model.video_project_id.in_(project_ids)))
        or 0
    )


def _latest_status(session, model, project_id: int) -> str:
    item = session.scalar(
        select(model).where(model.video_project_id == project_id).order_by(model.created_at.desc())
    )
    return item.status if item else "missing"
