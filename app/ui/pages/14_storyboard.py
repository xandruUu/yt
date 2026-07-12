from __future__ import annotations

import json

import streamlit as st
from sqlalchemy import select

from app.core.enums import ScriptStatus
from app.db import models
from app.db.database import new_session
from app.db.repositories import add_and_commit
from app.services.character_service import seed_nero_character_system
from app.services.storyboard_prompt_pack_service import create_nero_higgsfield_prompt_pack
from app.services.storyboard_service import (
    VisualStoryboardService,
    list_storyboard_scenes,
    list_storyboards_for_script,
)


def render() -> None:
    st.title("Storyboard Nero")
    with new_session() as session:
        script = _select_approved_script(session)
        if script is None:
            st.info("Aprueba un guion antes de generar storyboard.")
            return
        character = seed_nero_character_system(session)
        st.caption(
            f"Guion #{script.id} | {script.topic.title if script.topic else 'Sin tema'} | Personaje: {character.name}"
        )
        col1, col2 = st.columns(2)
        if col1.button("Generar storyboard Nero", type="primary"):
            storyboard = VisualStoryboardService().create_from_script(
                session,
                script_id=script.id,
                character_id=character.id,
                overwrite_existing=True,
            )
            st.success(f"Storyboard #{storyboard.id} generado.")
            st.rerun()
        storyboards = list_storyboards_for_script(session, script.id)
        if not storyboards:
            st.info("Todavia no hay storyboard para este guion.")
            return
        options = {f"Storyboard #{item.id} [{item.status}]": item.id for item in storyboards}
        selected = col2.selectbox("Storyboard", list(options))
        storyboard = session.get(models.VisualStoryboard, options[selected])
        if storyboard is None:
            st.error("Storyboard no encontrado.")
            return
        _render_storyboard(session, storyboard)


def _select_approved_script(session) -> models.Script | None:
    scripts = session.scalars(
        select(models.Script)
        .where(models.Script.status == ScriptStatus.APPROVED.value)
        .order_by(models.Script.created_at.desc())
    ).all()
    if not scripts:
        return None
    options = {
        f"#{script.id} {script.topic.title if script.topic else 'Sin tema'} [{script.language}]": script.id
        for script in scripts
    }
    selected = st.selectbox("Guion aprobado", list(options))
    return session.get(models.Script, options[selected])


def _render_storyboard(session, storyboard: models.VisualStoryboard) -> None:
    st.subheader(f"VisualStoryboard #{storyboard.id}")
    cols = st.columns(4)
    cols[0].metric("Escenas", storyboard.total_scenes)
    cols[1].metric("Duracion", storyboard.target_duration_seconds)
    cols[2].metric("Aspect", storyboard.aspect_ratio)
    cols[3].metric("Estado", storyboard.status)
    if st.button("Exportar prompt pack estructurado"):
        pack = create_nero_higgsfield_prompt_pack(
            session, storyboard_id=storyboard.id, overwrite=True
        )
        st.success(f"PromptPack #{pack.id} creado.")
        st.code(pack.folder_path)
    if st.button("Aprobar storyboard"):
        VisualStoryboardService().approve_storyboard(session, storyboard.id)
        st.rerun()
    for scene in list_storyboard_scenes(session, storyboard.id):
        _render_scene_editor(session, scene)


def _render_scene_editor(session, scene: models.StoryboardScene) -> None:
    with st.container(border=True):
        st.markdown(f"**Escena {scene.scene_number:02}**")
        with st.form(f"scene_form_{scene.id}"):
            safe_duration, duration_max = safe_duration_bounds(scene.duration_seconds)
            duration = st.number_input(
                "Duracion",
                min_value=0.5,
                max_value=duration_max,
                value=safe_duration,
                step=0.5,
                key=f"storyboard_scene_duration_{scene.id}",
            )
            narration = st.text_area("Linea de guion", value=scene.narration_line, height=70)
            action = st.text_area("Accion de Nero", value=scene.on_screen_action, height=90)
            col1, col2, col3 = st.columns(3)
            pose = col1.text_input("Pose", value=scene.character_pose)
            emotion = col2.text_input("Emocion", value=scene.character_emotion)
            variant = col3.text_input("Variante", value=scene.character_variant or "")
            camera_shot = st.text_input("Plano", value=scene.camera_shot)
            camera_motion = st.text_input("Camara/movimiento", value=scene.camera_motion)
            background = st.text_area("Fondo", value=scene.background, height=80)
            props = st.text_input(
                "Props separados por coma", value=", ".join(json.loads(scene.props_json or "[]"))
            )
            prompt = st.text_area("Prompt Higgsfield", value=scene.higgsfield_prompt, height=220)
            negative = st.text_area("Negative prompt", value=scene.negative_prompt, height=120)
            status_options = [
                "generated",
                "edited",
                "approved",
                "needs_asset",
                "mapped",
                "rejected",
                "archived",
            ]
            status = st.selectbox(
                "Estado",
                status_options,
                index=status_options.index(scene.status) if scene.status in status_options else 0,
            )
            if st.form_submit_button("Guardar escena"):
                scene.duration_seconds = float(duration)
                scene.narration_line = narration.strip()
                scene.on_screen_action = action.strip()
                scene.character_pose = pose.strip()
                scene.character_emotion = emotion.strip()
                scene.character_variant = variant.strip() or None
                scene.camera_shot = camera_shot.strip()
                scene.camera_motion = camera_motion.strip()
                scene.background = background.strip()
                scene.props_json = json.dumps(
                    [item.strip() for item in props.split(",") if item.strip()]
                )
                scene.higgsfield_prompt = prompt.strip()
                scene.negative_prompt = negative.strip()
                scene.status = status
                add_and_commit(session, scene)
                st.success("Escena guardada.")
                st.rerun()


def safe_duration_bounds(duration: float | None) -> tuple[float, float]:
    safe_duration = float(duration or 8.0)
    return safe_duration, max(90.0, safe_duration)
