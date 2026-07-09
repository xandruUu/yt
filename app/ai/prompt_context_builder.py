from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.db import models
from app.services.character_locker_service import character_reference_images
from app.services.obsidian_sync_service import (
    get_character_brain_context,
    get_recent_lessons_context,
    get_style_guide_context,
)


def build_research_context(session: Session, research_run_id: int) -> dict[str, object]:
    run = session.get(models.ResearchRun, research_run_id)
    if run is None:
        raise ValueError(f"ResearchRun not found: {research_run_id}")
    items = (
        session.query(models.TrendItem)
        .filter_by(research_run_id=research_run_id)
        .order_by(models.TrendItem.viral_score.desc())
        .limit(40)
        .all()
    )
    return {
        "research_run": {
            "id": run.id,
            "idea_count_requested": run.idea_count_requested,
            "target_market": run.target_market,
            "content_language": run.content_language,
        },
        "trend_signals": [
            {
                "id": item.id,
                "source": item.provider_name,
                "title": item.title,
                "summary": item.summary,
                "url": item.url,
                "viral_score": item.viral_score,
                "velocity_score": item.velocity_score,
                "engagement_score": item.engagement_score,
                "visual_potential_score": item.visual_potential_score,
                "risk_score": item.risk_score,
            }
            for item in items
        ],
    }


def build_deep_research_context(session: Session, idea_candidate_id: int) -> dict[str, object]:
    idea = session.get(models.IdeaCandidate, idea_candidate_id)
    if idea is None:
        raise ValueError(f"IdeaCandidate not found: {idea_candidate_id}")
    return {
        "idea": {
            "id": idea.id,
            "title": idea.title,
            "short_description": idea.short_description,
            "viral_angle": idea.viral_angle,
            "why_now": idea.why_now,
            "visual_potential": idea.visual_potential,
            "risk_level": idea.risk_level,
            "risk_notes": idea.risk_notes,
        }
    }


def build_metadata_context(session: Session, deep_idea_id: int) -> dict[str, object]:
    idea = session.get(models.DeepIdeaCandidate, deep_idea_id)
    if idea is None:
        raise ValueError(f"DeepIdeaCandidate not found: {deep_idea_id}")
    return {
        "deep_idea": {
            "id": idea.id,
            "title": idea.title,
            "detailed_description": idea.detailed_description,
            "specific_angle": idea.specific_angle,
            "why_it_can_go_viral": idea.why_it_can_go_viral,
            "possible_hook": idea.possible_hook,
            "facts_to_verify": _json_list(idea.facts_to_verify_json),
            "visual_opportunities": _json_list(idea.visual_opportunities_json),
        }
    }


def build_script_context(session: Session, video_project_id: int) -> dict[str, object]:
    project = session.get(models.VideoProject, video_project_id)
    if project is None:
        raise ValueError(f"VideoProject not found: {video_project_id}")
    character = session.get(models.CharacterProfile, project.character_profile_id) if project.character_profile_id else None
    return {
        "project": _project_payload(project),
        "character": _character_payload(character),
        "obsidian": {
            "character_context": get_character_brain_context(session, character.id) if character else "",
            "style_guides": get_style_guide_context(),
            "recent_lessons": get_recent_lessons_context(),
        },
    }


def build_scene_context(session: Session, video_project_id: int) -> dict[str, object]:
    project = session.get(models.VideoProject, video_project_id)
    if project is None:
        raise ValueError(f"VideoProject not found: {video_project_id}")
    script = (
        session.query(models.ScriptDraft)
        .filter_by(video_project_id=video_project_id)
        .order_by(models.ScriptDraft.created_at.desc())
        .first()
    )
    character = session.get(models.CharacterProfile, project.character_profile_id) if project.character_profile_id else None
    return {
        "project": _project_payload(project),
        "script": {
            "voiceover_text": script.voiceover_text if script else "",
            "estimated_duration_seconds": script.estimated_duration_seconds if script else project.target_duration_seconds,
            "beats": _json_loads(script.beats_json) if script else [],
        },
        "character": _character_payload(character),
        "character_reference_images": character_reference_images(session, character.id) if character else [],
    }


def build_higgsfield_context(session: Session, video_project_id: int) -> dict[str, object]:
    return build_scene_context(session, video_project_id)


def _project_payload(project: models.VideoProject) -> dict[str, object]:
    return {
        "id": project.id,
        "title": project.title,
        "description": project.description,
        "hook": project.hook,
        "hashtags": _json_list(project.hashtags_json),
        "content_language": project.content_language,
        "target_market": project.target_market,
        "target_duration_seconds": project.target_duration_seconds,
        "max_duration_seconds": project.max_duration_seconds,
    }


def _character_payload(character: models.CharacterProfile | None) -> dict[str, object]:
    if character is None:
        return {}
    return {
        "id": character.id,
        "name": character.name,
        "slug": character.slug,
        "canonical_description": character.canonical_description,
        "visual_style": character.visual_style,
        "personality": character.personality,
        "prompt_fragment": character.prompt_fragment or character.master_prompt,
        "negative_prompt_fragment": character.negative_prompt_fragment or character.negative_prompt,
        "must_preserve": _json_list(character.must_preserve_json or character.required_traits_json),
        "must_avoid": _json_list(character.must_avoid_json or character.forbidden_traits_json),
    }


def _json_list(value: str | None) -> list[object]:
    decoded = _json_loads(value)
    return decoded if isinstance(decoded, list) else []


def _json_loads(value: str | None) -> object:
    try:
        return json.loads(value or "[]")
    except json.JSONDecodeError:
        return []

