from __future__ import annotations

import json

import streamlit as st

from app.db import models
from app.db.database import new_session
from app.services.pipeline_service import create_project_from_recipe, pending_metadata_recipes


def render() -> None:
    st.title("Ideas")
    st.caption("Elige los ingredientes de metadata en ingles y crea un VideoProject.")
    with new_session() as session:
        recipes = pending_metadata_recipes(session)
        if not recipes:
            st.info("No hay recetas pendientes. Envia una subidea desde Creacion.")
            return
        selected_recipe_id = st.selectbox(
            "Recetas pendientes",
            [recipe.id for recipe in recipes],
            format_func=lambda recipe_id: _recipe_label(session, recipe_id),
        )
        recipe = session.get(models.MetadataRecipeDraft, int(selected_recipe_id))
        if recipe is None:
            return
        _recipe_form(session, recipe)


def _recipe_form(session, recipe: models.MetadataRecipeDraft) -> None:
    deep_idea = session.get(models.DeepIdeaCandidate, recipe.deep_idea_candidate_id)
    if deep_idea is not None:
        st.subheader(deep_idea.title)
        st.write(deep_idea.detailed_description)

    titles = _json_loads(recipe.titles_json)
    hooks = _json_loads(recipe.hooks_json)
    descriptions = _json_loads(recipe.descriptions_json)
    hashtag_sets = _json_loads(recipe.hashtag_sets_json)

    title = st.radio(
        "Titulos propuestos",
        [item.get("title", "") for item in titles],
        captions=[item.get("reason", "") for item in titles],
    )
    hook = st.radio(
        "Hooks propuestos",
        [item.get("hook", "") for item in hooks],
        captions=[item.get("reason", "") for item in hooks],
    )
    description = st.radio(
        "Descripciones propuestas",
        [item.get("description", "") for item in descriptions],
        captions=[item.get("reason", "") for item in descriptions],
    )
    hashtag_label_map = {
        " ".join(item.get("hashtags", [])): item.get("hashtags", []) for item in hashtag_sets
    }
    selected_hashtag_label = st.radio("Hashtag sets", list(hashtag_label_map))
    if st.button("Crear proyecto y enviar a Produccion", type="primary"):
        project = create_project_from_recipe(
            session,
            metadata_recipe_id=recipe.id,
            title=title,
            hook=hook,
            description=description,
            hashtags=hashtag_label_map[selected_hashtag_label],
        )
        st.success(f"VideoProject #{project.id} creado.")
        st.rerun()


def _recipe_label(session, recipe_id: int) -> str:
    recipe = session.get(models.MetadataRecipeDraft, int(recipe_id))
    if recipe is None:
        return str(recipe_id)
    deep_idea = session.get(models.DeepIdeaCandidate, recipe.deep_idea_candidate_id)
    return f"#{recipe.id} | {deep_idea.title if deep_idea else 'Sin idea'}"


def _json_loads(value: str | None):
    try:
        decoded = json.loads(value or "[]")
    except json.JSONDecodeError:
        decoded = []
    return decoded if isinstance(decoded, list) else []

