from __future__ import annotations

from pathlib import Path
from typing import Any

from app.core.constants import EXPORT_FILE_NAMES
from app.services.review_service import checklist_can_export
from app.utils.files import copy_file, ensure_dir, write_json_file, write_text_file
from app.utils.language import export_language_folder
from app.utils.safe_paths import safe_join
from app.utils.slugs import slugify
from app.utils.text import normalize_hashtags
from app.utils.time import today_folder_prefix, utc_now_iso


def create_export_package(
    *,
    output_dir: str | Path,
    topic_title: str,
    language: str,
    video_path: str | Path,
    title: str,
    description: str,
    hashtags: str | list[str],
    script_text: str,
    metadata: dict[str, Any],
    review_checklist: dict[str, Any],
    license_manifest: dict[str, Any],
    subtitles_srt: str | None = None,
    voiceover_summary: dict[str, Any] | None = None,
    visual_plan: dict[str, Any] | None = None,
    render_plan: dict[str, Any] | None = None,
    overwrite: bool = False,
) -> dict[str, str]:
    if not checklist_can_export(review_checklist):
        raise ValueError("Export blocked: review checklist is not approved.")

    output_root = Path(output_dir).resolve()
    folder_name = f"{today_folder_prefix()}_{slugify(topic_title)}"
    export_folder = safe_join(output_root, folder_name, export_language_folder(language))
    ensure_dir(export_folder)

    video_file = copy_file(Path(video_path), export_folder / "video.mp4", overwrite=overwrite)
    hashtag_list = normalize_hashtags(hashtags)

    metadata_payload = {
        **metadata,
        "topic": metadata.get("topic") or topic_title,
        "language": metadata.get("language") or language,
        "hashtags": metadata.get("hashtags") or hashtag_list,
        "created_at": metadata.get("created_at") or utc_now_iso(),
    }

    files = {
        "video_file": str(video_file),
        "title_file": str(write_text_file(export_folder / "title.txt", title, overwrite=overwrite)),
        "description_file": str(
            write_text_file(export_folder / "description.txt", description, overwrite=overwrite)
        ),
        "hashtags_file": str(
            write_text_file(export_folder / "hashtags.txt", "\n".join(hashtag_list), overwrite=overwrite)
        ),
        "script_file": str(write_text_file(export_folder / "script.txt", script_text, overwrite=overwrite)),
        "subtitles_file": str(
            write_text_file(export_folder / "subtitles.srt", subtitles_srt or "", overwrite=overwrite)
        ),
        "voiceover_file": str(
            write_text_file(
                export_folder / "voiceover.txt",
                _voiceover_summary_text(voiceover_summary),
                overwrite=overwrite,
            )
        ),
        "visual_plan_file": str(
            write_json_file(export_folder / "visual_plan.json", visual_plan or {}, overwrite=overwrite)
        ),
        "render_plan_file": str(
            write_json_file(export_folder / "render_plan.json", render_plan or {}, overwrite=overwrite)
        ),
        "metadata_file": str(
            write_json_file(export_folder / "metadata.json", metadata_payload, overwrite=overwrite)
        ),
        "checklist_file": str(
            write_json_file(
                export_folder / "review_checklist.json",
                review_checklist,
                overwrite=overwrite,
            )
        ),
        "license_manifest_file": str(
            write_json_file(
                export_folder / "license_manifest.json",
                license_manifest,
                overwrite=overwrite,
            )
        ),
    }
    missing = [name for name in EXPORT_FILE_NAMES if not (export_folder / name).exists()]
    if missing:
        raise RuntimeError(f"Export package missing files: {', '.join(missing)}")
    return {"export_folder": str(export_folder), **files}


def _voiceover_summary_text(summary: dict[str, Any] | None) -> str:
    if not summary:
        return "Sin voz o no documentada.\n"
    lines = [
        f"provider: {summary.get('provider', '')}",
        f"voice_name: {summary.get('voice_name', '')}",
        f"voice_id: {summary.get('voice_id', '')}",
        f"audio_path: {summary.get('audio_path', '')}",
        f"duration_seconds: {summary.get('duration_seconds', '')}",
        f"status: {summary.get('status', '')}",
    ]
    return "\n".join(lines) + "\n"
