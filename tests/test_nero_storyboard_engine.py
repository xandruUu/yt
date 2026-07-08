from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config.settings import get_settings
from app.core.enums import ScriptStatus
from app.db.models import Base, Script, ScriptLine, Topic
from app.external_tools.elevenlabs.provider import ElevenLabsProvider
from app.services.character_service import (
    NERO_NEGATIVE_PROMPT,
    NERO_REQUIRED_TRAITS,
    character_bible_markdown,
    export_character_bible_markdown,
    seed_nero_character_system,
)
from app.services.external_asset_import_service import import_external_asset
from app.services.scene_asset_mapping_service import (
    create_scene_asset_mapping,
    storyboard_render_manifest,
    validate_storyboard_asset_mappings,
)
from app.services.storyboard_prompt_pack_service import create_nero_higgsfield_prompt_pack
from app.services.storyboard_service import VisualStoryboardService, list_storyboard_scenes


def _session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, future=True)()


def test_nero_exists_as_default_character_and_exports_bible(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    session = _session()
    try:
        nero = seed_nero_character_system(session)
        bible = character_bible_markdown(nero)
        exported = export_character_bible_markdown(session, nero.id)

        assert nero.is_default is True
        assert nero.slug == "nero"
        assert "Daily Brain Break" in bible
        assert "Pink cartoon brain body/head." in bible
        assert "Do not make Nero realistic." in bible
        assert Path(exported).exists()
    finally:
        session.close()
        get_settings.cache_clear()


def test_storyboard_from_approved_script_preserves_nero_identity() -> None:
    session = _session()
    try:
        script = _approved_script(session)
        nero = seed_nero_character_system(session)

        storyboard = VisualStoryboardService().create_from_script(
            session,
            script_id=script.id,
            character_id=nero.id,
        )
        scenes = list_storyboard_scenes(session, storyboard.id)

        assert storyboard.total_scenes == len(script.lines)
        assert scenes
        for scene in scenes:
            assert scene.duration_seconds > 0
            assert "Nero is a cute anthropomorphic pink cartoon brain mascot" in scene.higgsfield_prompt
            assert "Negative prompt:" in scene.higgsfield_prompt
            assert "Do not change Nero's identity" in scene.negative_prompt
            assert scene.required_assets_json
    finally:
        session.close()


def test_nero_prompt_pack_exports_expected_structure(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    session = _session()
    try:
        script = _approved_script(session)
        nero = seed_nero_character_system(session)
        storyboard = VisualStoryboardService().create_from_script(
            session,
            script_id=script.id,
            character_id=nero.id,
        )

        pack = create_nero_higgsfield_prompt_pack(session, storyboard_id=storyboard.id)
        folder = Path(pack.folder_path)

        assert (folder / "00_master_prompt.md").exists()
        assert (folder / "01_character_reference_nero.md").exists()
        assert (folder / "02_negative_prompt.md").read_text(encoding="utf-8") == NERO_NEGATIVE_PROMPT
        assert (folder / "03_storyboard.md").exists()
        assert (folder / "04_shot_list.csv").exists()
        assert (folder / "05_voiceover_script.txt").exists()
        assert (folder / "scenes" / "scene_01_prompt.txt").exists()
        assert (folder / "picsart" / "picsart_processing_plan.md").exists()
        assert (folder / "assets" / "required_assets.json").exists()
        assert (folder / "license_notes.md").exists()
    finally:
        session.close()
        get_settings.cache_clear()


def test_elevenlabs_is_safe_without_env_and_requires_confirmation(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    monkeypatch.delenv("ELEVENLABS_DEFAULT_VOICE_ID", raising=False)
    monkeypatch.setenv("ENABLE_ELEVENLABS", "false")
    monkeypatch.setenv("ENABLE_ELEVENLABS_TTS", "false")
    get_settings.cache_clear()
    try:
        provider = ElevenLabsProvider(http_post=lambda *_args: (_ for _ in ()).throw(AssertionError("API called")))
        status = provider.get_status()
        result = provider.synthesize_text(
            text="The first move is what sets everything in motion.",
            language="en",
            voice_id=None,
            model_id=None,
            output_path=tmp_path / "voice.mp3",
            confirmed_paid=False,
        )

        assert status.available is False
        assert result.ok is False
        assert not (tmp_path / "voice.mp3").exists()
    finally:
        get_settings.cache_clear()


def test_scene_mapping_manifest_supports_fallback_and_validates_assets(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ASSETS_DIR", str(tmp_path / "assets"))
    get_settings.cache_clear()
    session = _session()
    try:
        script = _approved_script(session)
        nero = seed_nero_character_system(session)
        storyboard = VisualStoryboardService().create_from_script(
            session,
            script_id=script.id,
            character_id=nero.id,
        )
        scenes = list_storyboard_scenes(session, storyboard.id)

        fallback_manifest = storyboard_render_manifest(session, storyboard.id, allow_fallback=True)
        assert fallback_manifest["ok"] is True
        assert fallback_manifest["warnings"]
        assert fallback_manifest["scenes"][0]["source"] == "fallback_prompt"

        source_clip = tmp_path / "scene_01.mp4"
        source_clip.write_bytes(b"fake mp4")
        asset = import_external_asset(
            session,
            file_path=source_clip,
            asset_type="video",
            provider_name="higgsfield",
            script_id=script.id,
            scene_order=1,
            license_info={
                "source": "higgsfield",
                "license_type": "generated_owned",
                "commercial_use_confirmed": True,
            },
        )
        mapping = create_scene_asset_mapping(
            session,
            scene_id=scenes[0].id,
            external_asset_id=asset.id,
            duration=scenes[0].duration_seconds,
        )

        assert mapping.fit_mode == "cover"
        assert validate_storyboard_asset_mappings(session, storyboard.id).ok is True
        Path(asset.file_path).unlink()
        assert validate_storyboard_asset_mappings(session, storyboard.id).ok is False
    finally:
        session.close()
        get_settings.cache_clear()


def _approved_script(session) -> Script:
    topic = Topic(
        title="QR codes still work when damaged",
        summary="Error correction explained",
        category="tech_explained",
    )
    session.add(topic)
    session.commit()
    script = Script(
        topic_id=topic.id,
        language="en",
        script_text="This QR code looks destroyed.\nBut it still scans.\nThat is error correction.",
        estimated_duration_seconds=9.0,
        tone="fast curious Nero explainer",
        status=ScriptStatus.APPROVED.value,
    )
    script.lines.extend(
        [
            ScriptLine(line_order=1, text="This QR code looks destroyed.", subtitle_text="This QR code looks destroyed.", duration_seconds=3.0),
            ScriptLine(line_order=2, text="But it still scans.", subtitle_text="But it still scans.", duration_seconds=3.0),
            ScriptLine(line_order=3, text="That is error correction.", subtitle_text="That is error correction.", duration_seconds=3.0),
        ]
    )
    session.add(script)
    session.commit()
    session.refresh(script)
    assert NERO_REQUIRED_TRAITS
    return script
