from __future__ import annotations

import importlib

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db import models
from app.db.models import Base

render_page = importlib.import_module("app.ui.pages.05_render")
storyboard_page = importlib.import_module("app.ui.pages.14_storyboard")
scene_mapping_page = importlib.import_module("app.ui.pages.15_scene_mapping")


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, future=True)()


def test_storyboard_duration_bounds_allow_persisted_values_above_20() -> None:
    value, max_value = storyboard_page.safe_duration_bounds(23.0)

    assert value == 23.0
    assert max_value >= 23.0


def test_scene_mapping_upserts_generated_clip_without_legacy_storyboard(tmp_path) -> None:
    session = _session()
    project, selected, _script = _canonical_project(session, with_voice=False)
    clip_path = tmp_path / "scene_01.mp4"
    clip_path.write_bytes(b"fake mp4")

    first = scene_mapping_page.upsert_generated_clip_for_scene(
        session,
        selected_scene_id=selected.id,
        file_path=str(clip_path),
        asset_type="video",
        provider="manual",
        duration_seconds=8.0,
        status="mapped",
        license_type="manual_owned",
        commercial_use_confirmed=True,
        notes="local test clip",
    )
    second = scene_mapping_page.upsert_generated_clip_for_scene(
        session,
        selected_scene_id=selected.id,
        file_path=str(clip_path),
        asset_type="video",
        provider="manual",
        duration_seconds=9.0,
        status="ready",
        license_type="manual_owned",
        commercial_use_confirmed=True,
        notes="updated",
    )
    third = scene_mapping_page.upsert_generated_clip_for_scene(
        session,
        selected_scene_id=selected.id,
        file_path=str(clip_path),
        asset_type="video",
        provider="manual",
        duration_seconds=10.0,
        status="mapped",
        license_type="manual_owned",
        commercial_use_confirmed=True,
        notes="new version",
        create_new_version=True,
    )

    assert project.id == selected.video_project_id
    assert first.id == second.id
    assert second.duration_seconds == 9.0
    assert third.id != first.id
    assert session.query(models.VisualStoryboard).count() == 0


def test_canonical_render_readiness_blocks_until_voice_and_clips_exist(tmp_path) -> None:
    session = _session()
    project, selected, script = _canonical_project(session, with_voice=False)

    missing_voice = render_page.canonical_render_readiness(session, project.id)
    assert missing_voice.script.id == script.id
    assert missing_voice.voiceover is None
    assert missing_voice.can_render_final is False

    voice = models.VoiceoverJob(
        video_project_id=project.id,
        script_draft_id=script.id,
        language="en",
        provider="placeholder",
        input_text=script.voiceover_text,
        status="generated",
    )
    session.add(voice)
    session.commit()

    missing_clip = render_page.canonical_render_readiness(session, project.id)
    assert missing_clip.voiceover.id == voice.id
    assert missing_clip.can_render_final is False

    clip_path = tmp_path / "scene_ready.mp4"
    clip_path.write_bytes(b"fake mp4")
    scene_mapping_page.upsert_generated_clip_for_scene(
        session,
        selected_scene_id=selected.id,
        file_path=str(clip_path),
        asset_type="video",
        provider="manual",
        duration_seconds=8.0,
        status="ready",
        license_type="manual_owned",
        commercial_use_confirmed=True,
        notes=None,
    )

    ready = render_page.canonical_render_readiness(session, project.id)
    assert ready.can_render_final is True

    final_job = render_page.create_canonical_render_job(
        session,
        project_id=project.id,
        output_path=str(tmp_path / "final.mp4"),
        preview=False,
    )
    preview_job = render_page.create_canonical_render_job(
        session,
        project_id=project.id,
        output_path=str(tmp_path / "preview.mp4"),
        preview=True,
    )
    assert final_job.status == "ready"
    assert preview_job.status == "placeholder_preview"


def _canonical_project(
    session: Session,
    *,
    with_voice: bool,
) -> tuple[models.VideoProject, models.SelectedScene, models.ScriptDraft]:
    project = models.VideoProject(
        title="Why this impossible image works",
        description="A canonical cleanup test project.",
        hook="This image should not make sense.",
        content_language="en",
        status="metadata_selected",
    )
    session.add(project)
    session.commit()

    script = models.ScriptDraft(
        video_project_id=project.id,
        language="en",
        voiceover_text="This image should not make sense. But your brain completes it.",
        estimated_duration_seconds=12,
        estimated_words=12,
        status="script_approved",
    )
    slot = models.SceneSlot(
        video_project_id=project.id,
        slot_number=1,
        slot_type="hook",
        target_start_second=0,
        target_end_second=8,
        voiceover_segment="This image should not make sense.",
    )
    session.add_all([script, slot])
    session.commit()

    candidate = models.SceneCandidate(
        scene_slot_id=slot.id,
        option_code="1A",
        duration_seconds=8.0,
        visual_description="Nero reveals an impossible image.",
        character_action="Nero points at the visual paradox.",
        camera_movement="slow push-in",
        setting="clean explainer set",
        status="selected",
    )
    session.add(candidate)
    session.commit()

    selected = models.SelectedScene(
        video_project_id=project.id,
        scene_slot_id=slot.id,
        scene_candidate_id=candidate.id,
        sort_order=1,
        status="selected",
    )
    session.add(selected)
    session.commit()

    if with_voice:
        session.add(
            models.VoiceoverJob(
                video_project_id=project.id,
                script_draft_id=script.id,
                language="en",
                provider="placeholder",
                input_text=script.voiceover_text,
                status="generated",
            )
        )
        session.commit()

    session.refresh(project)
    session.refresh(selected)
    session.refresh(script)
    return project, selected, script
