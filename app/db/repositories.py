from __future__ import annotations

from collections.abc import Iterable
from typing import Any, TypeVar

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.db import models

ModelT = TypeVar("ModelT", bound=models.Base)


def add_and_commit(session: Session, entity: ModelT) -> ModelT:
    session.add(entity)
    session.commit()
    session.refresh(entity)
    return entity


def get_by_id(session: Session, model: type[ModelT], entity_id: int) -> ModelT | None:
    return session.get(model, entity_id)


def list_all(session: Session, model: type[ModelT], order_by: Any | None = None) -> list[ModelT]:
    statement: Select[tuple[ModelT]] = select(model)
    if order_by is not None:
        statement = statement.order_by(order_by)
    return list(session.scalars(statement).all())


def create_topic(session: Session, **data: Any) -> models.Topic:
    return add_and_commit(session, models.Topic(**data))


def update_topic(session: Session, topic: models.Topic, **data: Any) -> models.Topic:
    for key, value in data.items():
        setattr(topic, key, value)
    return add_and_commit(session, topic)


def create_generated_idea(session: Session, **data: Any) -> models.GeneratedIdea:
    return add_and_commit(session, models.GeneratedIdea(**data))


def list_generated_ideas(
    session: Session,
    status: str | None = None,
    limit: int = 100,
) -> list[models.GeneratedIdea]:
    statement = select(models.GeneratedIdea).order_by(
        models.GeneratedIdea.total_score.desc(),
        models.GeneratedIdea.created_at.desc(),
    )
    if status is not None:
        statement = statement.where(models.GeneratedIdea.status == status)
    return list(session.scalars(statement.limit(limit)).all())


def update_generated_idea_status(
    session: Session,
    idea: models.GeneratedIdea,
    status: str,
) -> models.GeneratedIdea:
    idea.status = status
    return add_and_commit(session, idea)


def create_generated_title(session: Session, **data: Any) -> models.GeneratedTitle:
    return add_and_commit(session, models.GeneratedTitle(**data))


def list_generated_titles_for_hook(
    session: Session,
    hook_id: int,
    limit: int = 100,
) -> list[models.GeneratedTitle]:
    statement = (
        select(models.GeneratedTitle)
        .where(models.GeneratedTitle.hook_id == hook_id)
        .order_by(models.GeneratedTitle.total_score.desc(), models.GeneratedTitle.created_at.desc())
        .limit(limit)
    )
    return list(session.scalars(statement).all())


def set_selected_title(session: Session, title: models.GeneratedTitle) -> models.GeneratedTitle:
    titles = session.scalars(
        select(models.GeneratedTitle).where(models.GeneratedTitle.hook_id == title.hook_id)
    ).all()
    for item in titles:
        item.selected = item.id == title.id
        item.status = "selected" if item.id == title.id else "suggested"
    session.commit()
    session.refresh(title)
    return title


def create_metadata_suggestion(session: Session, **data: Any) -> models.MetadataSuggestion:
    return add_and_commit(session, models.MetadataSuggestion(**data))


def create_hook(session: Session, **data: Any) -> models.Hook:
    return add_and_commit(session, models.Hook(**data))


def set_selected_hook(session: Session, hook: models.Hook) -> models.Hook:
    hooks = session.scalars(select(models.Hook).where(models.Hook.topic_id == hook.topic_id)).all()
    for item in hooks:
        item.selected = item.id == hook.id
    session.commit()
    session.refresh(hook)
    return hook


def create_script_with_lines(
    session: Session,
    script_data: dict[str, Any],
    lines: Iterable[dict[str, Any]],
) -> models.Script:
    script = models.Script(**script_data)
    for index, line in enumerate(lines, start=1):
        script.lines.append(
            models.ScriptLine(
                line_order=index,
                text=line["text"],
                visual_suggestion=line.get("visual_suggestion"),
                duration_seconds=float(line.get("duration_seconds", 2.5)),
                subtitle_text=line.get("subtitle_text") or line["text"],
                needs_source=bool(line.get("needs_source", False)),
                source_url=line.get("source_url") or line.get("source_hint"),
                risk_note=line.get("risk_note"),
            )
        )
    return add_and_commit(session, script)


def create_asset(session: Session, **data: Any) -> models.Asset:
    return add_and_commit(session, models.Asset(**data))


def create_music_track(session: Session, **data: Any) -> models.MusicTrack:
    return add_and_commit(session, models.MusicTrack(**data))


def create_voiceover_job(session: Session, **data: Any) -> models.VoiceoverJob:
    return add_and_commit(session, models.VoiceoverJob(**data))


def create_subtitle_track(session: Session, **data: Any) -> models.SubtitleTrack:
    return add_and_commit(session, models.SubtitleTrack(**data))


def create_visual_plan(session: Session, **data: Any) -> models.VisualPlan:
    return add_and_commit(session, models.VisualPlan(**data))


def create_character_profile(session: Session, **data: Any) -> models.CharacterProfile:
    return add_and_commit(session, models.CharacterProfile(**data))


def create_character_family(session: Session, **data: Any) -> models.CharacterFamily:
    return add_and_commit(session, models.CharacterFamily(**data))


def create_character_cell(session: Session, **data: Any) -> models.CharacterCell:
    return add_and_commit(session, models.CharacterCell(**data))


def create_character_pose(session: Session, **data: Any) -> models.CharacterPose:
    return add_and_commit(session, models.CharacterPose(**data))


def create_character_variant(session: Session, **data: Any) -> models.CharacterVariant:
    return add_and_commit(session, models.CharacterVariant(**data))


def create_visual_storyboard(session: Session, **data: Any) -> models.VisualStoryboard:
    return add_and_commit(session, models.VisualStoryboard(**data))


def create_storyboard_scene(session: Session, **data: Any) -> models.StoryboardScene:
    return add_and_commit(session, models.StoryboardScene(**data))


def create_scene_asset_mapping(session: Session, **data: Any) -> models.SceneAssetMapping:
    return add_and_commit(session, models.SceneAssetMapping(**data))


def create_render_plan(session: Session, **data: Any) -> models.RenderPlan:
    return add_and_commit(session, models.RenderPlan(**data))


def create_external_tool_job(session: Session, **data: Any) -> models.ExternalToolJob:
    return add_and_commit(session, models.ExternalToolJob(**data))


def create_prompt_pack(session: Session, **data: Any) -> models.PromptPack:
    return add_and_commit(session, models.PromptPack(**data))


def create_external_asset(session: Session, **data: Any) -> models.ExternalAsset:
    return add_and_commit(session, models.ExternalAsset(**data))


def create_research_run(session: Session, **data: Any) -> models.ResearchRun:
    return add_and_commit(session, models.ResearchRun(**data))


def create_provider_fetch_log(session: Session, **data: Any) -> models.ProviderFetchLog:
    return add_and_commit(session, models.ProviderFetchLog(**data))


def create_trend_item(session: Session, **data: Any) -> models.TrendItem:
    return add_and_commit(session, models.TrendItem(**data))


def create_idea_candidate(session: Session, **data: Any) -> models.IdeaCandidate:
    return add_and_commit(session, models.IdeaCandidate(**data))


def create_creation_inbox_item(session: Session, **data: Any) -> models.CreationInboxItem:
    return add_and_commit(session, models.CreationInboxItem(**data))


def create_deep_research_run(session: Session, **data: Any) -> models.DeepResearchRun:
    return add_and_commit(session, models.DeepResearchRun(**data))


def create_deep_idea_candidate(session: Session, **data: Any) -> models.DeepIdeaCandidate:
    return add_and_commit(session, models.DeepIdeaCandidate(**data))


def create_metadata_recipe_draft(session: Session, **data: Any) -> models.MetadataRecipeDraft:
    return add_and_commit(session, models.MetadataRecipeDraft(**data))


def create_video_project(session: Session, **data: Any) -> models.VideoProject:
    return add_and_commit(session, models.VideoProject(**data))


def create_script_draft(session: Session, **data: Any) -> models.ScriptDraft:
    return add_and_commit(session, models.ScriptDraft(**data))


def create_scene_slot(session: Session, **data: Any) -> models.SceneSlot:
    return add_and_commit(session, models.SceneSlot(**data))


def create_scene_candidate(session: Session, **data: Any) -> models.SceneCandidate:
    return add_and_commit(session, models.SceneCandidate(**data))


def create_selected_scene(session: Session, **data: Any) -> models.SelectedScene:
    return add_and_commit(session, models.SelectedScene(**data))


def create_higgsfield_prompt_pack(session: Session, **data: Any) -> models.HiggsfieldPromptPack:
    return add_and_commit(session, models.HiggsfieldPromptPack(**data))


def create_higgsfield_job(session: Session, **data: Any) -> models.HiggsfieldJob:
    return add_and_commit(session, models.HiggsfieldJob(**data))


def create_generated_clip(session: Session, **data: Any) -> models.GeneratedClip:
    return add_and_commit(session, models.GeneratedClip(**data))


def create_render_job(session: Session, **data: Any) -> models.RenderJob:
    return add_and_commit(session, models.RenderJob(**data))


def create_obsidian_sync_log(session: Session, **data: Any) -> models.ObsidianSyncLog:
    return add_and_commit(session, models.ObsidianSyncLog(**data))


def create_cost_event(session: Session, **data: Any) -> models.CostEvent:
    return add_and_commit(session, models.CostEvent(**data))


def create_render(session: Session, **data: Any) -> models.Render:
    return add_and_commit(session, models.Render(**data))


def create_or_update_checklist(
    session: Session,
    render_id: int,
    **data: Any,
) -> models.ReviewChecklist:
    checklist = session.scalar(
        select(models.ReviewChecklist).where(models.ReviewChecklist.render_id == render_id)
    )
    if checklist is None:
        checklist = models.ReviewChecklist(render_id=render_id, **data)
    else:
        for key, value in data.items():
            setattr(checklist, key, value)
    return add_and_commit(session, checklist)
