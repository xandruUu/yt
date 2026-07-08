from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.core.enums import ExternalToolJobStatus, ScriptStatus, VoiceoverJobStatus
from app.db import models
from app.db.repositories import add_and_commit, create_external_tool_job, create_voiceover_job
from app.services.cost_tracking_service import record_cost_event
from app.tts import (
    ElevenLabsTTSProvider,
    LocalTTSProvider,
    ManualVoiceProvider,
    OpenAITTSProvider,
    PlaceholderVoiceProvider,
    TTSProvider,
)
from app.utils.safe_paths import safe_join


def get_tts_providers() -> dict[str, TTSProvider]:
    providers: list[TTSProvider] = [
        PlaceholderVoiceProvider(),
        ManualVoiceProvider(),
        LocalTTSProvider(),
        OpenAITTSProvider(),
        ElevenLabsTTSProvider(),
    ]
    return {provider.name: provider for provider in providers}


def list_tts_provider_statuses(language: str = "es") -> list[dict[str, object]]:
    rows = []
    for provider in get_tts_providers().values():
        rows.append(
            {
                "provider": provider.name,
                "available": provider.is_available(),
                "reason": provider.availability_reason(),
                "voices": [voice.__dict__ for voice in provider.list_voices(language)],
            }
        )
    return rows


def create_voiceover_from_script(
    session: Session,
    *,
    script_id: int,
    provider_name: str = "placeholder",
    language: str | None = None,
    voice_id: str | None = None,
    wizard_session_id: int | None = None,
    allow_paid: bool = False,
    model_id: str | None = None,
    with_timestamps: bool = True,
) -> models.VoiceoverJob:
    script = _get_approved_script(session, script_id)
    provider = _provider_or_error(provider_name)
    text = _script_text(script)
    language = language or script.language

    if provider.name == "manual_recording":
        return create_voiceover_job(
            session,
            wizard_session_id=wizard_session_id,
            script_id=script.id,
            language=language,
            provider=provider.name,
            voice_name="Grabacion manual pendiente",
            voice_id=voice_id or "manual_upload",
            input_text=text,
            status=VoiceoverJobStatus.PENDING.value,
            metadata_json=json.dumps({"provider_reason": provider.availability_reason()}, ensure_ascii=False),
        )

    output_path = _voiceover_output_dir(script.id) / f"{provider.name}.mp3"
    result = provider.synthesize(
        text=text,
        voice_id=voice_id,
        output_path=output_path,
        language=language,
        metadata={
            "script_id": script.id,
            "confirmed_paid": allow_paid,
            "model_id": model_id,
            "with_timestamps": with_timestamps,
        },
    )
    status = VoiceoverJobStatus.GENERATED.value if result.ok else VoiceoverJobStatus.FAILED.value
    if provider.name == "placeholder" and result.ok:
        status = VoiceoverJobStatus.PLACEHOLDER.value
    metadata = dict(result.metadata)
    cost_estimate = _metadata_float(metadata, "estimated_cost")
    job = create_voiceover_job(
        session,
        wizard_session_id=wizard_session_id,
        script_id=script.id,
        language=language,
        provider=result.provider,
        voice_name=result.voice_name,
        voice_id=result.voice_id,
        input_text=text,
        output_audio_path=result.audio_path,
        duration_seconds=result.duration_seconds or script.estimated_duration_seconds,
        status=status,
        error_message=result.error_message,
        cost_estimate=cost_estimate,
        metadata_json=json.dumps(metadata, ensure_ascii=False),
    )
    if provider.name == "elevenlabs_tts":
        _record_elevenlabs_audit_rows(
            session,
            voiceover_job=job,
            request_payload={
                "script_id": script.id,
                "voice_id": voice_id,
                "model_id": model_id,
                "language": language,
                "input_chars": len(text),
                "with_timestamps": with_timestamps,
                "confirmed_paid": allow_paid,
            },
            response_payload=metadata,
            estimated_cost=cost_estimate,
            actual_cost=_metadata_float(metadata, "actual_cost"),
            ok=result.ok,
            error_message=result.error_message,
        )
    return job


def import_manual_voiceover(
    session: Session,
    *,
    script_id: int,
    file_path: str | Path,
    language: str | None = None,
    wizard_session_id: int | None = None,
    duration_seconds: float | None = None,
    overwrite: bool = False,
) -> models.VoiceoverJob:
    script = _get_approved_script(session, script_id)
    provider = ManualVoiceProvider()
    text = _script_text(script)
    result = provider.import_audio(
        source_path=file_path,
        destination_dir=_voiceover_output_dir(script.id),
        overwrite=overwrite,
        duration_seconds=duration_seconds or script.estimated_duration_seconds,
    )
    return create_voiceover_job(
        session,
        wizard_session_id=wizard_session_id,
        script_id=script.id,
        language=language or script.language,
        provider=result.provider,
        voice_name=result.voice_name,
        voice_id=result.voice_id,
        input_text=text,
        output_audio_path=result.audio_path,
        duration_seconds=result.duration_seconds or script.estimated_duration_seconds,
        status=VoiceoverJobStatus.IMPORTED_MANUAL.value,
        metadata_json=json.dumps(result.metadata, ensure_ascii=False),
    )


def approve_voiceover(session: Session, voiceover_job_id: int) -> models.VoiceoverJob:
    job = _get_voiceover_job(session, voiceover_job_id)
    if job.status == VoiceoverJobStatus.FAILED.value:
        raise ValueError("No se puede aprobar una voz fallida.")
    job.status = VoiceoverJobStatus.APPROVED.value
    job.error_message = None
    return add_and_commit(session, job)


def reject_voiceover(
    session: Session,
    voiceover_job_id: int,
    reason: str | None = None,
) -> models.VoiceoverJob:
    job = _get_voiceover_job(session, voiceover_job_id)
    job.status = VoiceoverJobStatus.REJECTED.value
    job.error_message = reason or "Rechazada en revision humana."
    return add_and_commit(session, job)


def _get_approved_script(session: Session, script_id: int) -> models.Script:
    script = session.get(models.Script, script_id)
    if script is None:
        raise ValueError(f"Script not found: {script_id}")
    if script.status != ScriptStatus.APPROVED.value:
        raise ValueError("El guion debe estar aprobado antes de generar voz.")
    return script


def _get_voiceover_job(session: Session, voiceover_job_id: int) -> models.VoiceoverJob:
    job = session.get(models.VoiceoverJob, voiceover_job_id)
    if job is None:
        raise ValueError(f"Voiceover job not found: {voiceover_job_id}")
    return job


def _provider_or_error(provider_name: str) -> TTSProvider:
    providers = get_tts_providers()
    try:
        return providers[provider_name]
    except KeyError as exc:
        raise ValueError(f"Unknown TTS provider: {provider_name}") from exc


def _script_text(script: models.Script) -> str:
    if script.script_text.strip():
        return script.script_text.strip()
    return "\n".join(line.text.strip() for line in script.lines if line.text.strip())


def _voiceover_output_dir(script_id: int) -> Path:
    settings = get_settings()
    return safe_join(settings.output_dir, "voiceovers", f"script_{script_id}")


def _metadata_float(metadata: dict[str, object], key: str) -> float | None:
    value = metadata.get(key)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _record_elevenlabs_audit_rows(
    session: Session,
    *,
    voiceover_job: models.VoiceoverJob,
    request_payload: dict[str, object],
    response_payload: dict[str, object],
    estimated_cost: float | None,
    actual_cost: float | None,
    ok: bool,
    error_message: str | None,
) -> None:
    create_external_tool_job(
        session,
        wizard_session_id=voiceover_job.wizard_session_id,
        script_id=voiceover_job.script_id,
        provider_name="elevenlabs",
        provider_type="api",
        job_type="tts",
        status=ExternalToolJobStatus.COMPLETED.value if ok else ExternalToolJobStatus.FAILED.value,
        request_json=json.dumps(request_payload, ensure_ascii=False),
        response_json=json.dumps(response_payload, ensure_ascii=False),
        output_path=voiceover_job.output_audio_path,
        error_message=error_message,
        estimated_cost=estimated_cost,
        actual_cost=actual_cost,
    )
    record_cost_event(
        session,
        provider_name="elevenlabs",
        operation="tts",
        model=str(response_payload.get("model_id") or request_payload.get("model_id") or ""),
        estimated_cost=estimated_cost,
        actual_cost=actual_cost,
        units_type="characters",
        input_units=float(request_payload.get("input_chars") or 0),
        metadata={
            "voiceover_job_id": voiceover_job.id,
            "with_timestamps": request_payload.get("with_timestamps"),
            "ok": ok,
        },
    )
