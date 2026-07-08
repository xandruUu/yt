from __future__ import annotations

import streamlit as st
from sqlalchemy import select

from app.db import models
from app.db.database import new_session
from app.services.external_asset_import_service import import_external_asset
from app.services.scene_asset_mapping_service import (
    create_scene_asset_mapping,
    list_scene_asset_mappings,
    storyboard_render_manifest,
)
from app.services.storyboard_service import list_storyboard_scenes


def render() -> None:
    st.title("Mapeo de clips")
    with new_session() as session:
        storyboard = _select_storyboard(session)
        if storyboard is None:
            st.info("Genera un storyboard antes de mapear clips.")
            return
        _render_import_and_map(session, storyboard)
        st.divider()
        _render_existing_mappings(session, storyboard)
        st.divider()
        _render_manifest(session, storyboard)


def _select_storyboard(session) -> models.VisualStoryboard | None:
    storyboards = session.scalars(
        select(models.VisualStoryboard).order_by(models.VisualStoryboard.created_at.desc())
    ).all()
    if not storyboards:
        return None
    options = {
        f"Storyboard #{item.id} | Script #{item.script_id} | {item.status}": item.id
        for item in storyboards
    }
    selected = st.selectbox("Storyboard", list(options))
    return session.get(models.VisualStoryboard, options[selected])


def _render_import_and_map(session, storyboard: models.VisualStoryboard) -> None:
    st.subheader("Importar y asociar clip")
    scenes = list_storyboard_scenes(session, storyboard.id)
    if not scenes:
        st.info("Este storyboard no tiene escenas.")
        return
    scene_options = {f"Escena {scene.scene_number:02}: {scene.narration_line[:60]}": scene.id for scene in scenes}
    with st.form("scene_asset_mapping_form"):
        selected_scene = st.selectbox("Escena", list(scene_options))
        file_path = st.text_input("Ruta local del clip/imagen")
        asset_type = st.selectbox("Tipo", ["video", "image"])
        provider_name = st.selectbox("Proveedor", ["higgsfield", "picsart", "manual"])
        col1, col2, col3 = st.columns(3)
        usage_type = col1.selectbox("Uso", ["foreground_clip", "background_video", "image", "overlay", "broll"])
        fit_mode = col2.selectbox("Fit", ["cover", "contain", "crop", "blur_background"])
        crop_anchor = col3.selectbox("Crop anchor", ["center", "top", "bottom", "face_safe"])
        license_type = st.text_input("Licencia", value="generated_owned")
        commercial = st.checkbox("Uso comercial confirmado", value=True)
        notes = st.text_area("Notas")
        submitted = st.form_submit_button("Importar y mapear")
        if submitted:
            try:
                scene = session.get(models.StoryboardScene, scene_options[selected_scene])
                if scene is None:
                    st.error("Escena no encontrada.")
                    return
                asset = import_external_asset(
                    session,
                    file_path=file_path,
                    asset_type=asset_type,
                    provider_name=provider_name,
                    script_id=storyboard.script_id,
                    scene_order=scene.scene_number,
                    license_info={
                        "source": provider_name,
                        "license_type": license_type or None,
                        "commercial_use_confirmed": commercial,
                        "license_notes": notes or None,
                    },
                    overwrite=True,
                )
                mapping = create_scene_asset_mapping(
                    session,
                    scene_id=scene.id,
                    external_asset_id=asset.id,
                    usage_type=usage_type,
                    duration=scene.duration_seconds,
                    fit_mode=fit_mode,
                    crop_anchor=crop_anchor,
                    notes=notes or None,
                )
                st.success(f"ExternalAsset #{asset.id} mapeado a escena #{scene.scene_number} (mapping #{mapping.id}).")
                st.rerun()
            except Exception as exc:  # noqa: BLE001 - Streamlit debe mostrar el bloqueo exacto.
                st.error(str(exc))


def _render_existing_mappings(session, storyboard: models.VisualStoryboard) -> None:
    st.subheader("Mappings existentes")
    mappings = list_scene_asset_mappings(session, storyboard.id)
    if not mappings:
        st.info("Todavia no hay clips asociados.")
        return
    rows = []
    for mapping in mappings:
        scene = session.get(models.StoryboardScene, mapping.scene_id)
        asset = session.get(models.ExternalAsset, mapping.external_asset_id)
        rows.append(
            {
                "mapping": mapping.id,
                "escena": scene.scene_number if scene else "-",
                "asset": asset.id if asset else "-",
                "ruta": asset.file_path if asset else "-",
                "uso": mapping.usage_type,
                "fit": mapping.fit_mode,
                "crop": mapping.crop_anchor,
            }
        )
    st.dataframe(rows, use_container_width=True, hide_index=True)


def _render_manifest(session, storyboard: models.VisualStoryboard) -> None:
    st.subheader("Render manifest")
    manifest = storyboard_render_manifest(session, storyboard.id, allow_fallback=True)
    for warning in manifest["warnings"]:
        st.warning(warning)
    for error in manifest["errors"]:
        st.error(error)
    st.json(manifest, expanded=False)
