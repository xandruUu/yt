from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config.settings import get_settings
from app.core.enums import (
    RenderPlanStatus,
    ScriptStatus,
    SubtitleTrackStatus,
    VisualPlanStatus,
    VoiceoverJobStatus,
)
from app.core.validation import REQUIRED_REVIEW_FLAGS
from app.db.models import Base, MusicTrack, Script, ScriptLine, Topic
from app.render.audio_mixer import mix_voice_and_music
from app.services.export_service import create_export_package
from app.services.music_service import suggest_music_for_script
from app.services.render_plan_service import (
    create_short_render_plan,
    mark_render_plan_ready,
    validate_render_plan,
)
from app.services.subtitle_alignment_service import (
    approve_subtitles,
    export_srt,
    generate_subtitles_from_script,
)
from app.services.visual_plan_service import (
    approve_visual_plan,
    generate_visual_plan,
    visual_plan_scenes,
)
from app.services.voiceover_generation_service import (
    approve_voiceover,
    create_voiceover_from_script,
    import_manual_voiceover,
    list_tts_provider_statuses,
)


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
def output_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    get_settings.cache_clear()
    try:
        yield tmp_path / "outputs"
    finally:
        get_settings.cache_clear()


def test_placeholder_and_manual_voiceover_jobs(session, output_dir: Path) -> None:
    script = _approved_script(session)

    placeholder = create_voiceover_from_script(
        session,
        script_id=script.id,
        provider_name="placeholder",
    )
    assert placeholder.status == VoiceoverJobStatus.PLACEHOLDER.value
    assert placeholder.output_audio_path is None

    approved = approve_voiceover(session, placeholder.id)
    assert approved.status == VoiceoverJobStatus.APPROVED.value

    source_audio = output_dir.parent / "manual.wav"
    source_audio.write_bytes(b"fake wav")
    manual = import_manual_voiceover(
        session,
        script_id=script.id,
        file_path=source_audio,
        duration_seconds=script.estimated_duration_seconds,
    )
    assert manual.status == VoiceoverJobStatus.IMPORTED_MANUAL.value
    assert manual.output_audio_path and Path(manual.output_audio_path).exists()

    providers = {item["provider"]: item for item in list_tts_provider_statuses("es")}
    assert providers["placeholder"]["available"] is True
    assert providers["manual_recording"]["available"] is True


def test_subtitles_generate_srt_and_can_be_approved(session, output_dir: Path) -> None:
    script = _approved_script(session)
    track = generate_subtitles_from_script(session, script_id=script.id, target_duration_seconds=10)

    assert Path(track.srt_path).exists()
    assert "00:00:00,000 -->" in export_srt(session, track.id)

    approved = approve_subtitles(session, track.id)
    assert approved.status == SubtitleTrackStatus.APPROVED.value


def test_visual_plan_and_render_plan_validation(session, output_dir: Path, monkeypatch) -> None:
    monkeypatch.setattr("app.services.render_plan_service.ffmpeg_available", lambda: True)
    script = _approved_script(session)
    voiceover = create_voiceover_from_script(session, script_id=script.id, provider_name="placeholder")
    subtitles = approve_subtitles(
        session,
        generate_subtitles_from_script(session, script_id=script.id, voiceover_job_id=voiceover.id).id,
    )
    visual_plan = approve_visual_plan(session, generate_visual_plan(session, script_id=script.id).id)

    render_plan = create_short_render_plan(
        session,
        script_id=script.id,
        voiceover_job_id=voiceover.id,
        subtitle_track_id=subtitles.id,
        visual_plan_id=visual_plan.id,
        music_track_id=None,
    )
    report = validate_render_plan(session, render_plan.id)
    ready = mark_render_plan_ready(session, render_plan.id)

    assert report.ok is True
    assert "No hay musica seleccionada." in report.warnings
    assert ready.status == RenderPlanStatus.READY.value


def test_visual_plan_has_one_scene_per_script_line(session, output_dir: Path) -> None:
    script = _approved_script(session)
    plan = generate_visual_plan(session, script_id=script.id)

    assert plan.status == VisualPlanStatus.GENERATED.value
    assert len(visual_plan_scenes(plan)) == len(script.lines)


def test_music_suggestions_filter_unsafe_tracks(session) -> None:
    script = _approved_script(session)
    safe = MusicTrack(
        title="Safe Tech Pulse",
        file_path="assets/music/safe.mp3",
        source="local",
        license_type="royalty_free",
        mood="tech",
        energy=4,
        safe_for_monetization=True,
    )
    unsafe = MusicTrack(
        title="Unsafe Track",
        file_path="assets/music/unsafe.mp3",
        source="unknown",
        license_type="unknown",
        mood="tech",
        energy=4,
        safe_for_monetization=False,
    )
    session.add_all([safe, unsafe])
    session.commit()

    suggested = suggest_music_for_script(session, script_id=script.id)
    suggested_with_unsafe = suggest_music_for_script(session, script_id=script.id, include_unsafe=True)

    assert [track.title for track in suggested] == ["Safe Tech Pulse"]
    assert {track.title for track in suggested_with_unsafe} == {"Safe Tech Pulse", "Unsafe Track"}


def test_audio_mixer_accepts_no_audio_without_ffmpeg(tmp_path) -> None:
    result = mix_voice_and_music(
        voice_path=None,
        music_path=None,
        output_path=tmp_path / "mix.m4a",
    )

    assert result.ok is True
    assert result.output_path is None


def test_export_package_contains_iteration_d_files(tmp_path) -> None:
    video = tmp_path / "source.mp4"
    video.write_bytes(b"fake mp4")
    checklist = {flag: True for flag in REQUIRED_REVIEW_FLAGS}
    checklist["approved"] = True

    package = create_export_package(
        output_dir=tmp_path / "exports",
        topic_title="Iteracion D",
        language="es",
        video_path=video,
        title="Titulo",
        description="Descripcion",
        hashtags=["#shorts"],
        script_text="Linea uno",
        subtitles_srt="1\n00:00:00,000 --> 00:00:01,000\nLinea uno\n",
        voiceover_summary={"provider": "placeholder", "status": "approved"},
        visual_plan={"template": "clean_text_focus"},
        render_plan={"status": "rendered"},
        metadata={},
        review_checklist=checklist,
        license_manifest={"music": [], "assets": []},
        overwrite=True,
    )

    export_folder = Path(package["export_folder"])
    assert (export_folder / "subtitles.srt").read_text(encoding="utf-8").startswith("1\n")
    assert "placeholder" in (export_folder / "voiceover.txt").read_text(encoding="utf-8")
    assert (export_folder / "visual_plan.json").exists()
    assert (export_folder / "render_plan.json").exists()


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
        script_text="Linea uno\nLinea dos\nLinea tres",
        estimated_duration_seconds=9.0,
        tone="documental rapido",
        status=ScriptStatus.APPROVED.value,
    )
    script.lines.extend(
        [
            ScriptLine(line_order=1, text="Linea uno", subtitle_text="Linea uno", duration_seconds=3.0),
            ScriptLine(line_order=2, text="Linea dos", subtitle_text="Linea dos", duration_seconds=3.0),
            ScriptLine(line_order=3, text="Linea tres", subtitle_text="Linea tres", duration_seconds=3.0),
        ]
    )
    session.add(script)
    session.commit()
    session.refresh(script)
    return script
