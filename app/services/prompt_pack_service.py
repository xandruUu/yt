from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.core.enums import PromptPackStatus
from app.db import models
from app.db.repositories import add_and_commit, create_prompt_pack
from app.services.visual_plan_service import visual_plan_scenes
from app.utils.files import ensure_dir, write_json_file, write_text_file
from app.utils.safe_paths import safe_join
from app.utils.slugs import slugify
from app.utils.time import today_folder_prefix

NEGATIVE_PROMPT = (
    "no copyrighted characters, no real logos, no real people unless explicitly licensed, "
    "no gore, no text artifacts, no watermark, no subtitles burned in"
)


def create_higgsfield_prompt_pack(
    session: Session,
    *,
    script_id: int,
    visual_plan_id: int,
    wizard_session_id: int | None = None,
    overwrite: bool = True,
) -> models.PromptPack:
    script, visual_plan = _load_script_and_visual_plan(session, script_id, visual_plan_id)
    scenes = visual_plan_scenes(visual_plan)
    folder = _prompt_pack_folder("higgsfield", script)
    ensure_dir(folder / "scene_prompts")
    scene_files = []
    for scene in scenes:
        content = _higgsfield_scene_prompt(scene, visual_plan)
        scene_path = folder / "scene_prompts" / f"scene_{int(scene.get('order') or len(scene_files) + 1):02}.txt"
        write_text_file(scene_path, content, overwrite=overwrite)
        scene_files.append({"order": scene.get("order"), "path": str(scene_path), "prompt": content})

    master_prompt = _higgsfield_master_prompt(script, visual_plan, scenes)
    readme = _higgsfield_readme(script)
    write_text_file(folder / "README_HIGGSFIELD.md", readme, overwrite=overwrite)
    write_text_file(folder / "master_prompt.md", master_prompt, overwrite=overwrite)
    write_text_file(folder / "negative_prompt.txt", NEGATIVE_PROMPT, overwrite=overwrite)
    write_text_file(folder / "visual_style.md", visual_plan.global_style, overwrite=overwrite)
    write_text_file(folder / "voiceover_script.txt", script.script_text, overwrite=overwrite)
    write_text_file(folder / "shot_list.csv", _shot_list_csv(scenes), overwrite=overwrite)
    write_json_file(folder / "scene_prompts.json", {"scenes": scene_files}, overwrite=overwrite)

    return create_prompt_pack(
        session,
        wizard_session_id=wizard_session_id,
        script_id=script.id,
        visual_plan_id=visual_plan.id,
        provider_name="higgsfield_manual",
        pack_type="higgsfield",
        title=f"Higgsfield prompts - {script.topic.title}",
        folder_path=str(folder),
        master_prompt_path=str(folder / "master_prompt.md"),
        scene_prompts_json=json.dumps(scene_files, ensure_ascii=False),
        negative_prompt=NEGATIVE_PROMPT,
        style_reference=visual_plan.global_style,
        instructions_path=str(folder / "README_HIGGSFIELD.md"),
        status=PromptPackStatus.GENERATED.value,
    )


def create_picsart_prompt_pack(
    session: Session,
    *,
    script_id: int,
    visual_plan_id: int,
    wizard_session_id: int | None = None,
    overwrite: bool = True,
) -> models.PromptPack:
    script, visual_plan = _load_script_and_visual_plan(session, script_id, visual_plan_id)
    scenes = visual_plan_scenes(visual_plan)
    folder = _prompt_pack_folder("picsart", script)
    ensure_dir(folder)
    scene_map = [_picsart_scene_instruction(scene) for scene in scenes]
    write_text_file(folder / "README_PICSART.md", _picsart_readme(script), overwrite=overwrite)
    write_text_file(folder / "asset_processing_plan.md", _picsart_processing_plan(scene_map), overwrite=overwrite)
    write_text_file(folder / "clip_processing_plan.csv", _picsart_clip_csv(scene_map), overwrite=overwrite)
    write_json_file(folder / "scene_asset_map.json", {"scenes": scene_map}, overwrite=overwrite)
    write_text_file(folder / "resize_crop_instructions.md", _picsart_resize_instructions(), overwrite=overwrite)
    write_text_file(folder / "background_instructions.md", _picsart_background_instructions(), overwrite=overwrite)

    return create_prompt_pack(
        session,
        wizard_session_id=wizard_session_id,
        script_id=script.id,
        visual_plan_id=visual_plan.id,
        provider_name="picsart_manual",
        pack_type="picsart",
        title=f"Picsart processing - {script.topic.title}",
        folder_path=str(folder),
        master_prompt_path=str(folder / "asset_processing_plan.md"),
        scene_prompts_json=json.dumps(scene_map, ensure_ascii=False),
        negative_prompt=None,
        style_reference=visual_plan.global_style,
        instructions_path=str(folder / "README_PICSART.md"),
        status=PromptPackStatus.GENERATED.value,
    )


def create_generic_video_prompt_pack(
    session: Session,
    *,
    script_id: int,
    visual_plan_id: int,
    wizard_session_id: int | None = None,
    overwrite: bool = True,
) -> models.PromptPack:
    script, visual_plan = _load_script_and_visual_plan(session, script_id, visual_plan_id)
    folder = _prompt_pack_folder("generic", script)
    ensure_dir(folder)
    scenes = visual_plan_scenes(visual_plan)
    instructions = _generic_prompt_pack(script, visual_plan, scenes)
    write_text_file(folder / "generic_video_prompt_pack.md", instructions, overwrite=overwrite)
    return create_prompt_pack(
        session,
        wizard_session_id=wizard_session_id,
        script_id=script.id,
        visual_plan_id=visual_plan.id,
        provider_name="generic_manual",
        pack_type="generic",
        title=f"Generic video prompts - {script.topic.title}",
        folder_path=str(folder),
        master_prompt_path=str(folder / "generic_video_prompt_pack.md"),
        scene_prompts_json=json.dumps(scenes, ensure_ascii=False),
        instructions_path=str(folder / "generic_video_prompt_pack.md"),
        status=PromptPackStatus.GENERATED.value,
    )


def mark_prompt_pack_used_manually(session: Session, prompt_pack_id: int) -> models.PromptPack:
    pack = session.get(models.PromptPack, prompt_pack_id)
    if pack is None:
        raise ValueError(f"PromptPack not found: {prompt_pack_id}")
    pack.status = PromptPackStatus.USED_MANUALLY.value
    return add_and_commit(session, pack)


def _load_script_and_visual_plan(
    session: Session,
    script_id: int,
    visual_plan_id: int,
) -> tuple[models.Script, models.VisualPlan]:
    script = session.get(models.Script, script_id)
    visual_plan = session.get(models.VisualPlan, visual_plan_id)
    if script is None:
        raise ValueError(f"Script not found: {script_id}")
    if visual_plan is None:
        raise ValueError(f"VisualPlan not found: {visual_plan_id}")
    if visual_plan.script_id != script.id:
        raise ValueError("El plan visual no pertenece a este guion.")
    return script, visual_plan


def _prompt_pack_folder(provider: str, script: models.Script) -> Path:
    slug = slugify(script.topic.title if script.topic else f"script-{script.id}")
    return safe_join(get_settings().output_dir, "external_tools", provider, f"{today_folder_prefix()}_{slug}")


def _higgsfield_scene_prompt(scene: dict[str, Any], visual_plan: models.VisualPlan) -> str:
    return f"""Scene {int(scene.get("order") or 1)}

Narration:
{scene.get("text", "")}

Duration:
{float(scene.get("duration_seconds") or 2.5):.2f} seconds

Aspect ratio:
9:16 vertical

Visual prompt:
{scene.get("visual_prompt", "")}

Camera/motion:
{scene.get("animation", "subtle_push")}

Style:
{visual_plan.global_style}

Avoid:
{NEGATIVE_PROMPT}
"""


def _higgsfield_master_prompt(
    script: models.Script,
    visual_plan: models.VisualPlan,
    scenes: list[dict[str, Any]],
) -> str:
    total_duration = sum(float(scene.get("duration_seconds") or 2.5) for scene in scenes)
    scene_lines = "\n".join(
        f"- Scene {scene.get('order')}: {scene.get('visual_prompt')} ({scene.get('duration_seconds')}s)"
        for scene in scenes
    )
    return f"""# Higgsfield Master Prompt

Objective:
Create original vertical 9:16 visual clips for a YouTube Short about "{script.topic.title}".

Language:
{script.language}

Tone:
{script.tone}

Visual style:
{visual_plan.global_style}

Total duration:
{total_duration:.2f} seconds

Scene structure:
{scene_lines}

Instructions:
- Keep visual continuity across all scenes.
- Do not add burned-in subtitles or on-screen text artifacts.
- Do not add voices; the voiceover is generated/imported separately in ShortsFactory.
- Avoid copyrighted characters, real logos, celebrities, watermarks and protected material.
- Generate safe, original, monetization-friendly visuals.
"""


def _higgsfield_readme(script: models.Script) -> str:
    return f"""# Higgsfield prompt pack

Project: {script.topic.title}

1. Open `master_prompt.md` in Higgsfield.
2. Generate one vertical 9:16 clip per file in `scene_prompts/`.
3. Do not burn subtitles into the clips.
4. Download the clips.
5. Import them back into ShortsFactory from `Herramientas externas`.
6. Confirm license/commercial-use status before render/export.
"""


def _shot_list_csv(scenes: list[dict[str, Any]]) -> str:
    rows = ["scene_order,duration_seconds,visual_type,expected_output"]
    for scene in scenes:
        order = int(scene.get("order") or 1)
        rows.append(
            f"{order},{float(scene.get('duration_seconds') or 2.5):.2f},"
            f"{scene.get('visual_type', '')},scene_{order:02}.mp4"
        )
    return "\n".join(rows) + "\n"


def _picsart_scene_instruction(scene: dict[str, Any]) -> dict[str, object]:
    order = int(scene.get("order") or 1)
    return {
        "scene_order": order,
        "duration_seconds": float(scene.get("duration_seconds") or 2.5),
        "operation": "fit_9_16",
        "crop": "1080x1920 vertical, avoid distortion",
        "background": "extend or blur background if needed",
        "color": "increase clarity and contrast without heavy filters",
        "thumbnail": order == 1,
        "expected_output": f"scene_{order:02}_processed.mp4",
    }


def _picsart_processing_plan(scene_map: list[dict[str, object]]) -> str:
    lines = ["# Picsart asset processing plan", ""]
    for item in scene_map:
        lines.extend(
            [
                f"## Scene {item['scene_order']}",
                f"- Target duration: {item['duration_seconds']} seconds",
                f"- Operation: {item['operation']}",
                f"- Crop/fit: {item['crop']}",
                f"- Background: {item['background']}",
                f"- Color: {item['color']}",
                f"- Expected output: `{item['expected_output']}`",
                "",
            ]
        )
    return "\n".join(lines)


def _picsart_clip_csv(scene_map: list[dict[str, object]]) -> str:
    rows = ["scene_order,operation,duration_seconds,expected_output"]
    for item in scene_map:
        rows.append(
            f"{item['scene_order']},{item['operation']},{item['duration_seconds']},{item['expected_output']}"
        )
    return "\n".join(rows) + "\n"


def _picsart_readme(script: models.Script) -> str:
    return f"""# Picsart processing pack

Project: {script.topic.title}

Use this pack to process locally imported or externally generated clips in Picsart.
Do not use third-party material without license. Import processed results back into ShortsFactory and approve commercial-use status before render/export.
"""


def _picsart_resize_instructions() -> str:
    return """# Resize/crop instructions

- Final format: 1080x1920 vertical, 9:16.
- Prefer crop/fit over stretching.
- If the source is horizontal, use smart crop or blurred/extended background.
- Keep important subject away from subtitle area.
"""


def _picsart_background_instructions() -> str:
    return """# Background instructions

- Remove/change background only for assets you own or generated yourself.
- Avoid logos, celebrities, copyrighted characters and watermarks.
- Keep visual continuity with the ShortsFactory visual plan.
"""


def _generic_prompt_pack(
    script: models.Script,
    visual_plan: models.VisualPlan,
    scenes: list[dict[str, Any]],
) -> str:
    scene_blocks = "\n\n".join(_higgsfield_scene_prompt(scene, visual_plan) for scene in scenes)
    return f"""# Generic video prompt pack

Project: {script.topic.title}

Use these prompts in any video/image generation tool that supports vertical scenes.
Do not generate burned-in subtitles, voices, copyrighted characters, logos, real people, gore or watermarks.

{scene_blocks}
"""
