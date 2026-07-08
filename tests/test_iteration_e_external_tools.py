from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config.settings import get_settings
from app.core.enums import ScriptStatus
from app.db import models
from app.db.models import Base, Script, ScriptLine, Topic
from app.external_tools.elevenlabs.provider import ElevenLabsProvider
from app.external_tools.registry import ExternalToolRegistry
from app.services.external_asset_import_service import import_external_asset
from app.services.prompt_pack_service import (
    create_higgsfield_prompt_pack,
    create_picsart_prompt_pack,
)
from app.services.render_plan_service import create_short_render_plan, validate_render_plan
from app.services.visual_plan_service import approve_visual_plan, generate_visual_plan
from app.services.voiceover_generation_service import create_voiceover_from_script
from app.tts.base import VoiceOption, VoiceoverResult


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    db_session = sessionmaker(bind=engine, future=True)()
    try:
        yield db_session
    finally:
        db_session.close()


@pytest.fixture()
def configured_env(tmp_path, monkeypatch):
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    monkeypatch.setenv("ASSETS_DIR", str(tmp_path / "assets"))
    monkeypatch.setenv("ENABLE_EXTERNAL_TOOLS", "true")
    monkeypatch.setenv("ENABLE_ELEVENLABS", "true")
    monkeypatch.setenv("ENABLE_ELEVENLABS_TTS", "true")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "secret-key-not-for-output")
    monkeypatch.setenv("ELEVENLABS_DEFAULT_VOICE_ID", "voice_123")
    monkeypatch.setenv("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2")
    monkeypatch.setenv("ELEVENLABS_ESTIMATED_COST_PER_1000_CHARS", "0.01")
    get_settings.cache_clear()
    try:
        yield tmp_path
    finally:
        get_settings.cache_clear()


def test_registry_lists_external_providers_without_api_key(monkeypatch) -> None:
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    monkeypatch.setenv("ENABLE_ELEVENLABS", "true")
    get_settings.cache_clear()
    try:
        rows = ExternalToolRegistry().status_rows()
    finally:
        get_settings.cache_clear()

    names = {row["herramienta"] for row in rows}
    elevenlabs = next(row for row in rows if row["herramienta"] == "elevenlabs")

    assert {"elevenlabs", "higgsfield_manual", "picsart_manual"}.issubset(names)
    assert elevenlabs["disponible"] is False
    assert "secret" not in json.dumps(rows).lower()


def test_elevenlabs_requires_paid_confirmation(configured_env: Path) -> None:
    called = False

    def fake_http(_url: str, _headers: dict[str, str], _body: bytes, _timeout: int):
        nonlocal called
        called = True
        return 200, b"", "application/json"

    result = ElevenLabsProvider(http_post=fake_http).synthesize_text(
        text="Texto de prueba",
        language="es",
        voice_id="voice_123",
        model_id="eleven_multilingual_v2",
        output_path=configured_env / "voice.mp3",
        confirmed_paid=False,
    )

    assert result.ok is False
    assert "confirmar" in result.error_message.lower()
    assert called is False
    assert "secret-key" not in result.error_message


def test_elevenlabs_generates_audio_and_alignment_with_mock(configured_env: Path) -> None:
    response = {
        "audio_base64": base64.b64encode(b"fake mp3").decode("ascii"),
        "alignment": {
            "characters": ["h", "i"],
            "character_start_times_seconds": [0.0, 0.1],
            "character_end_times_seconds": [0.1, 0.3],
        },
        "normalized_alignment": {
            "characters": ["h", "i"],
            "character_start_times_seconds": [0.0, 0.1],
            "character_end_times_seconds": [0.1, 0.3],
        },
    }

    def fake_http(url: str, headers: dict[str, str], body: bytes, _timeout: int):
        assert "/with-timestamps" in url
        assert headers["xi-api-key"] == "secret-key-not-for-output"
        assert b"Texto de prueba" in body
        return 200, json.dumps(response).encode("utf-8"), "application/json"

    output = configured_env / "voice.mp3"
    result = ElevenLabsProvider(http_post=fake_http).synthesize_text(
        text="Texto de prueba",
        language="es",
        voice_id="voice_123",
        model_id="eleven_multilingual_v2",
        output_path=output,
        confirmed_paid=True,
    )

    assert result.ok is True
    assert output.read_bytes() == b"fake mp3"
    assert Path(result.alignment_path).exists()
    assert result.duration_seconds == 0.3


def test_voiceover_service_records_elevenlabs_audit_rows(session, configured_env: Path, monkeypatch) -> None:
    script = _approved_script(session)

    class FakeElevenLabsTTS:
        name = "elevenlabs_tts"

        def is_available(self) -> bool:
            return True

        def availability_reason(self) -> str:
            return "ok"

        def list_voices(self, language: str = "es") -> list[VoiceOption]:
            return [VoiceOption(id="voice_123", name="Test", language=language, provider=self.name)]

        def synthesize(self, **_kwargs) -> VoiceoverResult:
            output = configured_env / "outputs" / "voice.mp3"
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(b"fake")
            return VoiceoverResult(
                ok=True,
                provider=self.name,
                voice_id="voice_123",
                voice_name="Test",
                audio_path=str(output),
                duration_seconds=1.2,
                metadata={
                    "estimated_cost": 0.01,
                    "actual_cost": 0.02,
                    "model_id": "eleven_multilingual_v2",
                },
            )

    monkeypatch.setattr(
        "app.services.voiceover_generation_service.get_tts_providers",
        lambda: {"elevenlabs_tts": FakeElevenLabsTTS()},
    )

    job = create_voiceover_from_script(
        session,
        script_id=script.id,
        provider_name="elevenlabs_tts",
        allow_paid=True,
    )

    assert job.output_audio_path
    assert job.cost_estimate == 0.01
    assert session.query(models.ExternalToolJob).count() == 1
    assert session.query(models.CostEvent).count() == 1


def test_prompt_packs_create_higgsfield_and_picsart_files(session, configured_env: Path) -> None:
    script = _approved_script(session)
    visual_plan = approve_visual_plan(session, generate_visual_plan(session, script_id=script.id).id)

    higgsfield = create_higgsfield_prompt_pack(session, script_id=script.id, visual_plan_id=visual_plan.id)
    picsart = create_picsart_prompt_pack(session, script_id=script.id, visual_plan_id=visual_plan.id)

    assert (Path(higgsfield.folder_path) / "master_prompt.md").exists()
    assert (Path(higgsfield.folder_path) / "scene_prompts" / "scene_01.txt").exists()
    assert "no subtitles burned in" in (Path(higgsfield.folder_path) / "negative_prompt.txt").read_text(
        encoding="utf-8"
    )
    assert (Path(picsart.folder_path) / "clip_processing_plan.csv").exists()


def test_external_asset_import_requires_valid_extension_and_license_review(session, configured_env: Path) -> None:
    script = _approved_script(session)
    bad_file = configured_env / "clip.exe"
    bad_file.write_bytes(b"bad")
    with pytest.raises(ValueError):
        import_external_asset(session, file_path=bad_file, asset_type="video", script_id=script.id)

    video = configured_env / "clip.mp4"
    video.write_bytes(b"fake mp4")
    asset = import_external_asset(
        session,
        file_path=video,
        asset_type="video",
        provider_name="higgsfield",
        script_id=script.id,
        license_info={},
    )

    assert asset.status == "needs_license_review"
    assert Path(asset.file_path).exists()


def test_render_validation_blocks_external_asset_without_license(session, configured_env: Path, monkeypatch) -> None:
    monkeypatch.setattr("app.services.render_plan_service.ffmpeg_available", lambda: True)
    script = _approved_script(session)
    visual_plan = approve_visual_plan(session, generate_visual_plan(session, script_id=script.id).id)
    video = configured_env / "clip.mp4"
    video.write_bytes(b"fake mp4")
    asset = import_external_asset(
        session,
        file_path=video,
        asset_type="video",
        provider_name="higgsfield",
        script_id=script.id,
        visual_plan_id=visual_plan.id,
    )
    scenes = json.loads(visual_plan.scenes_json)
    scenes[0]["external_asset_id"] = asset.id
    visual_plan.scenes_json = json.dumps(scenes)
    session.commit()

    render_plan = create_short_render_plan(
        session,
        script_id=script.id,
        voiceover_job_id=None,
        subtitle_track_id=None,
        visual_plan_id=visual_plan.id,
    )
    report = validate_render_plan(session, render_plan.id)

    assert any("sin licencia" in error for error in report.errors)


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
        language="es",
        script_text="Linea uno\nLinea dos",
        estimated_duration_seconds=6.0,
        tone="documental rapido",
        status=ScriptStatus.APPROVED.value,
    )
    script.lines.extend(
        [
            ScriptLine(line_order=1, text="Linea uno", subtitle_text="Linea uno", duration_seconds=3.0),
            ScriptLine(line_order=2, text="Linea dos", subtitle_text="Linea dos", duration_seconds=3.0),
        ]
    )
    session.add(script)
    session.commit()
    session.refresh(script)
    return script
