from __future__ import annotations

import json
from pathlib import Path

import streamlit as st
from sqlalchemy import select

from app.config.settings import get_settings
from app.core.enums import ScriptStatus
from app.db import models
from app.db.database import new_session
from app.services.clip_library_service import list_external_assets, set_external_asset_license
from app.services.cost_tracking_service import cost_summary, estimate_cost
from app.services.external_asset_import_service import import_external_asset
from app.services.external_tool_service import list_external_tool_statuses
from app.services.prompt_pack_service import (
    create_higgsfield_prompt_pack,
    create_picsart_prompt_pack,
    mark_prompt_pack_used_manually,
)
from app.services.voiceover_generation_service import (
    approve_voiceover,
    create_voiceover_from_script,
)


def render() -> None:
    st.title("Herramientas externas")
    tabs = st.tabs(["Estado", "ElevenLabs", "Higgsfield", "Picsart", "Paquetes", "Clips", "Costes"])
    with tabs[0]:
        _render_status_tab()
    with tabs[1]:
        _render_elevenlabs_tab()
    with tabs[2]:
        _render_higgsfield_tab()
    with tabs[3]:
        _render_picsart_tab()
    with tabs[4]:
        _render_prompt_packs_tab()
    with tabs[5]:
        _render_clips_tab()
    with tabs[6]:
        _render_costs_tab()


def _render_status_tab() -> None:
    st.subheader("Estado de integraciones")
    st.dataframe(list_external_tool_statuses(), use_container_width=True, hide_index=True)
    st.caption("Las claves API se leen desde .env y nunca se guardan en la base de datos.")


def _render_elevenlabs_tab() -> None:
    st.subheader("ElevenLabs")
    settings = get_settings()
    cols = st.columns(4)
    cols[0].metric(
        "Provider",
        "activo" if settings.enable_elevenlabs or settings.enable_elevenlabs_tts else "inactivo",
    )
    cols[1].metric("API key", "configured" if settings.elevenlabs_api_key else "missing")
    cols[2].metric("Voice ID", _mask_secret(settings.elevenlabs_default_voice_id))
    cols[3].metric("Modelo", settings.elevenlabs_model_id)
    st.caption(
        "Esta accion puede consumir creditos de ElevenLabs. Confirma la generacion antes de llamar a la API."
    )
    script = _select_approved_script("external_elevenlabs_script")
    if script is None:
        st.info("Aprueba un guion antes de generar voz.")
        return
    script_text = script.script_text or "\n".join(line.text for line in script.lines)
    cost = estimate_cost("elevenlabs", "tts", {"text": script_text})
    cols = st.columns(3)
    voice_id = cols[0].text_input("Voice ID", value=settings.elevenlabs_default_voice_id)
    model_id = cols[1].text_input("Modelo", value=settings.elevenlabs_model_id)
    with_timestamps = cols[2].checkbox("Intentar timing", value=True)
    st.metric("Caracteres", len(script_text))
    if cost["estimated_cost"] is None:
        st.warning("Puede generar coste. No hay tarifa configurada; revisa tu plan de ElevenLabs.")
    else:
        st.warning(
            f"Puede generar coste estimado: {cost['estimated_cost']:.4f} {cost['currency']}."
        )
    st.caption("Comprueba licencia comercial del plan antes de monetizar.")
    confirmed = st.checkbox(
        "Esta accion puede consumir creditos de ElevenLabs. Confirmo la generacion."
    )
    if st.button("Generar voz con ElevenLabs", type="primary"):
        with new_session() as session:
            job = create_voiceover_from_script(
                session,
                script_id=script.id,
                provider_name="elevenlabs_tts",
                language=script.language,
                voice_id=voice_id or None,
                allow_paid=confirmed,
                model_id=model_id or None,
                with_timestamps=with_timestamps,
            )
        if job.status == "failed":
            st.error(job.error_message)
        else:
            st.success(f"VoiceoverJob #{job.id} generado.")
    _render_voiceover_jobs(script.id)


def _mask_secret(value: str | None) -> str:
    if not value:
        return "missing"
    clean = value.strip()
    if len(clean) <= 8:
        return "***"
    return f"{clean[:4]}...{clean[-4:]}"


def _render_higgsfield_tab() -> None:
    st.subheader("Higgsfield manual")
    st.info(
        "Modulo legacy/manual: esta pantalla usa Script + VisualPlan del flujo antiguo. "
        "Para el flujo canonico basado en VideoProject usa Produccion -> Higgsfield."
    )
    selection = _select_script_and_visual_plan("higgsfield")
    if selection is None:
        st.info("Necesitas un guion aprobado y un plan visual legacy para generar prompt packs.")
        return
    script, visual_plan = selection
    if st.button("Generar prompt pack Higgsfield", type="primary"):
        with new_session() as session:
            pack = create_higgsfield_prompt_pack(
                session,
                script_id=script.id,
                visual_plan_id=visual_plan.id,
                overwrite=True,
            )
        st.success(f"PromptPack #{pack.id} generado.")
        st.code(pack.folder_path)
    st.caption("Genera los clips fuera, descargalos e importalos en la pestaña Clips.")


def _render_picsart_tab() -> None:
    st.subheader("Picsart manual/API opcional")
    selection = _select_script_and_visual_plan("picsart")
    if selection is None:
        st.info(
            "Necesitas un guion aprobado y un plan visual para generar instrucciones de procesado."
        )
        return
    script, visual_plan = selection
    if st.button("Generar processing pack Picsart", type="primary"):
        with new_session() as session:
            pack = create_picsart_prompt_pack(
                session,
                script_id=script.id,
                visual_plan_id=visual_plan.id,
                overwrite=True,
            )
        st.success(f"PromptPack #{pack.id} generado.")
        st.code(pack.folder_path)
    st.caption(
        "La API queda preparada como proveedor opcional; sin PICSART_API_KEY se usa handoff manual."
    )


def _render_prompt_packs_tab() -> None:
    st.subheader("Paquetes de prompts")
    with new_session() as session:
        packs = session.scalars(
            select(models.PromptPack).order_by(models.PromptPack.created_at.desc())
        ).all()
        if not packs:
            st.info("Todavia no hay prompt packs.")
            return
        for pack in packs:
            with st.container(border=True):
                st.markdown(f"**PromptPack #{pack.id}: {pack.title}**")
                st.caption(f"{pack.provider_name} | {pack.pack_type} | {pack.status}")
                st.code(pack.folder_path)
                if st.button("Marcar usado manualmente", key=f"pack_used_{pack.id}"):
                    mark_prompt_pack_used_manually(session, pack.id)
                    st.rerun()


def _render_clips_tab() -> None:
    st.subheader("Importar clips/assets externos")
    script = _select_approved_script("external_asset_script", allow_none=True)
    visual_plan = _select_visual_plan(
        "external_asset_visual", script.id if script else None, allow_none=True
    )
    col1, col2, col3 = st.columns(3)
    file_path = col1.text_input("Ruta local del archivo")
    asset_type = col2.selectbox("Tipo", ["video", "image", "audio", "sfx"])
    provider_name = col3.selectbox("Proveedor", ["higgsfield", "picsart", "elevenlabs", "manual"])
    scene_order = st.number_input("Escena", min_value=0, value=0)
    license_type = st.text_input("Licencia")
    commercial = st.checkbox("Uso comercial confirmado")
    license_notes = st.text_area("Notas de licencia")
    if st.button("Importar asset externo", type="primary"):
        try:
            with new_session() as session:
                asset = import_external_asset(
                    session,
                    file_path=file_path,
                    asset_type=asset_type,
                    provider_name=provider_name,
                    script_id=script.id if script else None,
                    visual_plan_id=visual_plan.id if visual_plan else None,
                    scene_order=int(scene_order) or None,
                    license_info={
                        "source": provider_name,
                        "license_type": license_type or None,
                        "commercial_use_confirmed": commercial,
                        "license_notes": license_notes or None,
                    },
                    overwrite=True,
                )
            st.success(f"ExternalAsset #{asset.id} importado.")
        except Exception as exc:  # noqa: BLE001 - Streamlit muestra el bloqueo concreto.
            st.error(str(exc))
    _render_external_assets_table()


def _render_external_assets_table() -> None:
    st.subheader("Biblioteca externa")
    with new_session() as session:
        assets = list_external_assets(session)
        if not assets:
            st.info("No hay clips/assets importados.")
            return
        for asset in assets:
            with st.container(border=True):
                st.markdown(f"**ExternalAsset #{asset.id}**")
                st.caption(f"{asset.provider_name} | {asset.asset_type} | {asset.status}")
                st.write(asset.file_path)
                if asset.asset_type == "video" and Path(asset.file_path).exists():
                    st.video(asset.file_path)
                elif asset.asset_type == "image" and Path(asset.file_path).exists():
                    st.image(asset.file_path)
                license_type = st.text_input(
                    "Licencia", value=asset.license_type or "", key=f"asset_license_{asset.id}"
                )
                commercial = st.checkbox(
                    "Uso comercial confirmado",
                    value=asset.commercial_use_confirmed,
                    key=f"asset_commercial_{asset.id}",
                )
                notes = st.text_area(
                    "Notas", value=asset.license_notes or "", key=f"asset_notes_{asset.id}"
                )
                if st.button("Guardar licencia", key=f"asset_save_license_{asset.id}"):
                    set_external_asset_license(
                        session,
                        external_asset_id=asset.id,
                        license_type=license_type,
                        commercial_use_confirmed=commercial,
                        license_notes=notes,
                    )
                    st.rerun()


def _render_costs_tab() -> None:
    st.subheader("Costes")
    with new_session() as session:
        summary = cost_summary(session)
        cols = st.columns(3)
        cols[0].metric("Eventos", summary.event_count)
        cols[1].metric("Estimado", f"{summary.estimated_total:.4f} {summary.currency}")
        cols[2].metric("Real", f"{summary.actual_total:.4f} {summary.currency}")
        events = session.scalars(
            select(models.CostEvent).order_by(models.CostEvent.created_at.desc())
        ).all()
        st.dataframe(
            [
                {
                    "id": event.id,
                    "provider": event.provider_name,
                    "operation": event.operation,
                    "model": event.model,
                    "estimated": event.estimated_cost,
                    "actual": event.actual_cost,
                    "currency": event.currency,
                    "units": event.input_units,
                    "metadata": json.loads(event.metadata_json or "{}"),
                }
                for event in events
            ],
            use_container_width=True,
            hide_index=True,
        )


def _render_voiceover_jobs(script_id: int) -> None:
    with new_session() as session:
        jobs = session.scalars(
            select(models.VoiceoverJob)
            .where(models.VoiceoverJob.script_id == script_id)
            .order_by(models.VoiceoverJob.created_at.desc())
        ).all()
        for job in jobs:
            with st.container(border=True):
                st.markdown(f"**VoiceoverJob #{job.id}**")
                st.caption(f"{job.provider} | {job.status} | coste estimado: {job.cost_estimate}")
                if job.output_audio_path and Path(job.output_audio_path).exists():
                    st.audio(job.output_audio_path)
                if job.error_message:
                    st.warning(job.error_message)
                if st.button("Aprobar voz", key=f"external_approve_voice_{job.id}"):
                    try:
                        approve_voiceover(session, job.id)
                    except ValueError as exc:
                        st.error(str(exc))
                        return
                    st.rerun()


def _select_approved_script(key: str, allow_none: bool = False) -> models.Script | None:
    with new_session() as session:
        scripts = session.scalars(
            select(models.Script)
            .where(models.Script.status == ScriptStatus.APPROVED.value)
            .order_by(models.Script.created_at.desc())
        ).all()
        if not scripts:
            return None
        options = {"Ninguno": None} if allow_none else {}
        options.update(
            {
                f"#{script.id} {script.topic.title} [{script.language}]": script.id
                for script in scripts
            }
        )
        selected = st.selectbox("Guion aprobado", list(options), key=key)
        script_id = options[selected]
        return session.get(models.Script, script_id) if script_id else None


def _select_visual_plan(
    key: str, script_id: int | None, allow_none: bool = False
) -> models.VisualPlan | None:
    with new_session() as session:
        statement = select(models.VisualPlan).order_by(models.VisualPlan.created_at.desc())
        if script_id:
            statement = statement.where(models.VisualPlan.script_id == script_id)
        plans = session.scalars(statement).all()
        if not plans:
            return None
        options = {"Ninguno": None} if allow_none else {}
        options.update(
            {f"#{plan.id} {plan.template_name} [{plan.status}]": plan.id for plan in plans}
        )
        selected = st.selectbox("Plan visual", list(options), key=key)
        plan_id = options[selected]
        return session.get(models.VisualPlan, plan_id) if plan_id else None


def _select_script_and_visual_plan(
    key_prefix: str,
) -> tuple[models.Script, models.VisualPlan] | None:
    script = _select_approved_script(f"{key_prefix}_script")
    if script is None:
        return None
    visual_plan = _select_visual_plan(f"{key_prefix}_visual", script.id)
    if visual_plan is None:
        return None
    return script, visual_plan
