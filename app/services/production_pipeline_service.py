from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.ai.llm_gateway import LLMGateway
from app.ai.ollama_client import compact_json
from app.ai.prompt_context_builder import build_scene_context, build_script_context
from app.ai.schemas.scenes import SceneCandidatePayload, ScenePlannerResponse, SceneSlotPayload
from app.ai.schemas.script import ScriptBeatPayload, ScriptDraftResponse
from app.config.settings import get_settings
from app.db import models
from app.db.repositories import (
    add_and_commit,
    create_higgsfield_job,
    create_higgsfield_prompt_pack,
    create_scene_candidate,
    create_scene_slot,
    create_script_draft,
    create_selected_scene,
)
from app.external_tools.higgsfield.client import HiggsfieldClient, HiggsfieldStatus
from app.services.character_locker_service import character_reference_images

SCRIPT_SYSTEM_PROMPT = """You are the head writer of a YouTube Shorts factory.
The UI is Spanish, but the full script and every creative output must be English.
Write fast, clear, voiceover-ready English for a 45-90 second short.
Return valid JSON only."""

SCENE_SYSTEM_PROMPT = """You are a cinematic scene planner for vertical YouTube Shorts.
The UI is Spanish, but all scene descriptions and video prompts must be English.
Build compatible scene slots from the approved script and character references.
Each Higgsfield clip must be 7 to 15 seconds.
Return valid JSON only."""


def select_character_for_project(
    session: Session,
    *,
    video_project_id: int,
    character_profile_id: int,
) -> models.VideoProject:
    project = _get_or_raise(session, models.VideoProject, video_project_id)
    character = _get_or_raise(session, models.CharacterProfile, character_profile_id)
    project.character_profile_id = character.id
    project.status = "character_selected"
    return add_and_commit(session, project)


def generate_script_for_project(
    session: Session,
    *,
    video_project_id: int,
    llm_gateway: LLMGateway | None = None,
) -> models.ScriptDraft:
    project = _get_or_raise(session, models.VideoProject, video_project_id)
    context = build_script_context(session, project.id)
    gateway = llm_gateway or LLMGateway()
    result = gateway.generate_json(
        system_prompt=SCRIPT_SYSTEM_PROMPT,
        user_prompt=f"Generate a script draft in English from this JSON:\n{compact_json(context)}",
        schema=ScriptDraftResponse,
        temperature=get_settings().ollama_temperature_script,
    )
    if result.ok and isinstance(result.data, ScriptDraftResponse):
        payload = result.data.script
    else:
        payload = _fallback_script_payload(project)
    script = create_script_draft(
        session,
        video_project_id=project.id,
        language="en",
        voiceover_text=payload.voiceover_text,
        estimated_duration_seconds=payload.target_duration_seconds,
        estimated_words=payload.estimated_words or _word_count(payload.voiceover_text),
        beats_json=json.dumps([beat.model_dump() for beat in payload.beats], ensure_ascii=False),
        fact_check_notes_json=json.dumps(payload.fact_check_notes, ensure_ascii=False),
        risk_notes_json=json.dumps(payload.risk_notes, ensure_ascii=False),
        status="script_draft",
    )
    project.status = "script_draft"
    add_and_commit(session, project)
    return script


def approve_script_draft(session: Session, script_draft_id: int) -> models.ScriptDraft:
    script = _get_or_raise(session, models.ScriptDraft, script_draft_id)
    _validate_script_draft(script)
    script.status = "script_approved"
    project = session.get(models.VideoProject, script.video_project_id)
    if project is not None:
        project.status = "script_approved"
    session.commit()
    session.refresh(script)
    return script


def plan_scenes_for_project(
    session: Session,
    *,
    video_project_id: int,
    llm_gateway: LLMGateway | None = None,
) -> list[models.SceneSlot]:
    project = _get_or_raise(session, models.VideoProject, video_project_id)
    context = build_scene_context(session, project.id)
    gateway = llm_gateway or LLMGateway()
    result = gateway.generate_json(
        system_prompt=SCENE_SYSTEM_PROMPT,
        user_prompt=f"Generate compatible scene slots in English from this JSON:\n{compact_json(context)}",
        schema=ScenePlannerResponse,
        temperature=get_settings().ollama_temperature_scenes,
    )
    if result.ok and isinstance(result.data, ScenePlannerResponse) and result.data.scene_slots:
        slots_payload = result.data.scene_slots
    else:
        slots_payload = _fallback_scene_slots(context)
    slots = []
    for slot_payload in slots_payload:
        slot = create_scene_slot(
            session,
            video_project_id=project.id,
            slot_number=slot_payload.slot_number,
            slot_type=slot_payload.slot_type,
            target_start_second=slot_payload.target_start_second,
            target_end_second=slot_payload.target_end_second,
            voiceover_segment=slot_payload.candidates[0].voiceover_segment
            if slot_payload.candidates
            else "",
        )
        for candidate_payload in slot_payload.candidates:
            create_scene_candidate(
                session,
                scene_slot_id=slot.id,
                option_code=candidate_payload.option_code,
                duration_seconds=min(candidate_payload.duration_seconds, get_settings().higgsfield_max_scene_duration_seconds),
                visual_description=candidate_payload.visual_description,
                character_action=candidate_payload.character_action,
                camera_movement=candidate_payload.camera_movement,
                setting=candidate_payload.setting,
                continuity_in=candidate_payload.continuity_in,
                continuity_out=candidate_payload.continuity_out,
                compatible_next_states_json=json.dumps(
                    candidate_payload.compatible_next_states,
                    ensure_ascii=False,
                ),
                required_character_cell_ids_json=json.dumps(
                    candidate_payload.required_character_cells,
                    ensure_ascii=False,
                ),
                notes=candidate_payload.notes,
                status="suggested",
            )
        slots.append(slot)
    project.status = "scenes_planned"
    add_and_commit(session, project)
    return slots


def select_scene_candidate(
    session: Session,
    *,
    scene_candidate_id: int,
) -> models.SelectedScene:
    candidate = _get_or_raise(session, models.SceneCandidate, scene_candidate_id)
    slot = _get_or_raise(session, models.SceneSlot, candidate.scene_slot_id)
    selected = create_selected_scene(
        session,
        video_project_id=slot.video_project_id,
        scene_slot_id=slot.id,
        scene_candidate_id=candidate.id,
        sort_order=slot.slot_number,
        status="selected",
    )
    candidate.status = "selected"
    session.commit()
    return selected


def create_prompt_pack_for_selected_scene(
    session: Session,
    *,
    selected_scene_id: int,
) -> models.HiggsfieldPromptPack:
    selected = _get_or_raise(session, models.SelectedScene, selected_scene_id)
    candidate = _get_or_raise(session, models.SceneCandidate, selected.scene_candidate_id)
    project = _get_or_raise(session, models.VideoProject, selected.video_project_id)
    character = session.get(models.CharacterProfile, project.character_profile_id) if project.character_profile_id else None
    references = character_reference_images(session, character.id) if character else []
    prompt = _higgsfield_prompt(project, character, candidate)
    negative = _negative_prompt(character)
    return create_higgsfield_prompt_pack(
        session,
        video_project_id=project.id,
        selected_scene_id=selected.id,
        prompt=prompt,
        negative_prompt=negative,
        reference_images_json=json.dumps(references, ensure_ascii=False),
        camera_movement=candidate.camera_movement,
        style_notes="Vertical 9:16, high-retention, animated documentary look.",
        consistency_notes="The character must remain identical to the selected locker room references.",
        aspect_ratio=get_settings().higgsfield_default_aspect_ratio,
        duration_seconds=candidate.duration_seconds,
        status="generated",
    )


def check_higgsfield_status() -> HiggsfieldStatus:
    return HiggsfieldClient().check_status()


def generate_clip_from_scene(
    session: Session,
    *,
    selected_scene_id: int,
    confirmed_credits: bool = False,
) -> models.HiggsfieldJob:
    prompt_pack = _prompt_pack_for_scene(session, selected_scene_id)
    status = check_higgsfield_status()
    estimated_credits = max(1.0, prompt_pack.duration_seconds / 8.0 * 2.0)
    if estimated_credits > get_settings().higgsfield_confirm_credits_above and not confirmed_credits:
        return create_higgsfield_job(
            session,
            video_project_id=prompt_pack.video_project_id,
            selected_scene_id=prompt_pack.selected_scene_id,
            prompt_pack_id=prompt_pack.id,
            automation_mode=status.mode,
            submitted_payload_json=_job_payload(prompt_pack),
            status="pending_confirmation",
            estimated_credits=estimated_credits,
        )
    if not status.available:
        return create_higgsfield_job(
            session,
            video_project_id=prompt_pack.video_project_id,
            selected_scene_id=prompt_pack.selected_scene_id,
            prompt_pack_id=prompt_pack.id,
            automation_mode=status.mode,
            submitted_payload_json=_job_payload(prompt_pack),
            status="manual_required",
            error_message=status.detail,
            estimated_credits=estimated_credits,
        )
    return create_higgsfield_job(
        session,
        video_project_id=prompt_pack.video_project_id,
        selected_scene_id=prompt_pack.selected_scene_id,
        prompt_pack_id=prompt_pack.id,
        automation_mode=status.mode,
        submitted_payload_json=_job_payload(prompt_pack),
        status="created",
        error_message="Ready for CLI/MCP submission after explicit user confirmation.",
        estimated_credits=estimated_credits,
        started_at=datetime.now(UTC),
    )


def _prompt_pack_for_scene(session: Session, selected_scene_id: int) -> models.HiggsfieldPromptPack:
    existing = (
        session.query(models.HiggsfieldPromptPack)
        .filter_by(selected_scene_id=selected_scene_id)
        .order_by(models.HiggsfieldPromptPack.created_at.desc())
        .first()
    )
    if existing is not None:
        return existing
    return create_prompt_pack_for_selected_scene(session, selected_scene_id=selected_scene_id)


def _fallback_script_payload(project: models.VideoProject):
    text = (
        f"{project.hook}\n\n"
        f"Here's the strange part: {project.title} is not just a random trend. "
        "It works because the first image creates a question in your brain. "
        "Then every detail either confirms the mystery or flips what you expected. "
        "That is why short videos like this can hold attention: they turn one clear idea "
        "into a tiny visual puzzle. And once you notice the pattern, you start seeing it everywhere."
    )
    beats = [
        ScriptBeatPayload(
            beat_number=1,
            purpose="hook",
            start_second=0,
            end_second=8,
            text=project.hook or "This looks simple, but the explanation is weird.",
            visual_intent="Nero opens with a surprised visual clue.",
        ),
        ScriptBeatPayload(
            beat_number=2,
            purpose="setup",
            start_second=8,
            end_second=22,
            text="Here's the strange part: it is not just a random trend.",
            visual_intent="Nero points at a simple cause-effect diagram.",
        ),
        ScriptBeatPayload(
            beat_number=3,
            purpose="payoff",
            start_second=22,
            end_second=45,
            text="Every detail either confirms the mystery or flips what you expected.",
            visual_intent="Animated before/after reveal.",
        ),
    ]
    return ScriptDraftResponse.model_validate(
        {
            "script": {
                "language": "en",
                "target_duration_seconds": 60,
                "estimated_words": _word_count(text),
                "tone": "energetic, curious, educational",
                "voiceover_text": text,
                "beats": [beat.model_dump() for beat in beats],
                "fact_check_notes": ["Verify factual claims before final render."],
                "risk_notes": ["Fallback script; needs human review."],
            }
        }
    ).script


def _fallback_scene_slots(context: dict[str, object]) -> list[SceneSlotPayload]:
    script = context.get("script", {})
    beats = script.get("beats") if isinstance(script, dict) else []
    if not isinstance(beats, list) or not beats:
        beats = [
            {"purpose": "hook", "start_second": 0, "end_second": 8, "text": "Opening curiosity hook."},
            {"purpose": "setup", "start_second": 8, "end_second": 22, "text": "Set up the visual mystery."},
            {"purpose": "payoff", "start_second": 22, "end_second": 38, "text": "Reveal the surprising explanation."},
        ]
    slots = []
    for index, beat in enumerate(beats, start=1):
        start = float(beat.get("start_second") or (index - 1) * 8)
        end = min(float(beat.get("end_second") or start + 8), start + 15)
        text = str(beat.get("text") or "")
        option = SceneCandidatePayload(
            option_code=f"{index}A",
            duration_seconds=max(7.0, min(15.0, end - start)),
            voiceover_segment=text,
            visual_description=f"Vertical animated scene where Nero illustrates: {text}",
            character_action="Nero points at the key visual clue with curious energy.",
            camera_movement="slow push-in",
            setting="clean animated explainer set",
            continuity_in="start" if index == 1 else "previous_reveal",
            continuity_out="curiosity_established" if index == 1 else "next_explanation",
            compatible_next_states=["previous_reveal", "next_explanation"],
            required_character_cells=[],
            notes="Fallback scene generated without LLM.",
        )
        slots.append(
            SceneSlotPayload(
                slot_number=index,
                slot_type=str(beat.get("purpose") or "scene"),
                target_start_second=start,
                target_end_second=end,
                candidates=[option],
            )
        )
    return slots


def _validate_script_draft(script: models.ScriptDraft) -> None:
    if script.language != "en":
        raise ValueError("El guion debe estar en ingles.")
    if script.estimated_duration_seconds > 90:
        raise ValueError("El guion supera 90 segundos.")
    forbidden = ("interfaz", "pantalla de la app", "haz clic", "boton")
    lowered = script.voiceover_text.lower()
    if any(term in lowered for term in forbidden):
        raise ValueError("El guion no debe mencionar la UI espanola.")


def _higgsfield_prompt(
    project: models.VideoProject,
    character: models.CharacterProfile | None,
    candidate: models.SceneCandidate,
) -> str:
    character_prompt = (
        character.prompt_fragment or character.canonical_description if character else "A consistent friendly host character"
    )
    return (
        "Vertical 9:16 cinematic animated YouTube Short. "
        f"Project title: {project.title}. "
        f"Character: {character_prompt}. "
        f"Scene: {candidate.visual_description}. "
        f"Action: {candidate.character_action}. "
        f"Setting: {candidate.setting}. "
        f"Camera movement: {candidate.camera_movement}. "
        "High-retention composition, clean readable visuals, no on-screen text, no logos."
    )


def _negative_prompt(character: models.CharacterProfile | None) -> str:
    base = "No text, no subtitles, no watermarks, no logos, no copyrighted characters, no real celebrities."
    if character is None:
        return base
    return f"{character.negative_prompt_fragment or character.negative_prompt}. {base}"


def _job_payload(prompt_pack: models.HiggsfieldPromptPack) -> str:
    return json.dumps(
        {
            "prompt": prompt_pack.prompt,
            "negative_prompt": prompt_pack.negative_prompt,
            "reference_images": json.loads(prompt_pack.reference_images_json or "[]"),
            "aspect_ratio": prompt_pack.aspect_ratio,
            "duration_seconds": prompt_pack.duration_seconds,
        },
        ensure_ascii=False,
    )


def _word_count(value: str) -> int:
    return len([word for word in value.split() if word.strip()])


def _get_or_raise(session: Session, model: type[models.Base], entity_id: int):
    entity = session.get(model, entity_id)
    if entity is None:
        raise ValueError(f"{model.__name__} not found: {entity_id}")
    return entity

