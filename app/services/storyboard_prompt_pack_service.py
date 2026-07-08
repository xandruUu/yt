from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.core.enums import PromptPackStatus
from app.db import models
from app.db.repositories import create_prompt_pack
from app.services.character_service import (
    character_bible_markdown,
    list_character_poses,
    list_character_variants,
)
from app.services.storyboard_service import list_storyboard_scenes, storyboard_manifest
from app.utils.files import ensure_dir, write_json_file, write_text_file
from app.utils.safe_paths import safe_join
from app.utils.slugs import slugify
from app.utils.time import today_folder_prefix


class HiggsfieldPromptPackService:
    def export_for_storyboard(
        self,
        session: Session,
        *,
        storyboard_id: int,
        wizard_session_id: int | None = None,
        overwrite: bool = True,
    ) -> models.PromptPack:
        storyboard = _get_storyboard(session, storyboard_id)
        script = _get_script(session, storyboard.script_id)
        character = _get_character(session, storyboard.character_id)
        scenes = list_storyboard_scenes(session, storyboard.id)

        folder = _storyboard_prompt_pack_folder(script, storyboard)
        scenes_dir = ensure_dir(folder / "scenes")
        picsart_dir = ensure_dir(folder / "picsart")
        assets_dir = ensure_dir(folder / "assets")

        scene_files = []
        for scene in scenes:
            scene_path = scenes_dir / f"scene_{scene.scene_number:02}_prompt.txt"
            write_text_file(scene_path, scene.higgsfield_prompt, overwrite=overwrite)
            scene_files.append(
                {
                    "scene_number": scene.scene_number,
                    "path": str(scene_path),
                    "prompt": scene.higgsfield_prompt,
                }
            )

        write_text_file(folder / "00_master_prompt.md", _master_prompt(storyboard, script, character, scenes), overwrite=overwrite)
        write_text_file(
            folder / "01_character_reference_nero.md",
            character_bible_markdown(
                character,
                poses=list_character_poses(session, character.id),
                variants=list_character_variants(session, character.id),
            ),
            overwrite=overwrite,
        )
        write_text_file(folder / "02_negative_prompt.md", character.negative_prompt, overwrite=overwrite)
        write_text_file(folder / "03_storyboard.md", _storyboard_markdown(storyboard, script, scenes), overwrite=overwrite)
        write_text_file(folder / "04_shot_list.csv", _shot_list_csv(scenes), overwrite=overwrite)
        write_text_file(folder / "05_voiceover_script.txt", script.script_text, overwrite=overwrite)
        write_text_file(picsart_dir / "picsart_processing_plan.md", _picsart_processing_plan(scenes), overwrite=overwrite)
        write_json_file(assets_dir / "required_assets.json", _required_assets_payload(scenes), overwrite=overwrite)
        write_text_file(folder / "license_notes.md", _license_notes(), overwrite=overwrite)
        write_json_file(folder / "storyboard_manifest.json", storyboard_manifest(session, storyboard.id), overwrite=overwrite)

        return create_prompt_pack(
            session,
            wizard_session_id=wizard_session_id,
            script_id=script.id,
            visual_plan_id=None,
            provider_name="higgsfield_manual",
            pack_type="nero_storyboard",
            title=f"Nero storyboard prompts - {script.topic.title if script.topic else script.id}",
            folder_path=str(folder),
            master_prompt_path=str(folder / "00_master_prompt.md"),
            scene_prompts_json=json.dumps(scene_files, ensure_ascii=False),
            negative_prompt=character.negative_prompt,
            style_reference=storyboard.visual_style,
            instructions_path=str(folder / "03_storyboard.md"),
            status=PromptPackStatus.GENERATED.value,
        )


def create_nero_higgsfield_prompt_pack(
    session: Session,
    *,
    storyboard_id: int,
    wizard_session_id: int | None = None,
    overwrite: bool = True,
) -> models.PromptPack:
    return HiggsfieldPromptPackService().export_for_storyboard(
        session,
        storyboard_id=storyboard_id,
        wizard_session_id=wizard_session_id,
        overwrite=overwrite,
    )


def _storyboard_prompt_pack_folder(script: models.Script, storyboard: models.VisualStoryboard) -> Path:
    topic_title = script.topic.title if script.topic else f"script-{script.id}"
    slug = slugify(topic_title)
    return safe_join(
        get_settings().output_dir,
        "external_tools",
        "higgsfield",
        "nero_storyboards",
        f"{today_folder_prefix()}_storyboard_{storyboard.id}_{slug}",
    )


def _master_prompt(
    storyboard: models.VisualStoryboard,
    script: models.Script,
    character: models.CharacterProfile,
    scenes: list[models.StoryboardScene],
) -> str:
    return f"""# Nero Higgsfield Master Prompt

Project: {script.topic.title if script.topic else f"Script {script.id}"}
Channel: Daily Brain Break
Character: {character.name}
Aspect ratio: {storyboard.aspect_ratio}
Target duration: {storyboard.target_duration_seconds} seconds

## Character Consistency
{character.master_prompt}

## Global Style
{storyboard.visual_style}

## Scene Count
{len(scenes)}

## Instructions
- Generate one original vertical 9:16 clip per scene prompt.
- Preserve Nero's identity exactly in every scene.
- Do not burn subtitles into clips.
- Do not include text, logos, watermarks, real movie footage, celebrities or copyrighted characters.
- Download each clip as `scene_01.mp4`, `scene_02.mp4`, etc.
- Import the clips back into ShortsFactory and map them to scenes.
"""


def _storyboard_markdown(
    storyboard: models.VisualStoryboard,
    script: models.Script,
    scenes: list[models.StoryboardScene],
) -> str:
    lines = [
        "# Nero Visual Storyboard",
        "",
        f"Script: {script.id}",
        f"Topic: {script.topic.title if script.topic else '-'}",
        f"Status: {storyboard.status}",
        "",
    ]
    for scene in scenes:
        lines.extend(
            [
                f"## Scene {scene.scene_number:02}",
                f"- Duration: {scene.duration_seconds:.2f}s",
                f"- Narration: {scene.narration_line}",
                f"- Action: {scene.on_screen_action}",
                f"- Pose: {scene.character_pose}",
                f"- Emotion: {scene.character_emotion}",
                f"- Variant: {scene.character_variant or 'default Nero'}",
                f"- Camera: {scene.camera_shot}; {scene.camera_motion}",
                f"- Background: {scene.background}",
                f"- Required assets: {scene.required_assets_json}",
                "",
            ]
        )
    return "\n".join(lines)


def _shot_list_csv(scenes: list[models.StoryboardScene]) -> str:
    rows = ["scene_number,duration_seconds,variant,pose,expected_clip,fit_mode"]
    for scene in scenes:
        rows.append(
            f"{scene.scene_number},{scene.duration_seconds:.2f},"
            f"{_csv(scene.character_variant or 'default')},{_csv(scene.character_pose)},"
            f"scene_{scene.scene_number:02}.mp4,cover"
        )
    return "\n".join(rows) + "\n"


def _picsart_processing_plan(scenes: list[models.StoryboardScene]) -> str:
    lines = ["# Picsart Processing Plan", ""]
    for scene in scenes:
        lines.extend(
            [
                f"## Scene {scene.scene_number:02}",
                "- Format: 1080x1920 vertical.",
                "- Fit: cover by default; avoid stretching Nero.",
                "- Keep Nero and main props clear of lower subtitle area.",
                "- Do not add text, captions, logos or watermarks.",
                f"- Notes: {scene.picsart_processing_notes or 'Clean color correction only.'}",
                "",
            ]
        )
    return "\n".join(lines)


def _required_assets_payload(scenes: list[models.StoryboardScene]) -> dict[str, object]:
    return {
        "assets": [
            {
                "scene_number": scene.scene_number,
                "required_assets": json.loads(scene.required_assets_json or "[]"),
                "expected_clip": f"scene_{scene.scene_number:02}.mp4",
                "license_required": True,
                "commercial_use_must_be_confirmed": True,
            }
            for scene in scenes
        ]
    }


def _license_notes() -> str:
    return """# License Notes

- Use only clips generated by you, licensed by you, or cleared for commercial use.
- Do not use real movie footage, protected logos, real celebrity likenesses, copied characters or copyrighted music.
- Confirm commercial-use status in ShortsFactory before render/export.
"""


def _csv(value: str) -> str:
    clean = value.replace('"', '""')
    return f'"{clean}"' if "," in clean else clean


def _get_storyboard(session: Session, storyboard_id: int) -> models.VisualStoryboard:
    storyboard = session.get(models.VisualStoryboard, storyboard_id)
    if storyboard is None:
        raise ValueError(f"VisualStoryboard not found: {storyboard_id}")
    return storyboard


def _get_script(session: Session, script_id: int) -> models.Script:
    script = session.get(models.Script, script_id)
    if script is None:
        raise ValueError(f"Script not found: {script_id}")
    return script


def _get_character(session: Session, character_id: int) -> models.CharacterProfile:
    character = session.get(models.CharacterProfile, character_id)
    if character is None:
        raise ValueError(f"CharacterProfile not found: {character_id}")
    return character
