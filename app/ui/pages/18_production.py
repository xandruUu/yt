from __future__ import annotations

import json

import streamlit as st
from sqlalchemy import select

from app.config.settings import get_settings
from app.db import models
from app.db.database import new_session
from app.services.character_service import seed_nero_character_system
from app.services.production_pipeline_service import (
    approve_script_draft,
    check_higgsfield_status,
    create_prompt_pack_for_selected_scene,
    estimate_higgsfield_cost_for_scene,
    find_active_higgsfield_job,
    find_active_higgsfield_prompt_pack,
    generate_script_for_project,
    plan_scenes_for_project,
    refresh_higgsfield_job_status,
    register_higgsfield_output_as_generated_clip,
    select_character_for_project,
    select_scene_candidate,
    submit_higgsfield_job_for_scene,
)
from app.services.voiceover_service import create_voiceover, estimate_voiceover_cost_or_usage


def render() -> None:
    st.title("Produccion")
    st.caption("Personaje, guion en ingles, voz, escenas y preparacion Higgsfield.")
    with new_session() as session:
        seed_nero_character_system(session)
        projects = list(
            session.scalars(
                select(models.VideoProject)
                .order_by(models.VideoProject.created_at.desc())
                .limit(30)
            ).all()
        )
        if not projects:
            st.info("Todavia no hay VideoProjects. Crea uno desde Ideas.")
            return
        project_id = st.selectbox(
            "Proyecto",
            [project.id for project in projects],
            format_func=lambda value: _project_label(
                next(project for project in projects if project.id == value)
            ),
        )
        project = session.get(models.VideoProject, int(project_id))
        if project is None:
            return
        _project_summary(project)
        st.divider()
        _character_panel(session, project)
        st.divider()
        _script_panel(session, project)
        st.divider()
        _voiceover_panel(session, project)
        st.divider()
        _scene_panel(session, project)
        st.divider()
        _higgsfield_panel(session, project)


def _project_summary(project: models.VideoProject) -> None:
    st.subheader(project.title)
    cols = st.columns(4)
    cols[0].metric("Estado", project.status)
    cols[1].metric("Idioma contenido", project.content_language)
    cols[2].metric("Duracion objetivo", f"{project.target_duration_seconds}s")
    cols[3].metric("Max", f"{project.max_duration_seconds}s")
    st.write(f"**Hook:** {project.hook}")
    st.write(project.description)
    st.caption(" ".join(_json_loads(project.hashtags_json)))


def _character_panel(session, project: models.VideoProject) -> None:
    st.subheader("1. Personaje")
    characters = list(
        session.scalars(
            select(models.CharacterProfile).order_by(models.CharacterProfile.name)
        ).all()
    )
    options = {f"{character.name} ({character.slug})": character.id for character in characters}
    current = project.character_profile_id or (characters[0].id if characters else None)
    if current is None:
        st.warning("No hay personajes.")
        return
    labels = list(options)
    index = list(options.values()).index(current) if current in options.values() else 0
    selected_label = st.selectbox("Selector locker room", labels, index=index)
    if st.button("Seleccionar personaje para proyecto"):
        select_character_for_project(
            session, video_project_id=project.id, character_profile_id=options[selected_label]
        )
        st.success("Personaje seleccionado.")
        st.rerun()


def _script_panel(session, project: models.VideoProject) -> None:
    st.subheader("2. Guion")
    scripts = _scripts(session, project.id)
    if st.button(
        "Generar guion en ingles", type="primary", disabled=project.character_profile_id is None
    ):
        script = generate_script_for_project(session, video_project_id=project.id)
        st.success(f"ScriptDraft #{script.id} generado.")
        st.rerun()
    if not scripts:
        st.info("Genera un guion despues de seleccionar personaje.")
        return
    script = scripts[0]
    st.caption(
        f"Estado: {script.status} | {script.estimated_words} words | {script.estimated_duration_seconds}s"
    )
    st.text_area("Voiceover text", value=script.voiceover_text, height=220, disabled=True)
    with st.expander("Beats"):
        st.json(_json_loads(script.beats_json))
    if script.status != "script_approved" and st.button(
        "Aprobar guion", key=f"approve_script_{script.id}"
    ):
        try:
            approve_script_draft(session, script.id)
        except ValueError as exc:
            st.error(str(exc))
        else:
            st.success("Guion aprobado.")
            st.rerun()


def _voiceover_panel(session, project: models.VideoProject) -> None:
    st.subheader("3. Voz")
    script = _approved_script(session, project.id)
    if script is None:
        st.info("Aprueba el guion antes de generar voz.")
        return
    estimate = estimate_voiceover_cost_or_usage(script.voiceover_text)
    cols = st.columns(3)
    cols[0].metric("Caracteres", estimate.character_count)
    cols[1].metric("Proveedor", estimate.provider)
    cols[2].metric("Coste estimado", f"${estimate.estimated_cost_usd:.2f}")
    allow_paid = st.checkbox("Confirmo posible uso de creditos ElevenLabs", value=False)
    if st.button("Generar voz con ElevenLabs / fallback", type="primary"):
        if estimate.requires_confirmation and not allow_paid:
            st.error("Este job requiere confirmacion de coste.")
            return
        job = create_voiceover(
            session,
            video_project_id=project.id,
            script_draft_id=script.id,
            allow_paid=allow_paid,
        )
        st.success(f"VoiceoverJob #{job.id}: {job.status}")
        st.rerun()
    jobs = _voiceovers(session, project.id)
    if jobs:
        st.dataframe(
            [
                {
                    "id": job.id,
                    "provider": job.provider,
                    "status": job.status,
                    "path": job.output_path or job.output_audio_path,
                    "chars": job.character_count,
                }
                for job in jobs
            ],
            use_container_width=True,
            hide_index=True,
        )


def _scene_panel(session, project: models.VideoProject) -> None:
    st.subheader("4. Escenas")
    if _approved_script(session, project.id) is None:
        st.info("Aprueba guion antes de planificar escenas.")
        return
    if st.button("Planificar escenas compatibles", type="primary"):
        slots = plan_scenes_for_project(session, video_project_id=project.id)
        st.success(f"{len(slots)} scene slots creados.")
        st.rerun()
    slots = _scene_slots(session, project.id)
    if not slots:
        return
    for slot in slots:
        with st.container(border=True):
            st.markdown(f"**Escena {slot.slot_number} - {slot.slot_type}**")
            st.caption(f"{slot.target_start_second:.1f}s - {slot.target_end_second:.1f}s")
            candidates = _scene_candidates(session, slot.id)
            for candidate in candidates:
                st.write(f"**{candidate.option_code}:** {candidate.visual_description}")
                st.caption(
                    f"{candidate.duration_seconds}s | {candidate.camera_movement} | {candidate.status}"
                )
                if candidate.status != "selected" and st.button(
                    f"Seleccionar {candidate.option_code}",
                    key=f"select_scene_{candidate.id}",
                ):
                    selected = select_scene_candidate(session, scene_candidate_id=candidate.id)
                    st.success(f"SelectedScene #{selected.id} creada.")
                    st.rerun()


def _higgsfield_panel(session, project: models.VideoProject) -> None:
    st.subheader("5. Higgsfield")
    settings = get_settings()
    status = check_higgsfield_status()
    st.caption(f"Modo: {status.mode} | Disponible: {status.available} | {status.detail}")
    if settings.higgsfield_real_generation_enabled:
        st.error("Modo real activado: enviar jobs puede consumir creditos de Higgsfield.")
    else:
        st.warning(
            "Modo seguro: la generacion real esta desactivada. "
            "Puedes estimar costes, pero no enviar jobs reales."
        )
    selected_scenes = _selected_scenes(session, project.id)
    if not selected_scenes:
        st.info("Selecciona escenas antes de generar prompt packs.")
        return
    for selected in selected_scenes:
        with st.container(border=True):
            st.markdown(f"**SelectedScene #{selected.id}**")
            prompt_pack = find_active_higgsfield_prompt_pack(session, selected_scene_id=selected.id)
            force_new_pack = False
            if prompt_pack is not None:
                st.info(f"Prompt pack existente: #{prompt_pack.id} [{prompt_pack.status}]")
                force_new_pack = st.checkbox(
                    "Regenerar prompt pack aunque ya exista",
                    key=f"higgs_force_pack_{selected.id}_{prompt_pack.id}",
                )
                existing_job = find_active_higgsfield_job(
                    session,
                    selected_scene_id=selected.id,
                    prompt_pack_id=prompt_pack.id,
                )
                if existing_job is not None:
                    _render_higgsfield_job_summary(existing_job)
                    _render_higgsfield_clip_summary(session, existing_job)
                else:
                    st.caption("Sin HiggsfieldJob activo para este prompt pack.")
            else:
                existing_job = None

            model_name = st.selectbox(
                "Modelo seleccionado",
                ["veo3_1_lite", "seedance_2_0_mini", "wan2_7", "kling3_0_turbo"],
                index=0,
                key=f"higgs_model_{selected.id}",
            )
            duration_seconds = st.selectbox(
                "Duracion seleccionada",
                [4, 6, 8],
                index=0,
                key=f"higgs_duration_{selected.id}",
            )
            aspect_ratio = st.selectbox(
                "Aspect ratio",
                ["9:16", "16:9", "1:1", "4:3", "3:4", "auto"],
                index=0,
                key=f"higgs_aspect_{selected.id}",
            )
            cols = st.columns(3)
            cols[0].metric("Saldo conocido local", f"{settings.higgsfield_known_credit_balance:g}")
            cols[1].metric(
                "Coste estimado",
                _credits_label(existing_job.cost_estimate_credits if existing_job else None),
            )
            cols[2].metric(
                "external_job_id",
                existing_job.external_job_id
                if existing_job and existing_job.external_job_id
                else "-",
            )

            if st.button("Ver/crear prompt pack", key=f"pack_{selected.id}"):
                pack = create_prompt_pack_for_selected_scene(
                    session,
                    selected_scene_id=selected.id,
                    force_new_pack=force_new_pack,
                )
                st.success(f"HiggsfieldPromptPack #{pack.id}: {pack.status}")
                st.rerun()

            if st.button(
                "Estimar coste Higgsfield",
                key=f"higgs_estimate_{selected.id}",
            ):
                try:
                    job = estimate_higgsfield_cost_for_scene(
                        session,
                        selected_scene_id=selected.id,
                        model_name=model_name,
                        duration_seconds=int(duration_seconds),
                        aspect_ratio=aspect_ratio,
                    )
                except Exception as exc:  # noqa: BLE001 - Streamlit should show the failure.
                    st.error(str(exc))
                    return
                st.success(f"HiggsfieldJob #{job.id}: coste {job.cost_estimate_credits:g} creditos")
                st.rerun()

            if existing_job is None:
                continue

            estimated_credits = existing_job.cost_estimate_credits or existing_job.estimated_credits
            confirmed = st.checkbox(
                f"Confirmo gastar {_credits_label(estimated_credits)} creditos en Higgsfield para esta escena",
                key=f"higgs_confirm_{existing_job.id}",
            )
            stale_needed = bool(
                estimated_credits is not None
                and estimated_credits > settings.higgsfield_known_credit_balance
            )
            allow_stale = st.checkbox(
                "Permitir envio aunque el saldo local pueda estar desactualizado",
                value=False,
                disabled=not stale_needed,
                key=f"higgs_allow_stale_{existing_job.id}",
            )
            can_submit = (
                settings.higgsfield_real_generation_enabled
                and estimated_credits is not None
                and confirmed
                and (not stale_needed or allow_stale)
                and not existing_job.external_job_id
            )
            if st.button(
                "Enviar a Higgsfield",
                type="primary",
                disabled=not can_submit,
                key=f"higgs_submit_{existing_job.id}",
            ):
                try:
                    job = submit_higgsfield_job_for_scene(
                        session,
                        higgsfield_job_id=existing_job.id,
                        confirmed_credits=confirmed,
                        allow_stale_balance=allow_stale,
                    )
                except Exception as exc:  # noqa: BLE001 - Streamlit should show the failure.
                    st.error(str(exc))
                    return
                st.success(f"HiggsfieldJob #{job.id} enviado: {job.external_job_id}")
                st.rerun()

            state_cols = st.columns(3)
            if state_cols[0].button(
                "Consultar estado Higgsfield",
                disabled=not bool(existing_job.external_job_id),
                key=f"higgs_get_{existing_job.id}",
            ):
                job = refresh_higgsfield_job_status(
                    session,
                    higgsfield_job_id=existing_job.id,
                    wait=False,
                )
                st.success(f"Estado actualizado: {job.status}")
                st.rerun()
            if state_cols[1].button(
                "Esperar resultado",
                disabled=not bool(existing_job.external_job_id),
                key=f"higgs_wait_{existing_job.id}",
            ):
                job = refresh_higgsfield_job_status(
                    session,
                    higgsfield_job_id=existing_job.id,
                    wait=True,
                )
                st.success(f"Estado actualizado: {job.status}")
                st.rerun()
            if state_cols[2].button(
                "Registrar output como GeneratedClip",
                disabled=not bool(existing_job.output_url or existing_job.output_path),
                key=f"higgs_register_{existing_job.id}",
            ):
                clip = register_higgsfield_output_as_generated_clip(
                    session,
                    higgsfield_job_id=existing_job.id,
                )
                st.success(f"GeneratedClip #{clip.id}: {clip.status}")
                st.rerun()
    packs = _prompt_packs(session, project.id)
    if packs:
        with st.expander("Prompt packs generados", expanded=False):
            for pack in packs:
                st.markdown(f"**Pack #{pack.id} - SelectedScene {pack.selected_scene_id}**")
                st.code(pack.prompt, language="markdown")
                st.caption(f"Negative: {pack.negative_prompt}")


def _render_higgsfield_job_summary(job: models.HiggsfieldJob) -> None:
    st.info(f"HiggsfieldJob #{job.id} [{job.status}]")
    rows = {
        "PromptPack": job.prompt_pack_id,
        "Modelo": job.model_name or "-",
        "Duracion": job.requested_duration_seconds or "-",
        "Aspect ratio": job.requested_aspect_ratio or "-",
        "Coste estimado": _credits_label(job.cost_estimate_credits or job.estimated_credits),
        "external_job_id": job.external_job_id or "-",
        "output_url": job.output_url or "-",
        "output_path": job.output_path or "-",
    }
    st.dataframe(
        [{"campo": key, "valor": value} for key, value in rows.items()],
        use_container_width=True,
        hide_index=True,
    )
    if job.error_message:
        st.warning(job.error_message)


def _render_higgsfield_clip_summary(session, job: models.HiggsfieldJob) -> None:
    clip = session.scalar(
        select(models.GeneratedClip)
        .where(models.GeneratedClip.higgsfield_job_id == job.id)
        .order_by(models.GeneratedClip.created_at.desc())
    )
    if clip is None:
        st.caption("GeneratedClip asociado: -")
        return
    st.success(f"GeneratedClip asociado: #{clip.id} [{clip.status}]")
    st.caption(clip.file_path)


def _credits_label(value: float | None) -> str:
    return "-" if value is None else f"{float(value):g}"


def _scripts(session, project_id: int) -> list[models.ScriptDraft]:
    return list(
        session.scalars(
            select(models.ScriptDraft)
            .where(models.ScriptDraft.video_project_id == project_id)
            .order_by(models.ScriptDraft.created_at.desc())
        ).all()
    )


def _approved_script(session, project_id: int) -> models.ScriptDraft | None:
    return session.scalar(
        select(models.ScriptDraft)
        .where(
            models.ScriptDraft.video_project_id == project_id,
            models.ScriptDraft.status == "script_approved",
        )
        .order_by(models.ScriptDraft.created_at.desc())
    )


def _voiceovers(session, project_id: int) -> list[models.VoiceoverJob]:
    return list(
        session.scalars(
            select(models.VoiceoverJob)
            .where(models.VoiceoverJob.video_project_id == project_id)
            .order_by(models.VoiceoverJob.created_at.desc())
        ).all()
    )


def _scene_slots(session, project_id: int) -> list[models.SceneSlot]:
    return list(
        session.scalars(
            select(models.SceneSlot)
            .where(models.SceneSlot.video_project_id == project_id)
            .order_by(models.SceneSlot.slot_number)
        ).all()
    )


def _scene_candidates(session, slot_id: int) -> list[models.SceneCandidate]:
    return list(
        session.scalars(
            select(models.SceneCandidate)
            .where(models.SceneCandidate.scene_slot_id == slot_id)
            .order_by(models.SceneCandidate.option_code)
        ).all()
    )


def _selected_scenes(session, project_id: int) -> list[models.SelectedScene]:
    return list(
        session.scalars(
            select(models.SelectedScene)
            .where(models.SelectedScene.video_project_id == project_id)
            .order_by(models.SelectedScene.sort_order)
        ).all()
    )


def _prompt_packs(session, project_id: int) -> list[models.HiggsfieldPromptPack]:
    return list(
        session.scalars(
            select(models.HiggsfieldPromptPack)
            .where(models.HiggsfieldPromptPack.video_project_id == project_id)
            .order_by(models.HiggsfieldPromptPack.created_at.desc())
        ).all()
    )


def _latest_prompt_pack_for_selected_scene(
    session, selected_scene_id: int
) -> models.HiggsfieldPromptPack | None:
    return session.scalar(
        select(models.HiggsfieldPromptPack)
        .where(models.HiggsfieldPromptPack.selected_scene_id == selected_scene_id)
        .order_by(models.HiggsfieldPromptPack.created_at.desc())
    )


def _project_label(project: models.VideoProject) -> str:
    return f"#{project.id} | {project.status} | {project.title}"


def _json_loads(value: str | None):
    try:
        decoded = json.loads(value or "[]")
    except json.JSONDecodeError:
        decoded = []
    return decoded if isinstance(decoded, list) else []
