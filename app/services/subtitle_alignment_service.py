from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.core.enums import ScriptStatus, SubtitleTrackStatus
from app.db import models
from app.db.repositories import add_and_commit, create_subtitle_track
from app.services.subtitle_service import SubtitleCue, seconds_to_srt_timestamp
from app.utils.files import write_text_file
from app.utils.safe_paths import safe_join


def generate_subtitles_from_script(
    session: Session,
    *,
    script_id: int,
    voiceover_job_id: int | None = None,
    target_duration_seconds: float | None = None,
    overwrite: bool = True,
) -> models.SubtitleTrack:
    script = _get_script_for_subtitles(session, script_id)
    voiceover = session.get(models.VoiceoverJob, voiceover_job_id) if voiceover_job_id else None
    duration = (
        target_duration_seconds
        or (voiceover.duration_seconds if voiceover and voiceover.duration_seconds else None)
        or script.estimated_duration_seconds
    )
    cues = _cues_from_script(script, float(duration))
    srt_content = cues_to_srt(cues)
    srt_path = _subtitle_output_dir(script.id) / "subtitles.srt"
    write_text_file(srt_path, srt_content, overwrite=overwrite)
    return create_subtitle_track(
        session,
        script_id=script.id,
        voiceover_job_id=voiceover_job_id,
        language=script.language,
        srt_path=str(srt_path),
        subtitles_json=json.dumps([_cue_to_payload(cue) for cue in cues], ensure_ascii=False),
        status=SubtitleTrackStatus.GENERATED.value,
    )


def update_subtitle_track_from_rows(
    session: Session,
    *,
    subtitle_track_id: int,
    rows: list[dict[str, Any]],
    overwrite: bool = True,
) -> models.SubtitleTrack:
    track = _get_subtitle_track(session, subtitle_track_id)
    cues = [
        SubtitleCue(
            index=index,
            start_seconds=float(row["start_seconds"]),
            end_seconds=float(row["end_seconds"]),
            text=str(row["text"]).strip(),
        )
        for index, row in enumerate(rows, start=1)
        if str(row.get("text") or "").strip()
    ]
    _validate_cues(cues)
    srt_path = Path(track.srt_path or (_subtitle_output_dir(track.script_id) / "subtitles.srt"))
    write_text_file(srt_path, cues_to_srt(cues), overwrite=overwrite)
    track.srt_path = str(srt_path)
    track.subtitles_json = json.dumps([_cue_to_payload(cue) for cue in cues], ensure_ascii=False)
    track.status = SubtitleTrackStatus.EDITED.value
    return add_and_commit(session, track)


def approve_subtitles(session: Session, subtitle_track_id: int) -> models.SubtitleTrack:
    track = _get_subtitle_track(session, subtitle_track_id)
    if not track.srt_path:
        raise ValueError("No se puede aprobar una pista sin archivo SRT.")
    track.status = SubtitleTrackStatus.APPROVED.value
    return add_and_commit(session, track)


def export_srt(session: Session, subtitle_track_id: int) -> str:
    track = _get_subtitle_track(session, subtitle_track_id)
    if track.srt_path and Path(track.srt_path).exists():
        return Path(track.srt_path).read_text(encoding="utf-8")
    return cues_to_srt([_payload_to_cue(item) for item in json.loads(track.subtitles_json or "[]")])


def cues_to_srt(cues: list[SubtitleCue]) -> str:
    _validate_cues(cues)
    blocks = []
    for cue in cues:
        blocks.append(
            "\n".join(
                [
                    str(cue.index),
                    f"{seconds_to_srt_timestamp(cue.start_seconds)} --> {seconds_to_srt_timestamp(cue.end_seconds)}",
                    cue.text,
                ]
            )
        )
    return "\n\n".join(blocks) + ("\n" if blocks else "")


def _get_script_for_subtitles(session: Session, script_id: int) -> models.Script:
    script = session.get(models.Script, script_id)
    if script is None:
        raise ValueError(f"Script not found: {script_id}")
    if script.status != ScriptStatus.APPROVED.value:
        raise ValueError("El guion debe estar aprobado antes de generar subtitulos.")
    return script


def _get_subtitle_track(session: Session, subtitle_track_id: int) -> models.SubtitleTrack:
    track = session.get(models.SubtitleTrack, subtitle_track_id)
    if track is None:
        raise ValueError(f"Subtitle track not found: {subtitle_track_id}")
    return track


def _cues_from_script(script: models.Script, target_duration_seconds: float) -> list[SubtitleCue]:
    lines = [line for line in script.lines if (line.subtitle_text or line.text).strip()]
    if not lines:
        raise ValueError("El guion no tiene lineas para subtitulos.")
    base_duration = sum(max(0.1, float(line.duration_seconds or 2.5)) for line in lines)
    target_duration_seconds = max(1.0, target_duration_seconds)
    scale = target_duration_seconds / base_duration if base_duration > 0 else 1.0
    cursor = 0.0
    cues: list[SubtitleCue] = []
    for index, line in enumerate(lines, start=1):
        duration = max(0.7, float(line.duration_seconds or 2.5) * scale)
        cues.append(
            SubtitleCue(
                index=index,
                start_seconds=cursor,
                end_seconds=cursor + duration,
                text=(line.subtitle_text or line.text).strip(),
            )
        )
        cursor += duration
    return cues


def _validate_cues(cues: list[SubtitleCue]) -> None:
    previous_end = 0.0
    for cue in cues:
        if cue.start_seconds < 0 or cue.end_seconds <= cue.start_seconds:
            raise ValueError("Los subtitulos tienen tiempos invalidos.")
        if cue.start_seconds < previous_end - 0.001:
            raise ValueError("Los subtitulos se solapan.")
        previous_end = cue.end_seconds


def _cue_to_payload(cue: SubtitleCue) -> dict[str, object]:
    payload = asdict(cue)
    payload["start"] = seconds_to_srt_timestamp(cue.start_seconds)
    payload["end"] = seconds_to_srt_timestamp(cue.end_seconds)
    return payload


def _payload_to_cue(payload: dict[str, Any]) -> SubtitleCue:
    return SubtitleCue(
        index=int(payload["index"]),
        start_seconds=float(payload["start_seconds"]),
        end_seconds=float(payload["end_seconds"]),
        text=str(payload["text"]),
    )


def _subtitle_output_dir(script_id: int) -> Path:
    settings = get_settings()
    return safe_join(settings.output_dir, "subtitles", f"script_{script_id}")
