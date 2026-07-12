from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models

SCRIPT_APPROVED_STATUSES = {"script_approved", "approved"}
VOICE_GENERATED_STATUSES = {"generated", "completed", "ready", "placeholder", "imported_manual"}
VOICE_APPROVED_STATUSES = {"approved", *VOICE_GENERATED_STATUSES}
INVALID_CLIP_STATUSES = {"discarded", "rejected", "failed"}
PROMPT_PACK_READY_STATUSES = {"generated", "draft", "pending_confirmation", "ready"}
HIGGSFIELD_SUBMITTED_STATUSES = {"submitted", "running"}


def refresh_video_project_status(session: Session, video_project_id: int) -> models.VideoProject:
    project = session.get(models.VideoProject, video_project_id)
    if project is None:
        raise ValueError(f"VideoProject not found: {video_project_id}")

    selected_scenes = _selected_scenes(session, video_project_id)
    selected_scene_ids = [scene.id for scene in selected_scenes]
    selected_count = len(selected_scenes)

    if _has_canonical_export(session, video_project_id):
        next_status = "exported"
    elif _has_approved_render(session, video_project_id):
        next_status = "approved"
    elif _has_rendered_render_job(session, video_project_id):
        next_status = "rendered"
    elif selected_count and _ready_clip_count(session, selected_scene_ids) >= selected_count:
        next_status = (
            "render_ready" if _has_approved_voiceover(session, video_project_id) else "clips_ready"
        )
    elif _has_higgsfield_submitted(session, video_project_id):
        next_status = "higgsfield_submitted"
    elif selected_count and _ready_prompt_pack_count(session, selected_scene_ids) >= selected_count:
        next_status = "prompt_packs_ready"
    elif selected_count:
        next_status = "scenes_selected"
    elif _has_scene_plan(session, video_project_id):
        next_status = "scenes_planned"
    elif _has_approved_voiceover(session, video_project_id):
        next_status = "voiceover_approved"
    elif _has_generated_voiceover(session, video_project_id):
        next_status = "voiceover_generated"
    elif _has_approved_script(session, video_project_id):
        next_status = "script_approved"
    elif _has_script_draft(session, video_project_id):
        next_status = "script_draft"
    elif project.character_profile_id:
        next_status = "character_selected"
    else:
        next_status = "metadata_selected"

    project.status = next_status
    session.commit()
    session.refresh(project)
    return project


def _selected_scenes(session: Session, video_project_id: int) -> list[models.SelectedScene]:
    return list(
        session.scalars(
            select(models.SelectedScene).where(
                models.SelectedScene.video_project_id == video_project_id
            )
        ).all()
    )


def _has_canonical_export(session: Session, video_project_id: int) -> bool:
    jobs = session.scalars(
        select(models.RenderJob).where(models.RenderJob.video_project_id == video_project_id)
    ).all()
    return any(_metadata(job.metadata_json).get("export_folder") for job in jobs)


def _has_approved_render(session: Session, video_project_id: int) -> bool:
    return (
        session.scalar(
            select(models.RenderJob.id).where(
                models.RenderJob.video_project_id == video_project_id,
                models.RenderJob.status.in_(("rendered", "exported")),
                models.RenderJob.approved.is_(True),
            )
        )
        is not None
    )


def _has_rendered_render_job(session: Session, video_project_id: int) -> bool:
    return (
        session.scalar(
            select(models.RenderJob.id).where(
                models.RenderJob.video_project_id == video_project_id,
                models.RenderJob.status.in_(("rendered", "exported")),
            )
        )
        is not None
    )


def _ready_clip_count(session: Session, selected_scene_ids: list[int]) -> int:
    if not selected_scene_ids:
        return 0
    rows = session.scalars(
        select(models.GeneratedClip.selected_scene_id).where(
            models.GeneratedClip.selected_scene_id.in_(selected_scene_ids),
            models.GeneratedClip.status.not_in(INVALID_CLIP_STATUSES),
        )
    ).all()
    return len(set(rows))


def _has_higgsfield_submitted(session: Session, video_project_id: int) -> bool:
    return (
        session.scalar(
            select(models.HiggsfieldJob.id).where(
                models.HiggsfieldJob.video_project_id == video_project_id,
                models.HiggsfieldJob.status.in_(HIGGSFIELD_SUBMITTED_STATUSES),
            )
        )
        is not None
    )


def _ready_prompt_pack_count(session: Session, selected_scene_ids: list[int]) -> int:
    if not selected_scene_ids:
        return 0
    rows = session.scalars(
        select(models.HiggsfieldPromptPack.selected_scene_id).where(
            models.HiggsfieldPromptPack.selected_scene_id.in_(selected_scene_ids),
            models.HiggsfieldPromptPack.status.in_(PROMPT_PACK_READY_STATUSES),
        )
    ).all()
    return len(set(rows))


def _has_scene_plan(session: Session, video_project_id: int) -> bool:
    return (
        session.scalar(
            select(models.SceneSlot.id).where(models.SceneSlot.video_project_id == video_project_id)
        )
        is not None
    )


def _has_approved_voiceover(session: Session, video_project_id: int) -> bool:
    return (
        session.scalar(
            select(models.VoiceoverJob.id).where(
                models.VoiceoverJob.video_project_id == video_project_id,
                models.VoiceoverJob.status.in_(VOICE_APPROVED_STATUSES),
            )
        )
        is not None
    )


def _has_generated_voiceover(session: Session, video_project_id: int) -> bool:
    return (
        session.scalar(
            select(models.VoiceoverJob.id).where(
                models.VoiceoverJob.video_project_id == video_project_id,
                models.VoiceoverJob.status.in_(VOICE_GENERATED_STATUSES),
            )
        )
        is not None
    )


def _has_approved_script(session: Session, video_project_id: int) -> bool:
    return (
        session.scalar(
            select(models.ScriptDraft.id).where(
                models.ScriptDraft.video_project_id == video_project_id,
                models.ScriptDraft.status.in_(SCRIPT_APPROVED_STATUSES),
            )
        )
        is not None
    )


def _has_script_draft(session: Session, video_project_id: int) -> bool:
    return (
        session.scalar(
            select(models.ScriptDraft.id).where(
                models.ScriptDraft.video_project_id == video_project_id
            )
        )
        is not None
    )


def _metadata(raw: str | None) -> dict[str, Any]:
    try:
        value = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}
