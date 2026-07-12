from __future__ import annotations

import json
from pathlib import Path

import streamlit as st
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models
from app.db.database import new_session
from app.db.repositories import add_and_commit, create_generated_clip
from app.services.production_pipeline_service import find_active_higgsfield_prompt_pack

CLIP_STATUSES = ("imported", "mapped", "ready", "failed", "registered")


def render() -> None:
    st.title("Mapeo de clips")
    st.caption("Asocia clips reales a escenas seleccionadas del flujo canonico.")
    with new_session() as session:
        project = _select_project(session)
        if project is None:
            st.info("Crea tu primer proyecto desde Investigacion -> Creacion -> Ideas.")
            return

        _render_project_summary(project)
        selected_scenes = _selected_scenes(session, project.id)
        if not selected_scenes:
            st.info("Selecciona escenas en Produccion antes de mapear clips.")
            return

        for selected_scene in selected_scenes:
            _render_scene_mapping(session, selected_scene)


def upsert_generated_clip_for_scene(
    session: Session,
    *,
    selected_scene_id: int,
    file_path: str,
    asset_type: str,
    provider: str,
    duration_seconds: float | None,
    status: str,
    license_type: str | None,
    commercial_use_confirmed: bool,
    notes: str | None,
    prompt_pack_id: int | None = None,
    higgsfield_job_id: int | None = None,
    create_new_version: bool = False,
) -> models.GeneratedClip:
    selected = session.get(models.SelectedScene, selected_scene_id)
    if selected is None:
        raise ValueError(f"SelectedScene not found: {selected_scene_id}")
    clean_path = file_path.strip()
    if not clean_path:
        raise ValueError("Indica la ruta local del clip o imagen.")
    if not Path(clean_path).exists():
        raise ValueError(f"No existe el archivo local: {clean_path}")

    prompt_pack_id = prompt_pack_id or _latest_prompt_pack(session, selected_scene_id)
    higgsfield_job_id = higgsfield_job_id or _latest_higgsfield_job_id(session, selected_scene_id)
    existing = None if create_new_version else _latest_generated_clip(session, selected_scene_id)
    metadata = {
        "asset_type": asset_type,
        "provider": provider,
        "license_type": license_type,
        "commercial_use_confirmed": commercial_use_confirmed,
        "notes": notes,
    }
    payload = {
        "video_project_id": selected.video_project_id,
        "selected_scene_id": selected.id,
        "prompt_pack_id": prompt_pack_id,
        "higgsfield_job_id": higgsfield_job_id,
        "external_job_id": _job_external_id(session, higgsfield_job_id),
        "asset_type": asset_type,
        "source": provider,
        "file_path": clean_path,
        "duration_seconds": duration_seconds,
        "license_type": license_type,
        "commercial_use_confirmed": commercial_use_confirmed,
        "notes": notes,
        "metadata_json": json.dumps(metadata, ensure_ascii=False),
        "status": status,
    }
    if existing is None:
        clip = create_generated_clip(session, **payload)
    else:
        for key, value in payload.items():
            setattr(existing, key, value)
        clip = add_and_commit(session, existing)
    if clip.status in {"imported", "mapped", "ready", "registered"}:
        selected.status = "mapped"
        session.commit()
    return clip


def _select_project(session: Session) -> models.VideoProject | None:
    projects = list(
        session.scalars(
            select(models.VideoProject).order_by(models.VideoProject.created_at.desc())
        ).all()
    )
    if not projects:
        return None
    project_id = st.selectbox(
        "Proyecto",
        [project.id for project in projects],
        format_func=lambda value: _project_label(
            next(project for project in projects if project.id == value)
        ),
    )
    return session.get(models.VideoProject, int(project_id))


def _render_project_summary(project: models.VideoProject) -> None:
    st.subheader(project.title)
    cols = st.columns(4)
    cols[0].metric("Estado", project.status)
    cols[1].metric("Idioma", project.content_language)
    cols[2].metric("Duracion objetivo", f"{project.target_duration_seconds}s")
    cols[3].metric("Proyecto", f"#{project.id}")
    st.write(f"**Hook:** {project.hook}")
    st.write(project.description)


def _render_scene_mapping(session: Session, selected: models.SelectedScene) -> None:
    slot = session.get(models.SceneSlot, selected.scene_slot_id)
    candidate = session.get(models.SceneCandidate, selected.scene_candidate_id)
    prompt_pack = find_active_higgsfield_prompt_pack(session, selected_scene_id=selected.id)
    jobs = _higgsfield_jobs(session, selected.id)
    clips = _generated_clips(session, selected.id)

    with st.container(border=True):
        st.markdown(
            f"**SelectedScene #{selected.id} | orden {selected.sort_order} | {selected.status}**"
        )
        if slot is not None:
            st.caption(f"SceneSlot {slot.slot_number} / {slot.slot_type}: {slot.voiceover_segment}")
        if candidate is not None:
            st.write(candidate.visual_description)
            st.caption(
                f"Opcion {candidate.option_code} | {candidate.duration_seconds}s | {candidate.camera_movement}"
            )

        _render_prompt_pack(prompt_pack)
        _render_jobs(jobs)
        _render_clips(clips)
        _render_clip_form(session, selected, prompt_pack, jobs, candidate)


def _render_prompt_pack(prompt_pack: models.HiggsfieldPromptPack | None) -> None:
    st.markdown("**Prompt pack**")
    if prompt_pack is None:
        st.info("No hay prompt pack para esta escena. Crealo desde Produccion -> Higgsfield.")
        return
    st.caption(
        f"PromptPack #{prompt_pack.id} | {prompt_pack.status} | "
        f"{prompt_pack.aspect_ratio} | {prompt_pack.duration_seconds}s"
    )
    with st.expander("Ver prompt Higgsfield", expanded=False):
        st.code(prompt_pack.prompt, language="markdown")
        st.caption(f"Negative: {prompt_pack.negative_prompt}")


def _render_jobs(jobs: list[models.HiggsfieldJob]) -> None:
    st.markdown("**Jobs Higgsfield internos**")
    if not jobs:
        st.info("No hay jobs internos para esta escena.")
        return
    st.warning(
        "Estos jobs son internos/pendientes. Todavia no son generaciones reales enviadas a Higgsfield."
    )
    st.dataframe(
        [
            {
                "id": job.id,
                "status": job.status,
                "automation_mode": job.automation_mode,
                "estimated_credits": job.estimated_credits,
                "external_job_id": job.external_job_id,
                "error": job.error_message,
                "created_at": job.created_at,
            }
            for job in jobs
        ],
        use_container_width=True,
        hide_index=True,
    )


def _render_clips(clips: list[models.GeneratedClip]) -> None:
    st.markdown("**Clips asociados**")
    if not clips:
        st.info("Todavia no hay GeneratedClip asociado.")
        return
    st.dataframe(
        [
            {
                "id": clip.id,
                "source": clip.source,
                "asset_type": clip.asset_type,
                "status": clip.status,
                "path": clip.file_path,
                "duration": clip.duration_seconds,
                "license": clip.license_type,
                "commercial": clip.commercial_use_confirmed,
            }
            for clip in clips
        ],
        use_container_width=True,
        hide_index=True,
    )


def _render_clip_form(
    session: Session,
    selected: models.SelectedScene,
    prompt_pack: models.HiggsfieldPromptPack | None,
    jobs: list[models.HiggsfieldJob],
    candidate: models.SceneCandidate | None,
) -> None:
    with st.form(f"generated_clip_form_{selected.id}"):
        st.markdown("**Importar clip local como GeneratedClip**")
        file_path = st.text_input("Ruta local del clip/imagen")
        col1, col2, col3 = st.columns(3)
        asset_type = col1.selectbox(
            "Tipo", ["video", "image"], key=f"clip_asset_type_{selected.id}"
        )
        provider = col2.selectbox(
            "Proveedor", ["higgsfield", "manual", "picsart"], key=f"clip_provider_{selected.id}"
        )
        status = col3.selectbox("Estado", CLIP_STATUSES, index=1, key=f"clip_status_{selected.id}")
        duration = st.number_input(
            "Duracion en segundos",
            min_value=0.0,
            value=float(candidate.duration_seconds if candidate else 8.0),
            step=0.5,
            key=f"clip_duration_{selected.id}",
        )
        job_options = {"Sin job": None}
        job_options.update({f"Job #{job.id} [{job.status}]": job.id for job in jobs})
        selected_job = st.selectbox(
            "HiggsfieldJob asociado", list(job_options), key=f"clip_job_{selected.id}"
        )
        license_type = st.selectbox(
            "Licencia",
            ["generated_owned", "manual_owned", "unknown"],
            key=f"clip_license_{selected.id}",
        )
        commercial = st.checkbox(
            "Uso comercial confirmado", value=True, key=f"clip_commercial_{selected.id}"
        )
        notes = st.text_area("Notas", key=f"clip_notes_{selected.id}")
        create_new_version = st.checkbox(
            "Crear nueva version aunque ya exista un clip para esta escena",
            key=f"clip_new_version_{selected.id}",
        )
        if st.form_submit_button("Guardar GeneratedClip"):
            try:
                clip = upsert_generated_clip_for_scene(
                    session,
                    selected_scene_id=selected.id,
                    file_path=file_path,
                    asset_type=asset_type,
                    provider=provider,
                    duration_seconds=float(duration) or None,
                    status=status,
                    license_type=license_type,
                    commercial_use_confirmed=commercial,
                    notes=notes.strip() or None,
                    prompt_pack_id=prompt_pack.id if prompt_pack else None,
                    higgsfield_job_id=job_options[selected_job],
                    create_new_version=create_new_version,
                )
            except ValueError as exc:
                st.error(str(exc))
                return
            st.success(f"GeneratedClip #{clip.id} guardado.")
            st.rerun()


def _selected_scenes(session: Session, project_id: int) -> list[models.SelectedScene]:
    return list(
        session.scalars(
            select(models.SelectedScene)
            .where(models.SelectedScene.video_project_id == project_id)
            .order_by(models.SelectedScene.sort_order)
        ).all()
    )


def _higgsfield_jobs(session: Session, selected_scene_id: int) -> list[models.HiggsfieldJob]:
    return list(
        session.scalars(
            select(models.HiggsfieldJob)
            .where(models.HiggsfieldJob.selected_scene_id == selected_scene_id)
            .order_by(models.HiggsfieldJob.created_at.desc())
        ).all()
    )


def _generated_clips(session: Session, selected_scene_id: int) -> list[models.GeneratedClip]:
    return list(
        session.scalars(
            select(models.GeneratedClip)
            .where(models.GeneratedClip.selected_scene_id == selected_scene_id)
            .order_by(models.GeneratedClip.created_at.desc())
        ).all()
    )


def _latest_generated_clip(session: Session, selected_scene_id: int) -> models.GeneratedClip | None:
    return session.scalar(
        select(models.GeneratedClip)
        .where(models.GeneratedClip.selected_scene_id == selected_scene_id)
        .order_by(models.GeneratedClip.created_at.desc())
    )


def _latest_prompt_pack(session: Session, selected_scene_id: int) -> int | None:
    pack = find_active_higgsfield_prompt_pack(session, selected_scene_id=selected_scene_id)
    return pack.id if pack else None


def _latest_higgsfield_job_id(session: Session, selected_scene_id: int) -> int | None:
    job = session.scalar(
        select(models.HiggsfieldJob)
        .where(models.HiggsfieldJob.selected_scene_id == selected_scene_id)
        .order_by(models.HiggsfieldJob.created_at.desc())
    )
    return job.id if job else None


def _job_external_id(session: Session, job_id: int | None) -> str | None:
    if job_id is None:
        return None
    job = session.get(models.HiggsfieldJob, job_id)
    return job.external_job_id if job else None


def _project_label(project: models.VideoProject) -> str:
    return f"#{project.id} | {project.title[:60]} | {project.status} | {project.content_language}"
