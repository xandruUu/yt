from __future__ import annotations

import streamlit as st
from sqlalchemy import select

from app.core.enums import AssetType, MusicMood
from app.db import models
from app.db.database import new_session
from app.db.repositories import create_asset, create_music_track
from app.services.asset_service import build_asset_payload
from app.services.music_service import build_music_payload


def render() -> None:
    st.title("Música y recursos")
    tab_assets, tab_music = st.tabs(["Recursos", "Música"])
    with tab_assets:
        _asset_form()
        _asset_table()
    with tab_music:
        _music_form()
        _music_table()


def _asset_form() -> None:
    st.subheader("Registrar recurso")
    with st.form("asset_form"):
        name = st.text_input("Nombre")
        asset_type = st.selectbox("Tipo", [item.value for item in AssetType])
        file_path = st.text_input("Ruta local del archivo")
        source = st.text_input("Fuente")
        source_url = st.text_input("URL de la fuente")
        license_type = st.text_input("Tipo de licencia")
        attribution_required = st.checkbox("Requiere atribución")
        attribution_text = st.text_area("Texto de atribución")
        safe_for_commercial_use = st.checkbox("Seguro para uso comercial")
        notes = st.text_area("Notas")
        if st.form_submit_button("Registrar recurso"):
            try:
                payload = build_asset_payload(
                    name=name,
                    asset_type=asset_type,
                    file_path=file_path,
                    source=source,
                    source_url=source_url,
                    license_type=license_type,
                    attribution_required=attribution_required,
                    attribution_text=attribution_text,
                    safe_for_commercial_use=safe_for_commercial_use,
                    notes=notes,
                )
                with new_session() as session:
                    create_asset(session, **payload)
                st.success("Recurso registrado.")
            except ValueError as exc:
                st.error(str(exc))


def _music_form() -> None:
    st.subheader("Registrar música")
    with st.form("music_form"):
        title = st.text_input("Título")
        artist = st.text_input("Autor")
        file_path = st.text_input("Ruta local del archivo")
        source = st.text_input("Fuente")
        source_url = st.text_input("URL de la fuente")
        license_type = st.text_input("Tipo de licencia")
        mood = st.selectbox("Mood", [item.value for item in MusicMood])
        energy = st.slider("Energía", 1, 5, 3)
        bpm = st.number_input("BPM", min_value=0, value=0)
        duration_seconds = st.number_input("Duración en segundos", min_value=0.0, value=0.0)
        attribution_required = st.checkbox("Requiere atribución", key="music_attr_required")
        attribution_text = st.text_area("Texto de atribución", key="music_attr_text")
        safe_for_monetization = st.checkbox("Segura para monetización")
        notes = st.text_area("Notas", key="music_notes")
        if st.form_submit_button("Registrar música"):
            try:
                payload = build_music_payload(
                    title=title,
                    artist=artist,
                    file_path=file_path,
                    source=source,
                    source_url=source_url,
                    license_type=license_type,
                    mood=mood,
                    energy=energy,
                    bpm=int(bpm) if bpm else None,
                    duration_seconds=float(duration_seconds) if duration_seconds else None,
                    attribution_required=attribution_required,
                    attribution_text=attribution_text,
                    safe_for_monetization=safe_for_monetization,
                    notes=notes,
                )
                with new_session() as session:
                    create_music_track(session, **payload)
                st.success("Música registrada.")
            except ValueError as exc:
                st.error(str(exc))


def _asset_table() -> None:
    with new_session() as session:
        assets = session.scalars(select(models.Asset).order_by(models.Asset.created_at.desc())).all()
        st.dataframe(
            [
                {
                    "id": asset.id,
                    "nombre": asset.name,
                    "tipo": asset.asset_type,
                    "licencia": asset.license_type,
                    "seguro": asset.safe_for_commercial_use,
                }
                for asset in assets
            ],
            use_container_width=True,
            hide_index=True,
        )


def _music_table() -> None:
    with new_session() as session:
        tracks = session.scalars(select(models.MusicTrack).order_by(models.MusicTrack.created_at.desc())).all()
        st.dataframe(
            [
                {
                    "id": track.id,
                    "título": track.title,
                    "mood": track.mood,
                    "licencia": track.license_type,
                    "seguro": track.safe_for_monetization,
                }
                for track in tracks
            ],
            use_container_width=True,
            hide_index=True,
        )
