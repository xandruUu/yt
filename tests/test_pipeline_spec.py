from __future__ import annotations

import json

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config.settings import get_settings
from app.db import models
from app.db.models import Base
from app.services.character_locker_service import create_character_cell
from app.services.character_service import list_character_cells, seed_nero_character_system
from app.services.pipeline_service import (
    create_project_from_recipe,
    run_deep_research,
    run_general_research,
    send_deep_idea_to_ideas,
    send_idea_to_creation,
)
from app.services.production_pipeline_service import (
    approve_script_draft,
    create_prompt_pack_for_selected_scene,
    generate_clip_from_scene,
    generate_script_for_project,
    plan_scenes_for_project,
    select_character_for_project,
    select_scene_candidate,
)


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, future=True)()


def test_research_creation_metadata_project_pipeline_without_category(monkeypatch) -> None:
    monkeypatch.setenv("ENABLE_OLLAMA_LLM", "false")
    get_settings.cache_clear()
    session = _session()

    research = run_general_research(
        session,
        idea_count=3,
        include_rss=False,
        include_hackernews=False,
        include_youtube=False,
        manual_input="A strange science image is going viral\nA weird history fact is trending",
    )

    assert research.research_run.content_language == "en"
    assert len(research.ideas) == 3
    assert all(idea.title for idea in research.ideas)
    assert all(idea.status == "suggested" for idea in research.ideas)

    inbox = send_idea_to_creation(session, research.ideas[0].id)
    assert inbox.status == "pending"

    _deep_run, deep_ideas = run_deep_research(session, idea_candidate_id=research.ideas[0].id)
    assert deep_ideas
    recipe = send_deep_idea_to_ideas(session, deep_ideas[0].id)
    assert json.loads(recipe.titles_json)

    title = json.loads(recipe.titles_json)[0]["title"]
    hook = json.loads(recipe.hooks_json)[0]["hook"]
    description = json.loads(recipe.descriptions_json)[0]["description"]
    hashtags = json.loads(recipe.hashtag_sets_json)[0]["hashtags"]
    project = create_project_from_recipe(
        session,
        metadata_recipe_id=recipe.id,
        title=title,
        hook=hook,
        description=description,
        hashtags=hashtags,
    )
    assert project.content_language == "en"
    assert project.ui_language == "es"
    assert project.status == "metadata_selected"


def test_locker_room_cells_and_production_pipeline(monkeypatch) -> None:
    monkeypatch.setenv("ENABLE_OLLAMA_LLM", "false")
    monkeypatch.setenv("ENABLE_HIGGSFIELD_AUTOMATION", "false")
    get_settings.cache_clear()
    session = _session()
    character = seed_nero_character_system(session)
    cell = create_character_cell(
        session,
        character=character,
        title="Nero Test Front",
        cell_type="front",
        description="Front view reference.",
        prompt_notes="Primary identity reference.",
        is_primary=True,
    )
    assert cell.is_primary is True
    assert list_character_cells(session, character.id)

    research = run_general_research(
        session,
        idea_count=1,
        include_rss=False,
        include_hackernews=False,
        include_youtube=False,
    )
    _deep_run, deep_ideas = run_deep_research(session, idea_candidate_id=research.ideas[0].id)
    recipe = send_deep_idea_to_ideas(session, deep_ideas[0].id)
    title = json.loads(recipe.titles_json)[0]["title"]
    hook = json.loads(recipe.hooks_json)[0]["hook"]
    description = json.loads(recipe.descriptions_json)[0]["description"]
    hashtags = json.loads(recipe.hashtag_sets_json)[0]["hashtags"]
    project = create_project_from_recipe(
        session,
        metadata_recipe_id=recipe.id,
        title=title,
        hook=hook,
        description=description,
        hashtags=hashtags,
    )
    select_character_for_project(
        session,
        video_project_id=project.id,
        character_profile_id=character.id,
    )
    script = generate_script_for_project(session, video_project_id=project.id)
    approved = approve_script_draft(session, script.id)
    assert approved.status == "script_approved"

    slots = plan_scenes_for_project(session, video_project_id=project.id)
    assert slots
    scene_candidate = session.query(models.SceneCandidate).first()
    assert scene_candidate is not None
    selected = select_scene_candidate(session, scene_candidate_id=scene_candidate.id)
    pack = create_prompt_pack_for_selected_scene(session, selected_scene_id=selected.id)
    assert "Vertical 9:16" in pack.prompt
    job = generate_clip_from_scene(session, selected_scene_id=selected.id)
    assert job.status == "manual_required"
    duplicate = generate_clip_from_scene(session, selected_scene_id=selected.id)
    assert duplicate.id == job.id

    forced = generate_clip_from_scene(
        session,
        selected_scene_id=selected.id,
        force_new_attempt=True,
    )
    assert forced.id != job.id
    assert forced.status == "manual_required"
