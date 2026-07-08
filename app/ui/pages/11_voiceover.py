from __future__ import annotations

from pathlib import Path

import streamlit as st
from sqlalchemy import select

from app.config.settings import get_settings
from app.core.enums import ScriptStatus, VoiceoverJobStatus
from app.db import models
from app.db.database import new_session
from app.services.cost_tracking_service import estimate_cost
from app.services.voiceover_generation_service import (
    approve_voiceover,
    create_voiceover_from_script,
    import_manual_voiceover,
    list_tts_provider_statuses,
    reject_voiceover,
)


def render() -> None:
    st.title("Voces")
    script = _select_approved_script()
    if script is None:
        st.info("Aprueba un guion antes de asociar voz.")
        return

    st.caption(f"Guion aprobado: #{script['id']} [{script['language']}]")
    with st.expander("Proveedores disponibles"):
        st.dataframe(list_tts_provider_statuses(str(script["language"])), use_container_width=True, hide_index=True)

    mode = st.radio(
        "Modo",
        ["placeholder", "manual_recording", "local_tts", "openai_tts", "elevenlabs_tts"],
        format_func=_provider_label,
        horizontal=True,
    )
    if mode == "manual_recording":
        file_path = st.text_input("Ruta del archivo de voz")
        duration = st.number_input(
            "Duracion en segundos",
            min_value=1.0,
            value=float(script["duration"] or 30),
            step=0.5,
        )
        if st.button("Importar voz manual", type="primary"):
            try:
                with new_session() as session:
                    job = import_manual_voiceover(
                        session,
                        script_id=int(script["id"]),
                        file_path=file_path,
                        duration_seconds=float(duration),
                        overwrite=True,
                    )
                st.success(f"VoiceoverJob #{job.id} importado.")
            except Exception as exc:  # noqa: BLE001 - Streamlit debe mostrar el error.
                st.error(str(exc))
    elif mode == "elevenlabs_tts":
        settings = get_settings()
        script_text = str(script.get("script_text") or "")
        cost = estimate_cost("elevenlabs", "tts", {"text": script_text})
        col1, col2 = st.columns(2)
        voice_id = col1.text_input("Voice ID", value=settings.elevenlabs_default_voice_id)
        model_id = col2.text_input("Modelo", value=settings.elevenlabs_model_id)
        with_timestamps = st.checkbox("Intentar timing/alignment", value=True)
        if cost["estimated_cost"] is None:
            st.warning("Puede generar coste. No hay tarifa configurada; revisa tu plan de ElevenLabs.")
        else:
            st.warning(f"Coste estimado: {cost['estimated_cost']:.4f} {cost['currency']}.")
        confirmed = st.checkbox("Confirmo operacion potencialmente de pago")
        if st.button("Generar voz con ElevenLabs", type="primary"):
            with new_session() as session:
                job = create_voiceover_from_script(
                    session,
                    script_id=int(script["id"]),
                    provider_name=mode,
                    language=str(script["language"]),
                    voice_id=voice_id or None,
                    allow_paid=confirmed,
                    model_id=model_id or None,
                    with_timestamps=with_timestamps,
                )
            if job.status == VoiceoverJobStatus.FAILED.value:
                st.error(job.error_message)
            else:
                st.success(f"VoiceoverJob #{job.id} creado.")
    else:
        label = "Continuar sin voz" if mode == "placeholder" else "Intentar generar TTS"
        if st.button(label, type="primary"):
            with new_session() as session:
                job = create_voiceover_from_script(
                    session,
                    script_id=int(script["id"]),
                    provider_name=mode,
                    language=str(script["language"]),
                )
            if job.status == VoiceoverJobStatus.FAILED.value:
                st.error(job.error_message)
            else:
                st.success(f"VoiceoverJob #{job.id} creado.")

    _render_voiceover_jobs(int(script["id"]))


def _select_approved_script() -> dict[str, object] | None:
    with new_session() as session:
        scripts = session.scalars(
            select(models.Script)
            .where(models.Script.status == ScriptStatus.APPROVED.value)
            .order_by(models.Script.created_at.desc())
        ).all()
        if not scripts:
            return None
        options = {f"#{script.id} {script.topic.title} [{script.language}]": script.id for script in scripts}
        selected = st.selectbox("Guion aprobado", list(options))
        script = session.get(models.Script, options[selected])
        return {
            "id": script.id,
            "language": script.language,
            "duration": script.estimated_duration_seconds,
            "script_text": script.script_text,
        }


def _render_voiceover_jobs(script_id: int) -> None:
    st.subheader("VoiceoverJobs")
    with new_session() as session:
        jobs = session.scalars(
            select(models.VoiceoverJob)
            .where(models.VoiceoverJob.script_id == script_id)
            .order_by(models.VoiceoverJob.created_at.desc())
        ).all()
        if not jobs:
            st.info("Todavia no hay voces para este guion.")
            return
        for job in jobs:
            with st.container(border=True):
                st.markdown(f"**VoiceoverJob #{job.id}**")
                st.caption(f"{job.provider} | {job.status} | {job.duration_seconds or '-'}s")
                if job.output_audio_path:
                    st.write(job.output_audio_path)
                    if Path(job.output_audio_path).exists():
                        st.audio(job.output_audio_path)
                if job.error_message:
                    st.warning(job.error_message)
                actions = st.columns(2)
                if actions[0].button("Aprobar", key=f"voice_page_approve_{job.id}"):
                    try:
                        approve_voiceover(session, job.id)
                    except ValueError as exc:
                        st.error(str(exc))
                        return
                    st.success("Voz aprobada.")
                    st.rerun()
                if actions[1].button("Rechazar", key=f"voice_page_reject_{job.id}"):
                    reject_voiceover(session, job.id)
                    st.rerun()


def _provider_label(value: str) -> str:
    return {
        "placeholder": "Sin voz / placeholder",
        "manual_recording": "Grabacion manual",
        "local_tts": "TTS local opcional",
        "openai_tts": "OpenAI TTS opcional",
        "elevenlabs_tts": "ElevenLabs opcional",
    }.get(value, value)
