from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config.settings import get_settings
from app.db import models
from app.db.models import Base
from app.external_tools.higgsfield import client as higgsfield_client
from app.external_tools.higgsfield.client import (
    HiggsfieldCliResult,
    HiggsfieldCostResult,
    HiggsfieldCreateResult,
)
from app.services import canonical_render_service, production_pipeline_service
from app.services.canonical_render_service import MediaProbe
from app.services.export_service import create_canonical_export_package
from app.services.production_pipeline_service import (
    estimate_higgsfield_cost_for_scene,
    register_higgsfield_output_as_generated_clip,
    submit_higgsfield_job_for_scene,
    supersede_stale_higgsfield_jobs,
)


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, future=True)()


def _completed(args, stdout: str, returncode: int = 0):
    return subprocess.CompletedProcess(args=args, returncode=returncode, stdout=stdout, stderr="")


def _cli_result(command: list[str], data: dict) -> HiggsfieldCliResult:
    return HiggsfieldCliResult(
        ok=True,
        command=command,
        stdout=json.dumps(data),
        stderr="",
        returncode=0,
        data=data,
    )


def test_estimate_generation_cost_parses_credits(monkeypatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setattr(
        higgsfield_client.subprocess,
        "run",
        lambda command, **_: _completed(command, '{"credits": 4}'),
    )

    result = higgsfield_client.estimate_generation_cost(
        prompt="short prompt",
        model_name="veo3_1_lite",
        duration_seconds=4,
        aspect_ratio="9:16",
    )

    assert result.credits == 4
    assert result.cli_result.command[:3] == ["higgsfield", "generate", "cost"]


def test_create_generation_job_rejects_when_real_generation_disabled(monkeypatch) -> None:
    monkeypatch.setenv("HIGGSFIELD_REAL_GENERATION_ENABLED", "false")
    get_settings.cache_clear()
    monkeypatch.setattr(
        higgsfield_client.subprocess,
        "run",
        lambda *_args, **_kwargs: pytest.fail("subprocess.run must not be called"),
    )

    with pytest.raises(ValueError, match="desactivada"):
        higgsfield_client.create_generation_job(prompt="p", confirmed_credits=True)


def test_create_generation_job_rejects_without_credit_confirmation(monkeypatch) -> None:
    monkeypatch.setenv("HIGGSFIELD_REAL_GENERATION_ENABLED", "true")
    get_settings.cache_clear()
    monkeypatch.setattr(
        higgsfield_client.subprocess,
        "run",
        lambda *_args, **_kwargs: pytest.fail("subprocess.run must not be called"),
    )

    with pytest.raises(ValueError, match="confirmacion"):
        higgsfield_client.create_generation_job(prompt="p", confirmed_credits=False)


def test_create_generation_job_parses_external_job_id(monkeypatch) -> None:
    monkeypatch.setenv("HIGGSFIELD_REAL_GENERATION_ENABLED", "true")
    get_settings.cache_clear()
    monkeypatch.setattr(
        higgsfield_client.subprocess,
        "run",
        lambda command, **_: _completed(command, '{"job_id": "job_123"}'),
    )

    result = higgsfield_client.create_generation_job(prompt="p", confirmed_credits=True)

    assert result.external_job_id == "job_123"


def test_wait_generation_job_extracts_output_url(monkeypatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setattr(
        higgsfield_client.subprocess,
        "run",
        lambda command, **_: _completed(
            command,
            '{"status": "completed", "outputs": [{"url": "https://cdn.test/out.mp4"}]}',
        ),
    )

    result = higgsfield_client.wait_generation_job("job_123")

    assert result.status == "completed"
    assert result.output_url == "https://cdn.test/out.mp4"


def test_get_generation_job_extracts_status(monkeypatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setattr(
        higgsfield_client.subprocess,
        "run",
        lambda command, **_: _completed(command, '{"data": {"state": "running"}}'),
    )

    result = higgsfield_client.get_generation_job("job_123")

    assert result.status == "running"


def test_estimate_higgsfield_cost_creates_cost_estimated_job(monkeypatch) -> None:
    session = _session()
    _project, selected = _canonical_project(session)
    monkeypatch.setattr(
        production_pipeline_service,
        "estimate_generation_cost",
        lambda **_: HiggsfieldCostResult(
            credits=4,
            raw={"credits": 4},
            cli_result=_cli_result(["higgsfield", "generate", "cost"], {"credits": 4}),
        ),
    )

    job = estimate_higgsfield_cost_for_scene(session, selected_scene_id=selected.id)

    assert job.status == "cost_estimated"
    assert job.model_name == "veo3_1_lite"
    assert job.cost_estimate_credits == 4
    assert job.confirmed_credits is False


def test_cost_estimated_job_does_not_duplicate_for_same_scene_pack(monkeypatch) -> None:
    session = _session()
    _project, selected = _canonical_project(session)
    monkeypatch.setattr(
        production_pipeline_service,
        "estimate_generation_cost",
        lambda **_: HiggsfieldCostResult(
            credits=4,
            raw={"credits": 4},
            cli_result=_cli_result(["higgsfield", "generate", "cost"], {"credits": 4}),
        ),
    )

    first = estimate_higgsfield_cost_for_scene(session, selected_scene_id=selected.id)
    second = estimate_higgsfield_cost_for_scene(session, selected_scene_id=selected.id)

    assert first.id == second.id
    assert session.query(models.HiggsfieldJob).count() == 1


def test_submit_higgsfield_job_requires_enabled_setting(monkeypatch) -> None:
    monkeypatch.setenv("HIGGSFIELD_REAL_GENERATION_ENABLED", "false")
    get_settings.cache_clear()
    session = _session()
    _project, selected = _canonical_project(session)
    pack = _prompt_pack(session, selected)
    job = _higgsfield_job(session, selected, pack, status="cost_estimated")

    with pytest.raises(ValueError, match="false"):
        submit_higgsfield_job_for_scene(
            session,
            higgsfield_job_id=job.id,
            confirmed_credits=True,
        )


def test_submit_higgsfield_job_saves_external_job_id(monkeypatch) -> None:
    monkeypatch.setenv("HIGGSFIELD_REAL_GENERATION_ENABLED", "true")
    get_settings.cache_clear()
    session = _session()
    _project, selected = _canonical_project(session)
    pack = _prompt_pack(session, selected)
    job = _higgsfield_job(session, selected, pack, status="cost_estimated")
    monkeypatch.setattr(
        production_pipeline_service,
        "create_generation_job",
        lambda **_: HiggsfieldCreateResult(
            external_job_id="job_123",
            raw={"id": "job_123", "status": "submitted"},
            cli_result=_cli_result(["higgsfield", "generate", "create"], {"id": "job_123"}),
            output_url=None,
        ),
    )

    submitted = submit_higgsfield_job_for_scene(
        session,
        higgsfield_job_id=job.id,
        confirmed_credits=True,
    )

    assert submitted.external_job_id == "job_123"
    assert submitted.status == "submitted"
    assert submitted.confirmed_credits is True


def test_register_higgsfield_output_creates_generated_clip() -> None:
    session = _session()
    _project, selected = _canonical_project(session)
    pack = _prompt_pack(session, selected)
    job = _higgsfield_job(
        session,
        selected,
        pack,
        status="completed",
        external_job_id="job_123",
        output_url="https://cdn.test/out.mp4",
    )

    clip = register_higgsfield_output_as_generated_clip(
        session,
        higgsfield_job_id=job.id,
        download_output=False,
    )

    assert clip.source == "higgsfield"
    assert clip.status == "registered_remote"
    assert clip.external_job_id == "job_123"


def test_supersede_stale_created_jobs_without_external_id() -> None:
    session = _session()
    _project, selected = _canonical_project(session)
    pack = _prompt_pack(session, selected)
    stale = _higgsfield_job(session, selected, pack, status="created")
    real = _higgsfield_job(
        session,
        selected,
        pack,
        status="created",
        external_job_id="job_real",
    )

    count = supersede_stale_higgsfield_jobs(session, selected_scene_id=selected.id)

    assert count == 1
    assert session.get(models.HiggsfieldJob, stale.id).status == "superseded"
    assert session.get(models.HiggsfieldJob, real.id).status == "created"


def test_render_readiness_blocks_without_voiceover_output_path(monkeypatch) -> None:
    session = _session()
    project, selected = _canonical_project(session)
    _patch_render_tools(monkeypatch)
    session.add(
        models.VoiceoverJob(
            video_project_id=project.id,
            script_draft_id=_latest_script(session, project.id).id,
            language="en",
            provider="placeholder",
            status="generated",
        )
    )
    session.add(_clip(session, project, selected, "missing_voice_scene.mp4"))
    session.commit()

    readiness = canonical_render_service.build_render_readiness(session, project.id)

    assert readiness.can_render_final is False
    assert "output_path local" in "; ".join(readiness.blockers)


def test_render_readiness_blocks_missing_clips(monkeypatch, tmp_path) -> None:
    session = _session()
    project, _selected = _canonical_project(session)
    _patch_render_tools(monkeypatch)
    _voiceover(session, project, tmp_path / "voice.mp3")

    readiness = canonical_render_service.build_render_readiness(session, project.id)

    assert readiness.can_render_final is False
    assert "Faltan clips reales" in "; ".join(readiness.blockers)


def test_render_readiness_ready_with_voice_and_all_clips(monkeypatch, tmp_path) -> None:
    session = _session()
    project, selected = _canonical_project(session)
    _patch_render_tools(monkeypatch)
    _voiceover(session, project, tmp_path / "voice.mp3")
    clip = _clip(session, project, selected, str(tmp_path / "scene.mp4"))
    Path(clip.file_path).write_bytes(b"fake mp4")
    session.add(clip)
    session.commit()

    readiness = canonical_render_service.build_render_readiness(session, project.id)

    assert readiness.can_render_final is True


def test_render_video_project_creates_render_job_rendered_when_ffmpeg_ok(
    monkeypatch, tmp_path
) -> None:
    session = _session()
    project, selected = _canonical_project(session)
    _patch_render_tools(monkeypatch)
    _voiceover(session, project, tmp_path / "voice.mp3")
    clip = _clip(session, project, selected, str(tmp_path / "scene.mp4"))
    Path(clip.file_path).write_bytes(b"fake mp4")
    session.add(clip)
    session.commit()
    monkeypatch.setattr(canonical_render_service.subprocess, "run", _fake_ffmpeg_run)

    job = canonical_render_service.render_video_project(
        session,
        video_project_id=project.id,
        output_path=str(tmp_path / "final.mp4"),
    )

    assert job.status == "rendered"
    assert job.output_path.endswith("final.mp4")


def test_render_video_project_marks_failed_when_ffmpeg_fails(monkeypatch, tmp_path) -> None:
    session = _session()
    project, selected = _canonical_project(session)
    _patch_render_tools(monkeypatch)
    _voiceover(session, project, tmp_path / "voice.mp3")
    clip = _clip(session, project, selected, str(tmp_path / "scene.mp4"))
    Path(clip.file_path).write_bytes(b"fake mp4")
    session.add(clip)
    session.commit()
    monkeypatch.setattr(
        canonical_render_service.subprocess,
        "run",
        lambda command, **_: subprocess.CompletedProcess(
            args=command,
            returncode=1,
            stdout="",
            stderr="ffmpeg failed",
        ),
    )

    job = canonical_render_service.render_video_project(
        session,
        video_project_id=project.id,
        output_path=str(tmp_path / "final.mp4"),
    )

    assert job.status == "failed"
    assert "ffmpeg failed" in job.error_message


def test_export_requires_approved_render_job(tmp_path) -> None:
    session = _session()
    project, _selected = _canonical_project(session)
    output = tmp_path / "final.mp4"
    output.write_bytes(b"fake")
    render_job = models.RenderJob(
        video_project_id=project.id,
        output_path=str(output),
        status="rendered",
        approved=False,
    )
    session.add(render_job)
    session.commit()

    with pytest.raises(ValueError, match="approved"):
        create_canonical_export_package(
            session,
            render_job_id=render_job.id,
            exports_dir=tmp_path / "exports",
        )


def test_export_package_contains_expected_files(tmp_path) -> None:
    session = _session()
    project, selected = _canonical_project(session)
    script = _latest_script(session, project.id)
    _voiceover(session, project, tmp_path / "voice.mp3")
    clip = _clip(session, project, selected, str(tmp_path / "scene.mp4"))
    Path(clip.file_path).write_bytes(b"fake mp4")
    session.add(clip)
    output = tmp_path / "final.mp4"
    output.write_bytes(b"fake final")
    render_job = models.RenderJob(
        video_project_id=project.id,
        output_path=str(output),
        status="rendered",
        approved=True,
        metadata_json=json.dumps(
            {
                "script_draft_id": script.id,
                "generated_clip_ids": [clip.id],
            }
        ),
    )
    session.add(render_job)
    session.commit()

    package = create_canonical_export_package(
        session,
        render_job_id=render_job.id,
        exports_dir=tmp_path / "exports",
    )
    export_folder = Path(package["export_folder"])

    assert (export_folder / "final.mp4").exists()
    assert (export_folder / "title.txt").exists()
    assert (export_folder / "description.txt").exists()
    assert (export_folder / "hashtags.txt").exists()
    assert (export_folder / "script.txt").exists()
    assert (export_folder / "voiceover.txt").exists()
    assert (export_folder / "metadata.json").exists()
    assert (export_folder / "assets.json").exists()
    assert (export_folder / "README.md").exists()
    metadata = json.loads((export_folder / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["video_project_id"] == project.id
    assert session.get(models.VideoProject, project.id).status == "exported"


def _canonical_project(session: Session) -> tuple[models.VideoProject, models.SelectedScene]:
    project = models.VideoProject(
        title="Why this impossible image works",
        description="A canonical project.",
        hook="This image should not make sense.",
        hashtags_json=json.dumps(["#shorts", "#science"]),
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
        duration_seconds=4.0,
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
    return project, selected


def _prompt_pack(session: Session, selected: models.SelectedScene) -> models.HiggsfieldPromptPack:
    pack = models.HiggsfieldPromptPack(
        video_project_id=selected.video_project_id,
        selected_scene_id=selected.id,
        prompt="Vertical scene",
        aspect_ratio="9:16",
        duration_seconds=4,
        status="generated",
    )
    session.add(pack)
    session.commit()
    return pack


def _higgsfield_job(
    session: Session,
    selected: models.SelectedScene,
    pack: models.HiggsfieldPromptPack,
    *,
    status: str,
    external_job_id: str | None = None,
    output_url: str | None = None,
) -> models.HiggsfieldJob:
    job = models.HiggsfieldJob(
        video_project_id=selected.video_project_id,
        selected_scene_id=selected.id,
        prompt_pack_id=pack.id,
        automation_mode="cli",
        status=status,
        estimated_credits=4,
        cost_estimate_credits=4,
        model_name="veo3_1_lite",
        requested_duration_seconds=4,
        requested_aspect_ratio="9:16",
        external_job_id=external_job_id,
        output_url=output_url,
    )
    session.add(job)
    session.commit()
    return job


def _latest_script(session: Session, project_id: int) -> models.ScriptDraft:
    return (
        session.query(models.ScriptDraft)
        .filter(models.ScriptDraft.video_project_id == project_id)
        .first()
    )


def _voiceover(session: Session, project: models.VideoProject, path: Path) -> models.VoiceoverJob:
    path.write_bytes(b"fake voice")
    job = models.VoiceoverJob(
        video_project_id=project.id,
        script_draft_id=_latest_script(session, project.id).id,
        language="en",
        provider="placeholder",
        output_path=str(path),
        status="generated",
    )
    session.add(job)
    session.commit()
    return job


def _clip(
    session: Session,
    project: models.VideoProject,
    selected: models.SelectedScene,
    path: str,
) -> models.GeneratedClip:
    return models.GeneratedClip(
        video_project_id=project.id,
        selected_scene_id=selected.id,
        source="manual",
        file_path=path,
        duration_seconds=4,
        status="ready",
        license_type="manual_owned",
        commercial_use_confirmed=True,
    )


def _patch_render_tools(monkeypatch) -> None:
    monkeypatch.setattr(canonical_render_service, "_binary_available", lambda _path: True)
    monkeypatch.setattr(
        canonical_render_service,
        "probe_media",
        lambda path: MediaProbe(path=str(path), duration_seconds=4, width=1080, height=1920),
    )


def _fake_ffmpeg_run(command, **_kwargs):
    output = Path(command[-1])
    if output.suffix == ".mp4":
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"fake mp4")
    return subprocess.CompletedProcess(args=command, returncode=0, stdout="", stderr="")
