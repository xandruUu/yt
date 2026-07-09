from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.db import models
from app.db.repositories import add_and_commit, create_obsidian_sync_log
from app.services.character_service import (
    character_bible_markdown,
    list_character_cells,
    list_character_poses,
    list_character_variants,
)
from app.utils.safe_paths import safe_join
from app.utils.slugs import slugify

VAULT_DIRS = (
    "00_Index",
    "01_Characters",
    "02_Video_Projects",
    "03_Scripts",
    "04_Higgsfield_Prompts",
    "05_Research",
    "06_Style_Guides",
    "07_App_Architecture",
    "99_Inbox",
)


def ensure_obsidian_vault() -> Path:
    settings = get_settings()
    vault = settings.obsidian_vault_path
    vault.mkdir(parents=True, exist_ok=True)
    for folder in VAULT_DIRS:
        (vault / folder).mkdir(parents=True, exist_ok=True)
    home = vault / "00_Index" / "Home.md"
    if not home.exists():
        home.write_text("# ShortsFactory Brain\n\nHuman-readable creative memory for ShortsFactory.\n", encoding="utf-8")
    return vault


def export_character_note(session: Session, character_id: int) -> Path:
    character = session.get(models.CharacterProfile, character_id)
    if character is None:
        raise ValueError(f"CharacterProfile not found: {character_id}")
    vault = ensure_obsidian_vault()
    path = safe_join(vault, "01_Characters", f"{slugify(character.name)}.md")
    content = _frontmatter(
        {
            "type": "character_profile",
            "id": character.id,
            "slug": character.slug,
            "family_id": character.family_id,
            "status": character.status,
            "main_image": character.main_image_path,
        }
    )
    content += character_bible_markdown(
        character,
        poses=list_character_poses(session, character.id),
        variants=list_character_variants(session, character.id),
        cells=list_character_cells(session, character.id),
    )
    path.write_text(content, encoding="utf-8")
    character.obsidian_note_path = str(path)
    add_and_commit(session, character)
    create_obsidian_sync_log(
        session,
        entity_type="character_profile",
        entity_id=character.id,
        note_path=str(path),
        action="export",
        status="completed",
    )
    return path


def export_video_project_note(session: Session, video_project_id: int) -> Path:
    project = session.get(models.VideoProject, video_project_id)
    if project is None:
        raise ValueError(f"VideoProject not found: {video_project_id}")
    vault = ensure_obsidian_vault()
    slug = slugify(project.title) or f"video_project_{project.id}"
    path = safe_join(vault, "02_Video_Projects", f"{project.id}_{slug}.md")
    script = _latest_script_draft(session, project.id)
    prompt_packs = _prompt_packs(session, project.id)
    clips = _generated_clips(session, project.id)
    content = _frontmatter(
        {
            "type": "video_project",
            "id": project.id,
            "slug": slug,
            "character_profile_id": project.character_profile_id,
            "status": project.status,
            "language": project.content_language,
        }
    )
    content += f"""# {project.title}

## Metadata
Title: {project.title}

Description:
{project.description}

Hashtags:
{_json_to_markdown_list(project.hashtags_json)}

Hook:
{project.hook}

## Script
{script.voiceover_text if script else "No script draft yet."}

## Higgsfield prompts
{_prompt_pack_markdown(prompt_packs)}

## Generated clips
{_clip_markdown(clips)}

## Lessons learned
- Pending review.
"""
    path.write_text(content, encoding="utf-8")
    create_obsidian_sync_log(
        session,
        entity_type="video_project",
        entity_id=project.id,
        note_path=str(path),
        action="export",
        status="completed",
    )
    return path


def get_character_brain_context(session: Session, character_profile_id: int) -> str:
    character = session.get(models.CharacterProfile, character_profile_id)
    if character is None or not character.obsidian_note_path:
        return ""
    return _read_note_excerpt(Path(character.obsidian_note_path), max_chars=4000)


def get_style_guide_context(limit: int = 5) -> str:
    vault = get_settings().obsidian_vault_path
    folder = vault / "06_Style_Guides"
    if not folder.exists():
        return ""
    excerpts = []
    for path in sorted(folder.glob("*.md"))[:limit]:
        excerpts.append(_read_note_excerpt(path, max_chars=1200))
    return "\n\n".join(excerpts)


def get_recent_lessons_context(limit: int = 5) -> str:
    vault = get_settings().obsidian_vault_path
    folder = vault / "02_Video_Projects"
    if not folder.exists():
        return ""
    excerpts = []
    paths = sorted(folder.glob("*.md"), key=lambda path: path.stat().st_mtime, reverse=True)
    for path in paths[:limit]:
        text = _read_note_excerpt(path, max_chars=3000)
        marker = "## Lessons learned"
        if marker in text:
            excerpts.append(text[text.index(marker) :])
    return "\n\n".join(excerpts)


def _frontmatter(payload: dict[str, object]) -> str:
    lines = ["---"]
    for key, value in payload.items():
        if value is None:
            continue
        lines.append(f"{key}: {json.dumps(value, ensure_ascii=False)}")
    lines.append("---\n")
    return "\n".join(lines)


def _read_note_excerpt(path: Path, max_chars: int) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return ""
    return text[:max_chars]


def _latest_script_draft(session: Session, video_project_id: int) -> models.ScriptDraft | None:
    return (
        session.query(models.ScriptDraft)
        .filter_by(video_project_id=video_project_id)
        .order_by(models.ScriptDraft.created_at.desc())
        .first()
    )


def _prompt_packs(session: Session, video_project_id: int) -> list[models.HiggsfieldPromptPack]:
    return list(session.query(models.HiggsfieldPromptPack).filter_by(video_project_id=video_project_id).all())


def _generated_clips(session: Session, video_project_id: int) -> list[models.GeneratedClip]:
    return list(session.query(models.GeneratedClip).filter_by(video_project_id=video_project_id).all())


def _json_to_markdown_list(value: str) -> str:
    try:
        items = json.loads(value or "[]")
    except json.JSONDecodeError:
        items = []
    if not isinstance(items, list) or not items:
        return "- None"
    return "\n".join(f"- {item}" for item in items)


def _prompt_pack_markdown(prompt_packs: list[models.HiggsfieldPromptPack]) -> str:
    if not prompt_packs:
        return "No Higgsfield prompt packs yet."
    return "\n\n".join(
        f"### Scene {pack.selected_scene_id}\n\n{pack.prompt}\n\nNegative: {pack.negative_prompt}"
        for pack in prompt_packs
    )


def _clip_markdown(clips: list[models.GeneratedClip]) -> str:
    if not clips:
        return "No generated clips yet."
    return "\n".join(f"- Scene {clip.selected_scene_id}: {clip.file_path}" for clip in clips)

