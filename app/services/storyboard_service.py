from __future__ import annotations

import json
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.core.enums import ScriptStatus, StoryboardSceneStatus, VisualStoryboardStatus
from app.db import models
from app.db.repositories import add_and_commit
from app.services.character_service import get_default_character, list_character_variants


@dataclass(frozen=True)
class SceneDraft:
    scene_number: int
    narration_line: str
    duration_seconds: float
    on_screen_action: str
    character_pose: str
    character_emotion: str
    character_variant: str | None
    camera_shot: str
    camera_motion: str
    background: str
    props: list[str]
    visual_effects: list[str]
    required_assets: list[str]


class VisualStoryboardService:
    def create_from_script(
        self,
        session: Session,
        *,
        script_id: int,
        character_id: int | None = None,
        overwrite_existing: bool = False,
    ) -> models.VisualStoryboard:
        script = session.get(models.Script, script_id)
        if script is None:
            raise ValueError(f"Script not found: {script_id}")
        if script.status != ScriptStatus.APPROVED.value:
            raise ValueError("El guion debe estar aprobado antes de crear storyboard.")

        character = session.get(models.CharacterProfile, character_id) if character_id else get_default_character(session)
        if character is None:
            raise ValueError("No hay personaje default configurado.")

        if overwrite_existing:
            self._archive_existing(session, script.id)

        drafts = self._draft_scenes(session, script, character)
        storyboard = models.VisualStoryboard(
            script_id=script.id,
            character_id=character.id,
            visual_style=character.visual_style,
            total_scenes=len(drafts),
            aspect_ratio="9:16",
            target_duration_seconds=int(round(sum(item.duration_seconds for item in drafts))),
            global_prompt=character.master_prompt,
            global_negative_prompt=character.negative_prompt,
            status=VisualStoryboardStatus.GENERATED.value,
        )
        session.add(storyboard)
        session.commit()
        session.refresh(storyboard)

        for draft in drafts:
            session.add(self._scene_from_draft(storyboard, character, draft))
        session.commit()
        session.refresh(storyboard)
        return storyboard

    def regenerate_scene_prompt(self, session: Session, scene_id: int) -> models.StoryboardScene:
        scene = _get_scene(session, scene_id)
        storyboard = _get_storyboard(session, scene.storyboard_id)
        character = _get_character(session, storyboard.character_id)
        scene.higgsfield_prompt = build_scene_prompt(scene, storyboard, character)
        scene.negative_prompt = build_scene_negative_prompt(scene, character)
        scene.status = StoryboardSceneStatus.EDITED.value
        return add_and_commit(session, scene)

    def approve_scene(self, session: Session, scene_id: int) -> models.StoryboardScene:
        scene = _get_scene(session, scene_id)
        scene.status = StoryboardSceneStatus.APPROVED.value
        return add_and_commit(session, scene)

    def approve_storyboard(self, session: Session, storyboard_id: int) -> models.VisualStoryboard:
        storyboard = _get_storyboard(session, storyboard_id)
        storyboard.status = VisualStoryboardStatus.APPROVED.value
        return add_and_commit(session, storyboard)

    def _archive_existing(self, session: Session, script_id: int) -> None:
        existing = session.scalars(
            select(models.VisualStoryboard).where(models.VisualStoryboard.script_id == script_id)
        ).all()
        for storyboard in existing:
            storyboard.status = VisualStoryboardStatus.ARCHIVED.value
        session.commit()

    def _draft_scenes(
        self,
        session: Session,
        script: models.Script,
        character: models.CharacterProfile,
    ) -> list[SceneDraft]:
        variants = list_character_variants(session, character.id)
        category = script.topic.category if script.topic else "other"
        selected_variant = _choose_variant(category, variants)
        lines = _script_lines(script)
        return [
            _draft_scene(
                scene_number=index,
                narration_line=line["text"],
                duration_seconds=line["duration_seconds"],
                category=category,
                variant=selected_variant,
            )
            for index, line in enumerate(lines, start=1)
        ]

    def _scene_from_draft(
        self,
        storyboard: models.VisualStoryboard,
        character: models.CharacterProfile,
        draft: SceneDraft,
    ) -> models.StoryboardScene:
        scene = models.StoryboardScene(
            storyboard_id=storyboard.id,
            scene_number=draft.scene_number,
            duration_seconds=draft.duration_seconds,
            narration_line=draft.narration_line,
            on_screen_action=draft.on_screen_action,
            character_pose=draft.character_pose,
            character_emotion=draft.character_emotion,
            character_variant=draft.character_variant,
            camera_shot=draft.camera_shot,
            camera_motion=draft.camera_motion,
            background=draft.background,
            props_json=json.dumps(draft.props, ensure_ascii=False),
            visual_effects_json=json.dumps(draft.visual_effects, ensure_ascii=False),
            transition_in="cut" if draft.scene_number == 1 else "quick_match_cut",
            transition_out="quick_cut",
            picsart_processing_notes=_picsart_notes(draft),
            required_assets_json=json.dumps(draft.required_assets, ensure_ascii=False),
            status=StoryboardSceneStatus.GENERATED.value,
        )
        scene.negative_prompt = build_scene_negative_prompt(scene, character)
        scene.higgsfield_prompt = build_scene_prompt(scene, storyboard, character)
        return scene


def list_storyboards_for_script(session: Session, script_id: int) -> list[models.VisualStoryboard]:
    return list(
        session.scalars(
            select(models.VisualStoryboard)
            .where(models.VisualStoryboard.script_id == script_id)
            .order_by(models.VisualStoryboard.created_at.desc())
        ).all()
    )


def list_storyboard_scenes(session: Session, storyboard_id: int) -> list[models.StoryboardScene]:
    return list(
        session.scalars(
            select(models.StoryboardScene)
            .where(models.StoryboardScene.storyboard_id == storyboard_id)
            .order_by(models.StoryboardScene.scene_number)
        ).all()
    )


def build_scene_prompt(
    scene: models.StoryboardScene,
    storyboard: models.VisualStoryboard,
    character: models.CharacterProfile,
) -> str:
    props = ", ".join(_json_list(scene.props_json)) or "no extra props"
    effects = ", ".join(_json_list(scene.visual_effects_json)) or "subtle clean motion"
    variant_line = f"Variant: {scene.character_variant}." if scene.character_variant else "Variant: default Nero."
    return f"""Create a vertical 9:16 short video scene in a colorful polished cartoon style.

Main character:
{character.canonical_description}
Preserve Nero's identity exactly across the whole Short.

{variant_line}

Narration line:
{scene.narration_line}

Scene:
{scene.background}

Action:
{scene.on_screen_action}

Emotion and pose:
Nero is {scene.character_emotion}. Pose: {scene.character_pose}.

Camera:
{scene.camera_shot}, {scene.camera_motion}.

Props:
{props}

Visual effects:
{effects}

Style:
{storyboard.visual_style}

Duration:
Approximately {scene.duration_seconds:.2f} seconds.

Important:
No text, no captions, no subtitles, no logos, no watermark, no copyrighted material, no real movie footage, no celebrity likeness.

Negative prompt:
{scene.negative_prompt}
"""


def build_scene_negative_prompt(scene: models.StoryboardScene, character: models.CharacterProfile) -> str:
    fragments = [character.negative_prompt]
    if scene.character_variant:
        fragments.append("Costume variants may add props or clothing only; they must not change Nero's core identity.")
    return " ".join(fragment.strip() for fragment in fragments if fragment.strip())


def storyboard_manifest(session: Session, storyboard_id: int) -> dict[str, object]:
    storyboard = _get_storyboard(session, storyboard_id)
    character = _get_character(session, storyboard.character_id)
    scenes = list_storyboard_scenes(session, storyboard.id)
    return {
        "storyboard_id": storyboard.id,
        "script_id": storyboard.script_id,
        "character": character.name,
        "aspect_ratio": storyboard.aspect_ratio,
        "target_duration_seconds": storyboard.target_duration_seconds,
        "status": storyboard.status,
        "scenes": [
            {
                "scene_number": scene.scene_number,
                "duration_seconds": scene.duration_seconds,
                "narration_line": scene.narration_line,
                "character_pose": scene.character_pose,
                "character_emotion": scene.character_emotion,
                "character_variant": scene.character_variant,
                "background": scene.background,
                "required_assets": _json_list(scene.required_assets_json),
                "external_asset_id": scene.external_asset_id,
                "status": scene.status,
            }
            for scene in scenes
        ],
    }


def _script_lines(script: models.Script) -> list[dict[str, object]]:
    if script.lines:
        return [
            {
                "text": line.text.strip(),
                "duration_seconds": float(line.duration_seconds or 2.5),
            }
            for line in script.lines
            if line.text.strip()
        ]
    raw_lines = [line.strip() for line in script.script_text.splitlines() if line.strip()]
    if not raw_lines:
        raw_lines = [script.script_text.strip() or "Nero introduces the topic."]
    default_duration = max(1.5, float(script.estimated_duration_seconds or get_settings().target_duration_seconds) / len(raw_lines))
    return [{"text": line, "duration_seconds": default_duration} for line in raw_lines]


def _choose_variant(category: str, variants: list[models.CharacterVariant]) -> str | None:
    if not variants:
        return None
    category_map = {
        "ai_tools": "nero_scientist",
        "tech_explained": "nero_scientist",
        "science_explained": "nero_scientist",
        "history_explained": "nero_historian",
        "mystery_explained": "nero_historian",
        "internet_culture_explained": "nero_movie_detective",
        "business_case": "nero_movie_detective",
    }
    target_name = category_map.get(category, "nero_movie_detective")
    if any(variant.name == target_name for variant in variants):
        return target_name
    return variants[0].name


def _draft_scene(
    *,
    scene_number: int,
    narration_line: str,
    duration_seconds: float,
    category: str,
    variant: str | None,
) -> SceneDraft:
    visual_profile = _category_visual_profile(category)
    if scene_number == 1:
        pose = "pointing_surprised"
        emotion = "surprised and curious"
        action = f"Nero reacts to the main visual hook, points at it, then looks back to camera: {narration_line}"
        camera = "medium shot"
        motion = "smooth slight zoom toward the visual hook"
    else:
        pose = "frontal_explaining" if scene_number % 2 else "thinking"
        emotion = "friendly and clever" if scene_number % 2 else "thoughtful curiosity"
        action = f"Nero explains the next beat with expressive gestures: {narration_line}"
        camera = "vertical medium shot"
        motion = "subtle push-in with gentle parallax"
    return SceneDraft(
        scene_number=scene_number,
        narration_line=narration_line,
        duration_seconds=duration_seconds,
        on_screen_action=action,
        character_pose=pose,
        character_emotion=emotion,
        character_variant=variant,
        camera_shot=camera,
        camera_motion=motion,
        background=visual_profile["background"],
        props=list(visual_profile["props"]),
        visual_effects=list(visual_profile["effects"]),
        required_assets=[f"scene_{scene_number:02}_vertical_clip"],
    )


def _category_visual_profile(category: str) -> dict[str, object]:
    profiles = {
        "tech_explained": {
            "background": "A friendly futuristic classroom with holograms, screens and simple educational shapes.",
            "props": ["hologram", "floating diagram", "soft glowing UI panels"],
            "effects": ["soft glow", "clean parallax", "subtle zoom"],
        },
        "science_explained": {
            "background": "A bright cartoon science lab with friendly equipment and floating simplified diagrams.",
            "props": ["beaker", "whiteboard", "floating science icon"],
            "effects": ["sparkle highlights", "soft glow", "subtle camera drift"],
        },
        "history_explained": {
            "background": "A stylized museum space with old maps, parchment and a generic timeline wall.",
            "props": ["old map", "scroll", "small magnifying glass"],
            "effects": ["paper texture", "warm light", "timeline reveal"],
        },
        "internet_culture_explained": {
            "background": "A colorful trend map room with generic screens, charts and abstract meme-like shapes.",
            "props": ["generic trend chart", "abstract icons", "magnifying glass"],
            "effects": ["screen glow", "pop transitions", "clean motion graphics"],
        },
        "mystery_explained": {
            "background": "A soft mysterious study room with maps, question marks and warm cinematic shadows.",
            "props": ["map", "magnifying glass", "mystery object"],
            "effects": ["soft shadows", "spotlight", "slow push-in"],
        },
    }
    return profiles.get(
        category,
        {
            "background": "A colorful Daily Brain Break studio with friendly educational props and clean shapes.",
            "props": ["floating clue", "simple diagram", "Nero pointer"],
            "effects": ["soft glow", "subtle zoom", "clean parallax"],
        },
    )


def _picsart_notes(draft: SceneDraft) -> str:
    return (
        "Fit generated clip to 1080x1920. Keep Nero and key props away from the lower subtitle area. "
        "Do not add text, logos, watermarks or copyrighted material."
    )


def _json_list(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        decoded = json.loads(value)
    except json.JSONDecodeError:
        return []
    return [str(item) for item in decoded] if isinstance(decoded, list) else []


def _get_storyboard(session: Session, storyboard_id: int) -> models.VisualStoryboard:
    storyboard = session.get(models.VisualStoryboard, storyboard_id)
    if storyboard is None:
        raise ValueError(f"VisualStoryboard not found: {storyboard_id}")
    return storyboard


def _get_scene(session: Session, scene_id: int) -> models.StoryboardScene:
    scene = session.get(models.StoryboardScene, scene_id)
    if scene is None:
        raise ValueError(f"StoryboardScene not found: {scene_id}")
    return scene


def _get_character(session: Session, character_id: int) -> models.CharacterProfile:
    character = session.get(models.CharacterProfile, character_id)
    if character is None:
        raise ValueError(f"CharacterProfile not found: {character_id}")
    return character
