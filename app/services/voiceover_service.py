from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.core.enums import ScriptStatus
from app.db import models
from app.db.repositories import create_script_with_lines, create_topic
from app.services.project_status_service import refresh_video_project_status
from app.services.voiceover_generation_service import create_voiceover_from_script


@dataclass(frozen=True)
class VoiceoverEstimate:
    character_count: int
    estimated_cost_usd: float
    requires_confirmation: bool
    provider: str


def estimate_voiceover_cost_or_usage(text: str) -> VoiceoverEstimate:
    settings = get_settings()
    character_count = len(text)
    estimated_cost = (character_count / 1000) * settings.elevenlabs_estimated_cost_per_1000_chars
    return VoiceoverEstimate(
        character_count=character_count,
        estimated_cost_usd=estimated_cost,
        requires_confirmation=estimated_cost > settings.elevenlabs_confirm_cost_above_usd,
        provider="elevenlabs_tts" if settings.enable_elevenlabs_tts else "placeholder",
    )


def create_voiceover(
    session: Session,
    *,
    video_project_id: int,
    script_draft_id: int,
    allow_paid: bool = False,
) -> models.VoiceoverJob:
    project = _get_or_raise(session, models.VideoProject, video_project_id)
    script_draft = _get_or_raise(session, models.ScriptDraft, script_draft_id)
    legacy_script = _ensure_legacy_script(session, project, script_draft)
    settings = get_settings()
    provider_name = "elevenlabs_tts" if _elevenlabs_ready() else "placeholder"
    job = create_voiceover_from_script(
        session,
        script_id=legacy_script.id,
        provider_name=provider_name,
        language="en",
        voice_id=settings.elevenlabs_default_voice_id or None,
        allow_paid=allow_paid,
        model_id=settings.elevenlabs_model_id,
    )
    job.video_project_id = project.id
    job.script_draft_id = script_draft.id
    job.model_id = settings.elevenlabs_model_id if provider_name == "elevenlabs_tts" else None
    job.text = script_draft.voiceover_text
    job.text_hash = hashlib.sha256(script_draft.voiceover_text.encode("utf-8")).hexdigest()
    job.output_path = job.output_audio_path
    job.character_count = len(script_draft.voiceover_text)
    job.metadata_json = _merged_metadata(
        job.metadata_json,
        {
            "video_project_id": project.id,
            "script_draft_id": script_draft.id,
            "pipeline_provider": provider_name,
        },
    )
    project.status = "voiceover_generated" if job.status not in {"failed"} else "voiceover_failed"
    session.commit()
    session.refresh(job)
    refresh_video_project_status(session, project.id)
    return job


def poll_or_finalize_voiceover(session: Session, job_id: int) -> models.VoiceoverJob:
    job = _get_or_raise(session, models.VoiceoverJob, job_id)
    return job


def _ensure_legacy_script(
    session: Session,
    project: models.VideoProject,
    script_draft: models.ScriptDraft,
) -> models.Script:
    existing = (
        session.query(models.Script)
        .filter(models.Script.script_text == script_draft.voiceover_text)
        .order_by(models.Script.created_at.desc())
        .first()
    )
    if existing is not None:
        if existing.status != ScriptStatus.APPROVED.value:
            existing.status = ScriptStatus.APPROVED.value
            session.commit()
        return existing

    topic = create_topic(
        session,
        title=project.title,
        summary=project.description,
        category="other",
        source="pipeline_video_project",
        language_origin="en",
        target_markets=project.target_market,
        status="approved_for_hooks",
    )
    lines = _script_lines(script_draft)
    return create_script_with_lines(
        session,
        script_data={
            "topic_id": topic.id,
            "language": "en",
            "script_text": script_draft.voiceover_text,
            "estimated_duration_seconds": float(script_draft.estimated_duration_seconds),
            "status": ScriptStatus.APPROVED.value,
            "needs_fact_check": True,
            "title_suggestion": project.title,
            "description_suggestion": project.description,
            "hashtags": project.hashtags_json,
        },
        lines=lines,
    )


def _script_lines(script_draft: models.ScriptDraft) -> list[dict[str, object]]:
    try:
        beats = json.loads(script_draft.beats_json or "[]")
    except json.JSONDecodeError:
        beats = []
    if isinstance(beats, list) and beats:
        return [
            {
                "text": str(beat.get("text") or ""),
                "visual_suggestion": str(beat.get("visual_intent") or ""),
                "duration_seconds": float(beat.get("end_second") or 0)
                - float(beat.get("start_second") or 0)
                or 8.0,
            }
            for beat in beats
            if str(beat.get("text") or "").strip()
        ]
    return [
        {
            "text": line.strip(),
            "visual_suggestion": "",
            "duration_seconds": 4.0,
        }
        for line in script_draft.voiceover_text.splitlines()
        if line.strip()
    ]


def _elevenlabs_ready() -> bool:
    settings = get_settings()
    return (
        settings.enable_elevenlabs
        and settings.enable_elevenlabs_tts
        and bool(settings.elevenlabs_api_key)
        and bool(settings.elevenlabs_default_voice_id)
    )


def _merged_metadata(existing: str | None, extra: dict[str, object]) -> str:
    try:
        payload = json.loads(existing or "{}")
    except json.JSONDecodeError:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    payload.update(extra)
    return json.dumps(payload, ensure_ascii=False)


def _get_or_raise(session: Session, model: type[models.Base], entity_id: int):
    entity = session.get(model, entity_id)
    if entity is None:
        raise ValueError(f"{model.__name__} not found: {entity_id}")
    return entity
