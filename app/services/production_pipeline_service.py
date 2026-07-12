from __future__ import annotations

import json
import urllib.request
from pathlib import Path

from sqlalchemy import select
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
from app.external_tools.higgsfield.client import (
    HiggsfieldClient,
    HiggsfieldStatus,
    create_generation_job,
    estimate_generation_cost,
    get_generation_job,
    wait_generation_job,
)
from app.services.character_locker_service import character_reference_images
from app.services.project_status_service import refresh_video_project_status

SCRIPT_SYSTEM_PROMPT = """You are the head writer of a YouTube Shorts factory.
The UI is Spanish, but the full script and every creative output must be English.
Write fast, clear, voiceover-ready English for a 45-90 second short.
Return valid JSON only."""

SCENE_SYSTEM_PROMPT = """You are a cinematic scene planner for vertical YouTube Shorts.
The UI is Spanish, but all scene descriptions and video prompts must be English.
Build compatible scene slots from the approved script and character references.
Each Higgsfield clip must be 7 to 15 seconds.
Return valid JSON only."""

ACTIVE_HIGGSFIELD_JOB_STATUSES = (
    "cost_estimated",
    "pending_confirmation",
    "submitted",
    "running",
    "manual_required",
)

ACTIVE_HIGGSFIELD_PROMPT_PACK_STATUSES = (
    "generated",
    "draft",
    "pending_confirmation",
    "ready",
)


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
    add_and_commit(session, project)
    return refresh_video_project_status(session, project.id)


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
    refresh_video_project_status(session, project.id)
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
    if project is not None:
        refresh_video_project_status(session, project.id)
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
                duration_seconds=min(
                    candidate_payload.duration_seconds,
                    get_settings().higgsfield_max_scene_duration_seconds,
                ),
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
    refresh_video_project_status(session, project.id)
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
    refresh_video_project_status(session, selected.video_project_id)
    return selected


def create_prompt_pack_for_selected_scene(
    session: Session,
    *,
    selected_scene_id: int,
    force_new_pack: bool = False,
) -> models.HiggsfieldPromptPack:
    existing_pack = find_active_higgsfield_prompt_pack(session, selected_scene_id=selected_scene_id)
    if existing_pack is not None and not force_new_pack:
        return existing_pack

    selected = _get_or_raise(session, models.SelectedScene, selected_scene_id)
    candidate = _get_or_raise(session, models.SceneCandidate, selected.scene_candidate_id)
    project = _get_or_raise(session, models.VideoProject, selected.video_project_id)
    character = (
        session.get(models.CharacterProfile, project.character_profile_id)
        if project.character_profile_id
        else None
    )
    references = character_reference_images(session, character.id) if character else []
    prompt = _higgsfield_prompt(project, character, candidate)
    negative = _negative_prompt(character)
    pack = create_higgsfield_prompt_pack(
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
    refresh_video_project_status(session, project.id)
    return pack


def check_higgsfield_status() -> HiggsfieldStatus:
    return HiggsfieldClient().check_status()


def generate_clip_from_scene(
    session: Session,
    *,
    selected_scene_id: int,
    confirmed_credits: bool = False,
    force_new_attempt: bool = False,
) -> models.HiggsfieldJob:
    prompt_pack = _prompt_pack_for_scene(session, selected_scene_id)
    existing_job = find_active_higgsfield_job(
        session,
        selected_scene_id=prompt_pack.selected_scene_id,
        prompt_pack_id=prompt_pack.id,
    )
    if existing_job is not None and not force_new_attempt:
        return existing_job

    status = check_higgsfield_status()
    estimated_credits = max(1.0, prompt_pack.duration_seconds / 8.0 * 2.0)
    if (
        estimated_credits > get_settings().higgsfield_confirm_credits_above
        and not confirmed_credits
    ):
        job = create_higgsfield_job(
            session,
            video_project_id=prompt_pack.video_project_id,
            selected_scene_id=prompt_pack.selected_scene_id,
            prompt_pack_id=prompt_pack.id,
            automation_mode=status.mode,
            submitted_payload_json=_job_payload(prompt_pack),
            status="pending_confirmation",
            error_message="Payload preparado; no se ha enviado a Higgsfield. Requiere confirmacion explicita.",
            estimated_credits=estimated_credits,
        )
        refresh_video_project_status(session, prompt_pack.video_project_id)
        return job
    if not status.available:
        job = create_higgsfield_job(
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
        refresh_video_project_status(session, prompt_pack.video_project_id)
        return job
    job = create_higgsfield_job(
        session,
        video_project_id=prompt_pack.video_project_id,
        selected_scene_id=prompt_pack.selected_scene_id,
        prompt_pack_id=prompt_pack.id,
        automation_mode=status.mode,
        submitted_payload_json=_job_payload(prompt_pack),
        status="pending_confirmation",
        error_message="Payload preparado; no se ha enviado todavia a Higgsfield CLI/MCP.",
        estimated_credits=estimated_credits,
    )
    refresh_video_project_status(session, prompt_pack.video_project_id)
    return job


def estimate_higgsfield_cost_for_scene(
    session: Session,
    *,
    selected_scene_id: int,
    model_name: str | None = None,
    duration_seconds: int | None = None,
    aspect_ratio: str | None = None,
) -> models.HiggsfieldJob:
    prompt_pack = _prompt_pack_for_scene(session, selected_scene_id)
    supersede_stale_higgsfield_jobs(
        session,
        selected_scene_id=prompt_pack.selected_scene_id,
        prompt_pack_id=prompt_pack.id,
    )
    existing_job = find_active_higgsfield_job(
        session,
        selected_scene_id=prompt_pack.selected_scene_id,
        prompt_pack_id=prompt_pack.id,
    )
    settings = get_settings()
    chosen_model = model_name or settings.higgsfield_default_model
    chosen_duration = int(duration_seconds or settings.higgsfield_default_test_duration_seconds)
    chosen_aspect_ratio = (
        aspect_ratio or prompt_pack.aspect_ratio or settings.higgsfield_default_aspect_ratio
    )
    cost = estimate_generation_cost(
        prompt=prompt_pack.prompt,
        model_name=chosen_model,
        duration_seconds=chosen_duration,
        aspect_ratio=chosen_aspect_ratio,
        generate_audio=False,
    )
    payload_json = _job_payload(
        prompt_pack,
        model_name=chosen_model,
        duration_seconds=chosen_duration,
        aspect_ratio=chosen_aspect_ratio,
    )
    job = existing_job or models.HiggsfieldJob(
        video_project_id=prompt_pack.video_project_id,
        selected_scene_id=prompt_pack.selected_scene_id,
        prompt_pack_id=prompt_pack.id,
        automation_mode="cli",
    )
    job.status = "cost_estimated"
    job.model_name = chosen_model
    job.requested_duration_seconds = float(chosen_duration)
    job.requested_aspect_ratio = chosen_aspect_ratio
    job.cost_estimate_credits = cost.credits
    job.estimated_credits = cost.credits
    job.confirmed_credits = False
    job.submitted_payload_json = payload_json
    job.cli_command_json = json.dumps(cost.cli_result.command, ensure_ascii=False)
    job.cli_response_json = _cli_result_json(cost.cli_result)
    job.error_message = None
    if existing_job is None:
        session.add(job)
    session.commit()
    session.refresh(job)
    return job


def submit_higgsfield_job_for_scene(
    session: Session,
    *,
    higgsfield_job_id: int,
    confirmed_credits: bool,
    allow_stale_balance: bool = False,
) -> models.HiggsfieldJob:
    job = _get_or_raise(session, models.HiggsfieldJob, higgsfield_job_id)
    settings = get_settings()
    if not settings.higgsfield_real_generation_enabled:
        raise ValueError("HIGGSFIELD_REAL_GENERATION_ENABLED=false. No se puede gastar creditos.")
    if not confirmed_credits:
        raise ValueError("Falta confirmacion explicita para gastar creditos.")
    if job.cost_estimate_credits is None and job.estimated_credits is None:
        raise ValueError("Estima el coste antes de enviar a Higgsfield.")
    credits = float(job.cost_estimate_credits or job.estimated_credits or 0)
    if credits > settings.higgsfield_known_credit_balance and not allow_stale_balance:
        raise ValueError("El coste estimado supera el saldo conocido local.")
    if job.external_job_id:
        return job

    prompt_pack = _get_or_raise(session, models.HiggsfieldPromptPack, job.prompt_pack_id)
    try:
        result = create_generation_job(
            prompt=prompt_pack.prompt,
            confirmed_credits=True,
            model_name=job.model_name or settings.higgsfield_default_model,
            aspect_ratio=job.requested_aspect_ratio or prompt_pack.aspect_ratio,
            duration_seconds=int(
                job.requested_duration_seconds or settings.higgsfield_default_test_duration_seconds
            ),
            generate_audio=False,
            real_generation_enabled=True,
        )
    except Exception as exc:
        job.status = "failed"
        job.error_message = str(exc)
        session.commit()
        session.refresh(job)
        raise

    job.external_job_id = result.external_job_id
    job.status = result.raw.get("status") or result.raw.get("state") or "submitted"
    job.confirmed_credits = True
    job.submitted_at = models.now_utc()
    job.started_at = job.started_at or job.submitted_at
    job.cli_command_json = json.dumps(result.cli_result.command, ensure_ascii=False)
    job.cli_response_json = _cli_result_json(result.cli_result)
    job.result_json = json.dumps(result.raw, ensure_ascii=False)
    job.output_url = result.output_url
    job.error_message = None
    session.commit()
    session.refresh(job)
    refresh_video_project_status(session, job.video_project_id)
    return job


def refresh_higgsfield_job_status(
    session: Session,
    *,
    higgsfield_job_id: int,
    wait: bool = False,
) -> models.HiggsfieldJob:
    job = _get_or_raise(session, models.HiggsfieldJob, higgsfield_job_id)
    if not job.external_job_id:
        raise ValueError("El job no tiene external_job_id.")
    try:
        result = (
            wait_generation_job(job.external_job_id)
            if wait
            else get_generation_job(job.external_job_id)
        )
    except Exception as exc:
        job.status = "failed"
        job.error_message = str(exc)
        session.commit()
        session.refresh(job)
        return job

    status = result.status or job.status
    job.status = status
    job.cli_command_json = json.dumps(result.cli_result.command, ensure_ascii=False)
    job.cli_response_json = _cli_result_json(result.cli_result)
    job.result_json = json.dumps(result.raw, ensure_ascii=False)
    job.output_url = result.output_url or job.output_url
    job.error_message = None
    if _is_completed_higgsfield_status(status) or job.output_url:
        job.completed_at = models.now_utc()
        job.finished_at = job.finished_at or job.completed_at
    session.commit()
    session.refresh(job)
    refresh_video_project_status(session, job.video_project_id)
    return job


def register_higgsfield_output_as_generated_clip(
    session: Session,
    *,
    higgsfield_job_id: int,
    download_output: bool | None = None,
) -> models.GeneratedClip:
    job = _get_or_raise(session, models.HiggsfieldJob, higgsfield_job_id)
    if not job.external_job_id:
        raise ValueError("El job no tiene external_job_id.")
    if not job.output_url and not job.output_path:
        raise ValueError("El job no tiene output_url ni output_path.")
    settings = get_settings()
    should_download = (
        settings.higgsfield_download_outputs if download_output is None else download_output
    )
    path_or_url = job.output_path or job.output_url or ""
    notes = ""
    if job.output_url and should_download:
        try:
            path_or_url = str(_download_higgsfield_output(settings.output_dir, job))
            job.output_path = path_or_url
        except Exception as exc:  # noqa: BLE001 - keep remote output usable.
            path_or_url = job.output_url
            notes = f"No se pudo descargar automaticamente: {exc}"

    existing_clip = session.scalar(
        select(models.GeneratedClip)
        .where(models.GeneratedClip.higgsfield_job_id == job.id)
        .order_by(models.GeneratedClip.created_at.desc())
    )
    clip = existing_clip or models.GeneratedClip(
        video_project_id=job.video_project_id,
        selected_scene_id=job.selected_scene_id,
        prompt_pack_id=job.prompt_pack_id,
        higgsfield_job_id=job.id,
        file_path=path_or_url,
    )
    clip.video_project_id = job.video_project_id
    clip.selected_scene_id = job.selected_scene_id
    clip.prompt_pack_id = job.prompt_pack_id
    clip.higgsfield_job_id = job.id
    clip.external_job_id = job.external_job_id
    clip.source = "higgsfield"
    clip.asset_type = "video"
    clip.file_path = path_or_url
    clip.duration_seconds = job.requested_duration_seconds
    clip.license_type = "generated_owned"
    clip.commercial_use_confirmed = True
    clip.notes = notes or "Registrado desde output Higgsfield."
    clip.metadata_json = job.result_json
    clip.status = "ready" if _local_path_exists(path_or_url) else "registered_remote"
    if existing_clip is None:
        session.add(clip)
    job.status = "registered"
    session.commit()
    session.refresh(clip)
    refresh_video_project_status(session, job.video_project_id)
    return clip


def supersede_stale_higgsfield_jobs(
    session: Session,
    *,
    selected_scene_id: int,
    prompt_pack_id: int | None = None,
) -> int:
    statement = select(models.HiggsfieldJob).where(
        models.HiggsfieldJob.selected_scene_id == selected_scene_id,
        models.HiggsfieldJob.status == "created",
        models.HiggsfieldJob.external_job_id.is_(None),
    )
    if prompt_pack_id is not None:
        statement = statement.where(models.HiggsfieldJob.prompt_pack_id == prompt_pack_id)
    jobs = list(session.scalars(statement).all())
    for job in jobs:
        job.status = "superseded"
        job.error_message = "Job interno antiguo sustituido por el flujo canónico de coste/envio."
    session.commit()
    return len(jobs)


def find_active_higgsfield_job(
    session: Session,
    *,
    selected_scene_id: int,
    prompt_pack_id: int,
) -> models.HiggsfieldJob | None:
    return session.scalar(
        select(models.HiggsfieldJob)
        .where(
            models.HiggsfieldJob.selected_scene_id == selected_scene_id,
            models.HiggsfieldJob.prompt_pack_id == prompt_pack_id,
            models.HiggsfieldJob.status.in_(ACTIVE_HIGGSFIELD_JOB_STATUSES),
        )
        .order_by(models.HiggsfieldJob.created_at.desc())
    )


def find_active_higgsfield_prompt_pack(
    session: Session,
    *,
    selected_scene_id: int,
) -> models.HiggsfieldPromptPack | None:
    return session.scalar(
        select(models.HiggsfieldPromptPack)
        .where(
            models.HiggsfieldPromptPack.selected_scene_id == selected_scene_id,
            models.HiggsfieldPromptPack.status.in_(ACTIVE_HIGGSFIELD_PROMPT_PACK_STATUSES),
        )
        .order_by(models.HiggsfieldPromptPack.created_at.desc())
    )


def _prompt_pack_for_scene(session: Session, selected_scene_id: int) -> models.HiggsfieldPromptPack:
    existing = find_active_higgsfield_prompt_pack(session, selected_scene_id=selected_scene_id)
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
            {
                "purpose": "hook",
                "start_second": 0,
                "end_second": 8,
                "text": "Opening curiosity hook.",
            },
            {
                "purpose": "setup",
                "start_second": 8,
                "end_second": 22,
                "text": "Set up the visual mystery.",
            },
            {
                "purpose": "payoff",
                "start_second": 22,
                "end_second": 38,
                "text": "Reveal the surprising explanation.",
            },
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
        character.prompt_fragment or character.canonical_description
        if character
        else "A consistent friendly host character"
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


def _job_payload(
    prompt_pack: models.HiggsfieldPromptPack,
    *,
    model_name: str | None = None,
    duration_seconds: int | float | None = None,
    aspect_ratio: str | None = None,
) -> str:
    return json.dumps(
        {
            "model_name": model_name or get_settings().higgsfield_default_model,
            "prompt": prompt_pack.prompt,
            "negative_prompt": prompt_pack.negative_prompt,
            "reference_images": json.loads(prompt_pack.reference_images_json or "[]"),
            "aspect_ratio": aspect_ratio or prompt_pack.aspect_ratio,
            "duration_seconds": duration_seconds or prompt_pack.duration_seconds,
            "generate_audio": False,
        },
        ensure_ascii=False,
    )


def _cli_result_json(cli_result) -> str:
    return json.dumps(
        {
            "command": cli_result.command,
            "stdout": cli_result.stdout,
            "stderr": cli_result.stderr,
            "returncode": cli_result.returncode,
            "data": cli_result.data,
            "error": cli_result.error,
        },
        ensure_ascii=False,
    )


def _download_higgsfield_output(output_root: Path, job: models.HiggsfieldJob) -> Path:
    if not job.output_url:
        raise ValueError("El job no tiene output_url.")
    folder = output_root / "higgsfield" / f"project_{job.video_project_id}"
    folder.mkdir(parents=True, exist_ok=True)
    destination = folder / f"scene_{job.selected_scene_id}_{job.external_job_id or job.id}.mp4"
    with urllib.request.urlopen(job.output_url, timeout=120) as response:
        destination.write_bytes(response.read())
    return destination


def _local_path_exists(value: str | None) -> bool:
    if not value or value.startswith(("http://", "https://")):
        return False
    return Path(value).exists()


def _is_completed_higgsfield_status(status: str | None) -> bool:
    return (status or "").lower() in {
        "completed",
        "complete",
        "succeeded",
        "success",
        "finished",
        "done",
        "ready",
    }


def _word_count(value: str) -> int:
    return len([word for word in value.split() if word.strip()])


def _get_or_raise(session: Session, model: type[models.Base], entity_id: int):
    entity = session.get(model, entity_id)
    if entity is None:
        raise ValueError(f"{model.__name__} not found: {entity_id}")
    return entity
