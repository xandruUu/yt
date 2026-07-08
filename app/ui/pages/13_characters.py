from __future__ import annotations

import json

import streamlit as st
from sqlalchemy import select

from app.db import models
from app.db.database import new_session
from app.db.repositories import add_and_commit
from app.services.character_service import (
    character_bible_markdown,
    export_character_bible_markdown,
    list_character_poses,
    list_character_variants,
    seed_nero_character_system,
    update_character_profile,
)


def render() -> None:
    st.title("Personajes")
    with new_session() as session:
        character = seed_nero_character_system(session)
        characters = session.scalars(select(models.CharacterProfile).order_by(models.CharacterProfile.name)).all()
        options = {f"{item.name} ({item.slug})": item.id for item in characters}
        selected = st.selectbox("Personaje", list(options), index=list(options.values()).index(character.id))
        character = session.get(models.CharacterProfile, options[selected])
        if character is None:
            st.error("Personaje no encontrado.")
            return

        _render_character_editor(session, character)
        st.divider()
        _render_poses(session, character)
        st.divider()
        _render_variants(session, character)


def _render_character_editor(session, character: models.CharacterProfile) -> None:
    st.subheader("Character Bible")
    with st.form(f"character_profile_{character.id}"):
        role = st.text_input("Rol", value=character.role)
        short_description = st.text_area("Descripcion corta", value=character.short_description, height=90)
        canonical_description = st.text_area(
            "Descripcion visual canonica",
            value=character.canonical_description,
            height=170,
        )
        master_prompt = st.text_area("Master prompt", value=character.master_prompt, height=180)
        negative_prompt = st.text_area("Negative prompt", value=character.negative_prompt, height=180)
        personality = st.text_area("Personalidad", value=character.personality, height=100)
        speaking_style = st.text_area("Forma de hablar", value=character.speaking_style, height=100)
        reference_images = st.text_area(
            "Reference images, una ruta por linea",
            value="\n".join(json.loads(character.reference_image_paths_json or "[]")),
            height=80,
        )
        submitted = st.form_submit_button("Guardar Character Bible")
        if submitted:
            update_character_profile(
                session,
                character.id,
                role=role.strip(),
                short_description=short_description.strip(),
                canonical_description=canonical_description.strip(),
                master_prompt=master_prompt.strip(),
                negative_prompt=negative_prompt.strip(),
                personality=personality.strip(),
                speaking_style=speaking_style.strip(),
                reference_image_paths_json=json.dumps(
                    [line.strip() for line in reference_images.splitlines() if line.strip()],
                    ensure_ascii=False,
                ),
            )
            st.success("Character Bible guardada.")
            st.rerun()

    poses = list_character_poses(session, character.id)
    variants = list_character_variants(session, character.id)
    with st.expander("Previsualizar Character Bible Markdown", expanded=False):
        st.markdown(character_bible_markdown(character, poses, variants))
    if st.button("Exportar Character Bible Markdown"):
        path = export_character_bible_markdown(session, character.id)
        st.success("Character Bible exportada.")
        st.code(str(path))
    st.code(character.master_prompt, language="markdown")
    st.code(character.negative_prompt, language="markdown")


def _render_poses(session, character: models.CharacterProfile) -> None:
    st.subheader("Poses")
    poses = list_character_poses(session, character.id)
    st.dataframe(
        [
            {
                "id": pose.id,
                "nombre": pose.name,
                "emocion": pose.emotion,
                "camara": pose.camera_angle,
                "descripcion": pose.description,
            }
            for pose in poses
        ],
        use_container_width=True,
        hide_index=True,
    )
    with st.form("new_character_pose"):
        name = st.text_input("Nueva pose")
        description = st.text_area("Descripcion")
        emotion = st.text_input("Emocion")
        camera_angle = st.text_input("Camara", value="vertical medium shot")
        prompt_fragment = st.text_area("Prompt fragment")
        if st.form_submit_button("Crear pose"):
            if not name.strip():
                st.error("La pose necesita nombre.")
                return
            add_and_commit(
                session,
                models.CharacterPose(
                    character_id=character.id,
                    name=name.strip(),
                    description=description.strip(),
                    emotion=emotion.strip(),
                    camera_angle=camera_angle.strip(),
                    prompt_fragment=prompt_fragment.strip(),
                ),
            )
            st.success("Pose creada.")
            st.rerun()


def _render_variants(session, character: models.CharacterProfile) -> None:
    st.subheader("Variantes")
    variants = list_character_variants(session, character.id)
    st.dataframe(
        [
            {
                "id": variant.id,
                "nombre": variant.name,
                "descripcion": variant.description,
                "outfit": variant.outfit_description,
            }
            for variant in variants
        ],
        use_container_width=True,
        hide_index=True,
    )
    with st.form("new_character_variant"):
        name = st.text_input("Nueva variante")
        description = st.text_area("Descripcion variante")
        outfit = st.text_area("Outfit controlado")
        use_cases = st.text_input("Use cases separados por coma", value="science_explained,tech_explained")
        prompt_fragment = st.text_area("Prompt fragment variante")
        negative_fragment = st.text_area("Negative prompt fragment")
        if st.form_submit_button("Crear variante"):
            if not name.strip():
                st.error("La variante necesita nombre.")
                return
            add_and_commit(
                session,
                models.CharacterVariant(
                    character_id=character.id,
                    name=name.strip(),
                    description=description.strip(),
                    outfit_description=outfit.strip(),
                    use_cases_json=json.dumps([item.strip() for item in use_cases.split(",") if item.strip()]),
                    prompt_fragment=prompt_fragment.strip(),
                    negative_prompt_fragment=negative_fragment.strip(),
                ),
            )
            st.success("Variante creada.")
            st.rerun()
