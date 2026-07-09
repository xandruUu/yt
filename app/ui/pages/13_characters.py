from __future__ import annotations

import streamlit as st
from sqlalchemy import select

from app.db import models
from app.db.database import new_session
from app.db.repositories import add_and_commit
from app.services.character_locker_service import (
    CELL_TYPES,
    create_character_cell,
    create_character_skin,
)
from app.services.character_service import (
    character_bible_markdown,
    export_character_bible_markdown,
    list_character_cells,
    list_character_poses,
    list_character_variants,
    seed_nero_character_system,
    update_character_profile,
)


def render() -> None:
    st.title("Personajes")
    st.caption("Locker room de personajes y skins. La UI esta en espanol; las descripciones creativas deben quedar en ingles.")

    with new_session() as session:
        seed_nero_character_system(session)
        characters = list(
            session.scalars(
                select(models.CharacterProfile).order_by(
                    models.CharacterProfile.is_default.desc(),
                    models.CharacterProfile.name,
                )
            ).all()
        )
        if not characters:
            st.warning("Todavia no hay personajes.")
            return

        selected_id = _locker_room(characters)
        character = session.get(models.CharacterProfile, selected_id)
        if character is None:
            st.error("Personaje no encontrado.")
            return

        st.divider()
        _render_character_editor(session, character)
        st.divider()
        _render_cells(session, character)
        st.divider()
        _render_poses(session, character)
        st.divider()
        _render_variants(session, character)
        st.divider()
        _render_new_skin(session, character.family_id)


def _locker_room(characters: list[models.CharacterProfile]) -> int:
    st.subheader("Locker room")
    current = st.session_state.get("selected_character_profile_id") or characters[0].id
    columns = st.columns(min(4, max(1, len(characters))))
    for index, character in enumerate(characters):
        with columns[index % len(columns)]:
            border = current == character.id
            with st.container(border=border):
                if character.main_image_path:
                    st.image(character.main_image_path, use_container_width=True)
                st.markdown(f"**{character.name}**")
                st.caption(character.short_description or character.role or character.slug)
                if st.button("Seleccionar", key=f"select_character_{character.id}"):
                    st.session_state["selected_character_profile_id"] = character.id
                    st.rerun()
    return int(st.session_state.get("selected_character_profile_id") or characters[0].id)


def _render_character_editor(session, character: models.CharacterProfile) -> None:
    st.subheader(f"Ficha: {character.name}")
    with st.form(f"character_profile_{character.id}"):
        cols = st.columns(2)
        role = cols[0].text_input("Rol", value=character.role)
        status = cols[1].selectbox(
            "Estado",
            ["active", "paused", "archived"],
            index=["active", "paused", "archived"].index(character.status or "active"),
        )
        short_description = st.text_area("Descripcion corta", value=character.short_description, height=80)
        canonical_description = st.text_area(
            "Descripcion visual canonica",
            value=character.canonical_description,
            height=150,
        )
        visual_style = st.text_area("Estilo visual", value=character.visual_style, height=80)
        personality = st.text_area("Personalidad", value=character.personality, height=80)
        prompt_fragment = st.text_area(
            "Prompt fragment",
            value=character.prompt_fragment or character.master_prompt,
            height=120,
        )
        negative_fragment = st.text_area(
            "Negative prompt fragment",
            value=character.negative_prompt_fragment or character.negative_prompt,
            height=120,
        )
        main_image_path = st.text_input("Ruta imagen principal", value=character.main_image_path or "")
        submitted = st.form_submit_button("Guardar personaje")
        if submitted:
            update_character_profile(
                session,
                character.id,
                role=role.strip(),
                status=status,
                short_description=short_description.strip(),
                canonical_description=canonical_description.strip(),
                visual_style=visual_style.strip(),
                personality=personality.strip(),
                prompt_fragment=prompt_fragment.strip(),
                negative_prompt_fragment=negative_fragment.strip(),
                master_prompt=prompt_fragment.strip(),
                negative_prompt=negative_fragment.strip(),
                main_image_path=main_image_path.strip() or None,
            )
            st.success("Personaje guardado.")
            st.rerun()

    cells = list_character_cells(session, character.id)
    poses = list_character_poses(session, character.id)
    variants = list_character_variants(session, character.id)
    with st.expander("Previsualizar Character Bible Markdown", expanded=False):
        st.markdown(character_bible_markdown(character, poses, variants, cells))
    if st.button("Exportar Character Bible Markdown"):
        path = export_character_bible_markdown(session, character.id)
        st.success("Character Bible exportada.")
        st.code(str(path))


def _render_cells(session, character: models.CharacterProfile) -> None:
    st.subheader("Celdas visuales")
    cells = list_character_cells(session, character.id)
    if cells:
        grid = st.columns(3)
        for index, cell in enumerate(cells):
            with grid[index % 3], st.container(border=True):
                if cell.image_path:
                    st.image(cell.image_path, use_container_width=True)
                st.markdown(f"**{cell.title}**")
                st.caption(f"{cell.cell_type} | {'principal' if cell.is_primary else 'referencia'}")
                st.write(cell.description)
                if cell.image_path:
                    st.code(cell.image_path)
    else:
        st.info("Este personaje todavia no tiene celdas visuales.")

    with st.form(f"new_character_cell_{character.id}"):
        st.markdown("**Anadir celda**")
        title = st.text_input("Titulo de celda", placeholder="Nero Zoologist Front")
        cell_type = st.selectbox("Tipo", CELL_TYPES)
        description = st.text_area("Descripcion", height=80)
        prompt_notes = st.text_area("Notas para IA", height=80)
        is_primary = st.checkbox("Marcar como referencia principal")
        upload = st.file_uploader("Imagen de referencia", type=["png", "jpg", "jpeg", "webp"])
        submitted = st.form_submit_button("Crear celda")
        if submitted:
            if not title.strip():
                st.error("La celda necesita titulo.")
                return
            image_bytes = upload.getvalue() if upload is not None else None
            image_filename = upload.name if upload is not None else None
            create_character_cell(
                session,
                character=character,
                title=title.strip(),
                cell_type=cell_type,
                description=description.strip(),
                prompt_notes=prompt_notes.strip(),
                image_filename=image_filename,
                image_bytes=image_bytes,
                is_primary=is_primary,
            )
            st.success("Celda creada.")
            st.rerun()


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
    with st.form(f"new_character_pose_{character.id}"):
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
    st.subheader("Variantes antiguas")
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


def _render_new_skin(session, family_id: int | None) -> None:
    with st.expander("Crear personaje/skin", expanded=False), st.form("new_character_skin"):
        name = st.text_input("Nombre", placeholder="Nero Zoologist")
        short_description = st.text_area("Descripcion corta", height=70)
        canonical_description = st.text_area("Descripcion canonica en ingles", height=120)
        visual_style = st.text_area("Estilo visual", height=70)
        personality = st.text_area("Personalidad", height=70)
        role = st.text_input("Rol", value="Host skin for Daily Brain Break.")
        submitted = st.form_submit_button("Crear skin")
        if submitted:
            if not name.strip() or not canonical_description.strip():
                st.error("La skin necesita nombre y descripcion canonica.")
                return
            create_character_skin(
                session,
                family_id=family_id,
                name=name.strip(),
                short_description=short_description.strip(),
                canonical_description=canonical_description.strip(),
                visual_style=visual_style.strip(),
                personality=personality.strip(),
                role=role.strip(),
            )
            st.success("Skin creada.")
            st.rerun()
