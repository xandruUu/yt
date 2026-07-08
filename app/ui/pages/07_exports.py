from __future__ import annotations

from pathlib import Path

import streamlit as st
from sqlalchemy import select

from app.config.settings import get_settings
from app.db import models
from app.db.database import new_session
from app.i18n.es import LANGUAGE_LABELS_ES, label_for
from app.services.export_service import create_export_package
from app.services.license_manifest_service import build_external_license_manifest
from app.utils.licenses import build_license_manifest
from app.utils.text import normalize_hashtags


def render() -> None:
    st.title("Exportaciones")
    render_row = _select_approved_render()
    if render_row is None:
        st.info("Aprueba un render antes de exportar.")
        return

    st.video(render_row["video_path"])
    st.subheader("Metadatos del paquete")
    title = st.text_input("Título", value=render_row["title"] or render_row["topic_title"])
    description = st.text_area("Descripción", value=render_row["description"] or "", height=140)
    hashtags = st.text_input("Hashtags", value=render_row["hashtags"] or "#shorts")
    contains_synthetic_media = st.checkbox("Contiene contenido sintético/IA", value=True)
    made_for_kids = st.checkbox("Contenido para niños", value=False)

    selected_assets, selected_music = _select_license_items()

    if st.button("Exportar paquete final", type="primary"):
        settings = get_settings()
        try:
            with new_session() as manifest_session:
                base_manifest = build_license_manifest(selected_music, selected_assets)
                external_manifest = build_external_license_manifest(
                    manifest_session,
                    script_id=int(render_row["script_id"]),
                )
            package = create_export_package(
                output_dir=settings.output_dir,
                topic_title=render_row["topic_title"],
                language=render_row["language"],
                video_path=render_row["video_path"],
                title=title,
                description=description,
                hashtags=normalize_hashtags(hashtags),
                script_text=render_row["script_text"],
                metadata={
                    "topic": render_row["topic_title"],
                    "language": render_row["language"],
                    "target_market": render_row["target_market"],
                    "duration_seconds": render_row["duration_seconds"],
                    "category": render_row["category"],
                    "hook": render_row["hook"],
                    "title": title,
                    "description": description,
                    "hashtags": normalize_hashtags(hashtags),
                    "contains_synthetic_media": contains_synthetic_media,
                    "made_for_kids": made_for_kids,
                    "music_track": selected_music[0]["title"] if selected_music else None,
                    "assets_used": [asset["name"] for asset in selected_assets],
                },
                review_checklist=render_row["checklist"],
                license_manifest={**base_manifest, **external_manifest},
                overwrite=True,
            )
            with new_session() as session:
                db_render = session.get(models.Render, render_row["id"])
                if db_render:
                    db_render.status = "exported"
                export_package = models.ExportPackage(
                    render_id=render_row["id"],
                    export_folder=package["export_folder"],
                    video_file=package["video_file"],
                    title_file=package["title_file"],
                    description_file=package["description_file"],
                    hashtags_file=package["hashtags_file"],
                    script_file=package["script_file"],
                    metadata_file=package["metadata_file"],
                    checklist_file=package["checklist_file"],
                )
                session.add(export_package)
                session.commit()
            st.success(f"Exportado en {package['export_folder']}")
        except Exception as exc:  # noqa: BLE001 - Streamlit should show the failure.
            st.error(str(exc))

    _manual_publish_marker()


def _select_approved_render() -> dict[str, object] | None:
    with new_session() as session:
        renders = session.scalars(
            select(models.Render).where(models.Render.status == "approved").order_by(models.Render.created_at.desc())
        ).all()
        if not renders:
            return None
        options = {
            f"#{item.id} {item.script.topic.title} [{label_for(LANGUAGE_LABELS_ES, item.language)}]": item.id
            for item in renders
        }
        selected = st.selectbox("Render aprobado", list(options))
        item = session.get(models.Render, options[selected])
        checklist = item.checklist
        return {
            "id": item.id,
            "script_id": item.script_id,
            "video_path": item.video_path,
            "language": item.language,
            "duration_seconds": item.duration_seconds,
            "topic_title": item.script.topic.title,
            "target_market": item.script.topic.target_markets,
            "category": item.script.topic.category,
            "hook": item.script.hook.text if item.script.hook else "",
            "script_text": item.script.script_text,
            "title": item.script.title_suggestion,
            "description": item.script.description_suggestion,
            "hashtags": item.script.hashtags,
            "checklist": {
                "approved": checklist.approved if checklist else False,
                "hook_strong": checklist.hook_strong if checklist else False,
                "script_fact_checked": checklist.script_fact_checked if checklist else False,
                "language_natural": checklist.language_natural if checklist else False,
                "music_license_ok": checklist.music_license_ok if checklist else False,
                "assets_license_ok": checklist.assets_license_ok if checklist else False,
                "no_reused_content_risk": checklist.no_reused_content_risk if checklist else False,
                "no_sensitive_content": checklist.no_sensitive_content if checklist else False,
                "subtitles_readable": checklist.subtitles_readable if checklist else False,
                "audio_clear": checklist.audio_clear if checklist else False,
                "video_not_too_repetitive": checklist.video_not_too_repetitive if checklist else False,
                "metadata_not_misleading": checklist.metadata_not_misleading if checklist else False,
                "made_for_kids_false_confirmed": checklist.made_for_kids_false_confirmed if checklist else False,
                "synthetic_media_reviewed": checklist.synthetic_media_reviewed if checklist else False,
                "review_notes": checklist.review_notes if checklist else None,
            },
        }


def _select_license_items() -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    with new_session() as session:
        assets = session.scalars(select(models.Asset).order_by(models.Asset.name)).all()
        music = session.scalars(select(models.MusicTrack).order_by(models.MusicTrack.title)).all()
        asset_options = {f"#{asset.id} {asset.name}": asset.id for asset in assets}
        music_options = {f"#{track.id} {track.title}": track.id for track in music}
        selected_asset_labels = st.multiselect("Recursos usados", list(asset_options))
        selected_music_labels = st.multiselect("Música usada", list(music_options), max_selections=1)
        selected_assets = [
            _asset_to_dict(session.get(models.Asset, asset_options[label])) for label in selected_asset_labels
        ]
        selected_music = [
            _music_to_dict(session.get(models.MusicTrack, music_options[label])) for label in selected_music_labels
        ]
        return selected_assets, selected_music


def _asset_to_dict(asset: models.Asset) -> dict[str, object]:
    return {
        "name": asset.name,
        "source": asset.source,
        "license_type": asset.license_type,
        "attribution_required": asset.attribution_required,
        "attribution_text": asset.attribution_text,
    }


def _music_to_dict(track: models.MusicTrack) -> dict[str, object]:
    return {
        "title": track.title,
        "source": track.source,
        "license_type": track.license_type,
        "attribution_required": track.attribution_required,
        "attribution_text": track.attribution_text,
    }


def _manual_publish_marker() -> None:
    st.subheader("Marcador de subida manual")
    with new_session() as session:
        packages = session.scalars(select(models.ExportPackage).order_by(models.ExportPackage.created_at.desc())).all()
        if not packages:
            return
        options = {f"#{package.id} {Path(package.export_folder).name}": package.id for package in packages}
        selected = st.selectbox("Paquete exportado", list(options))
        url = st.text_input("URL manual de YouTube")
        if st.button("Marcar como subido manualmente"):
            package = session.get(models.ExportPackage, options[selected])
            if package:
                package.manual_youtube_url = url
                package.render.status = "exported"
                session.commit()
                st.success("URL de subida manual guardada.")
