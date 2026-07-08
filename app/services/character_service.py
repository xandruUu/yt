from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.db import models
from app.db.repositories import add_and_commit
from app.utils.files import write_text_file
from app.utils.safe_paths import safe_join

NERO_SLUG = "nero"
DAILY_BRAIN_BREAK_CHANNEL = "Daily Brain Break"

NERO_SHORT_DESCRIPTION = (
    "Nero is a relaxed, curious and friendly cartoon brain who explains weird facts, "
    "history moments, movie lore, science and internet stories in short visual videos."
)

NERO_CANONICAL_DESCRIPTION = (
    "Nero is a cute anthropomorphic pink cartoon brain mascot with a rounded brain-shaped "
    "head/body, visible soft brain folds, large expressive white eyes with black pupils, "
    "thick black eyebrows, a wide friendly smile, small rosy cheek highlights, thin pink "
    "cartoon arms and legs, red shorts, a black belt with a silver buckle, and red-and-white "
    "sneakers. He has a playful polished cartoon style with clean outlines, vibrant colors, "
    "soft shading and a cheerful educational tone."
)

NERO_MASTER_PROMPT = (
    "Nero is a cute anthropomorphic pink cartoon brain mascot and the recurring host of the "
    "YouTube Shorts channel Daily Brain Break. He has a rounded brain-shaped head/body with "
    "stylized soft brain folds, large expressive white eyes with black pupils, thick black "
    "eyebrows, a wide friendly smile, small rosy cheek highlights, thin pink cartoon arms and "
    "legs, red shorts, a black belt with a silver buckle, and red-and-white sneakers. His "
    "style is colorful, clean, polished, friendly, educational and playful, with crisp cartoon "
    "outlines, vibrant colors and soft shading. Nero is curious, relaxed, funny, expressive "
    "and clever. He should always look like the same character across scenes, even when "
    "wearing temporary costumes or props."
)

NERO_NEGATIVE_PROMPT = (
    "Do not change Nero's identity. Do not make him realistic, anatomical, grotesque, "
    "horror-like, bloody, scary, ugly or overly detailed. Do not turn him into a human, "
    "animal, robot or different creature. Do not remove his large eyes, thick eyebrows, "
    "friendly smile, red shorts, black belt or red-and-white sneakers unless a controlled "
    "costume variant explicitly covers them. Do not add extra limbs, distorted hands, "
    "malformed legs, duplicate faces, wrong eye direction, inconsistent clothing, random "
    "logos, text, subtitles, captions, watermarks or copyrighted characters. Do not use real "
    "movie footage, real celebrity likenesses or protected brand logos."
)

NERO_REQUIRED_TRAITS = [
    "Pink cartoon brain body/head.",
    "Visible stylized brain folds.",
    "Big expressive eyes.",
    "Thick black eyebrows.",
    "Wide friendly smile.",
    "Thin cartoon arms and legs.",
    "Red shorts.",
    "Black belt with silver buckle.",
    "Red-and-white sneakers.",
    "Friendly polished cartoon aesthetic.",
    "Educational but fun tone.",
]

NERO_FORBIDDEN_TRAITS = [
    "Do not make Nero realistic.",
    "Do not make Nero grotesque.",
    "Do not make Nero horror-like.",
    "Do not make Nero bloody or anatomical.",
    "Do not turn Nero into a human.",
    "Do not change his face structure.",
    "Do not remove the big eyes.",
    "Do not remove the thick eyebrows.",
    "Do not remove the red shorts unless using a controlled costume variant.",
    "Do not add random extra limbs.",
    "Do not add text inside generated clips unless explicitly requested.",
    "Do not use copyrighted characters, logos or movie footage.",
]

DEFAULT_POSES = [
    {
        "name": "frontal_explaining",
        "description": "Nero faces the camera and explains a fact with a friendly smile.",
        "camera_angle": "front medium shot",
        "body_orientation": "facing camera",
        "emotion": "curious and friendly",
        "prompt_fragment": "Nero faces the viewer, one hand raised as if explaining a quick fact.",
        "negative_prompt_fragment": "Do not change Nero's body, face or outfit.",
    },
    {
        "name": "pointing_surprised",
        "description": "Nero points at an object or clue with surprised curiosity.",
        "camera_angle": "3/4 medium shot",
        "body_orientation": "three-quarter toward object",
        "emotion": "surprised and curious",
        "prompt_fragment": "Nero points at the key visual clue, eyebrows raised, excited smile.",
        "negative_prompt_fragment": "No extra fingers, no distorted hands, no text.",
    },
    {
        "name": "thinking",
        "description": "Nero pauses, thinking through a mystery or explanation.",
        "camera_angle": "close medium shot",
        "body_orientation": "slight three-quarter",
        "emotion": "thoughtful",
        "prompt_fragment": "Nero looks thoughtful, one hand near his chin, eyes focused.",
        "negative_prompt_fragment": "Do not make Nero sad, scary, realistic or anatomical.",
    },
]

DEFAULT_VARIANTS = [
    {
        "name": "nero_scientist",
        "description": "Science and technology explainer Nero.",
        "allowed_changes": ["white lab coat", "safety goggles", "small hologram props"],
        "must_preserve": NERO_REQUIRED_TRAITS,
        "outfit_description": "A lightweight white lab coat over Nero's red shorts, optional goggles.",
        "use_cases": ["science_explained", "tech_explained", "ai_tools"],
        "prompt_fragment": "Nero wears a small white lab coat and optional goggles while keeping his red shorts visible.",
        "negative_prompt_fragment": "Do not hide Nero's eyes, eyebrows, smile, red shorts or sneakers.",
    },
    {
        "name": "nero_historian",
        "description": "History and ancient mystery explainer Nero.",
        "allowed_changes": ["tiny explorer hat", "map", "scroll", "museum props"],
        "must_preserve": NERO_REQUIRED_TRAITS,
        "outfit_description": "A small explorer hat and a satchel, with Nero's core outfit preserved.",
        "use_cases": ["history_explained", "mystery_explained"],
        "prompt_fragment": "Nero wears a small explorer hat and holds an old map or scroll.",
        "negative_prompt_fragment": "No real historical figures, no protected symbols, no realistic anatomy.",
    },
    {
        "name": "nero_movie_detective",
        "description": "Movie lore explainer without protected characters or real footage.",
        "allowed_changes": ["director cap", "film reel", "magnifying glass", "generic clapperboard"],
        "must_preserve": NERO_REQUIRED_TRAITS,
        "outfit_description": "A tiny director cap or detective prop while preserving Nero's core look.",
        "use_cases": ["business_case", "internet_culture_explained", "other"],
        "prompt_fragment": "Nero holds a magnifying glass and a generic film reel in a parody explainer setting.",
        "negative_prompt_fragment": "No copyrighted characters, no movie logos, no real actors, no official-looking footage.",
    },
]


def seed_nero_character_system(session: Session) -> models.CharacterProfile:
    character = get_character_by_slug(session, NERO_SLUG)
    if character is None:
        character = models.CharacterProfile(**nero_profile_payload())
        session.add(character)
        session.commit()
        session.refresh(character)
    else:
        character.is_default = True
        add_and_commit(session, character)

    _seed_poses(session, character)
    _seed_variants(session, character)
    return character


def nero_profile_payload() -> dict[str, Any]:
    return {
        "name": "Nero",
        "slug": NERO_SLUG,
        "role": "Host, narrator and mascot of Daily Brain Break.",
        "short_description": NERO_SHORT_DESCRIPTION,
        "canonical_description": NERO_CANONICAL_DESCRIPTION,
        "master_prompt": NERO_MASTER_PROMPT,
        "negative_prompt": NERO_NEGATIVE_PROMPT,
        "visual_style": "Colorful polished 2D/3D cartoon style, clean outlines, soft shading, 9:16 friendly explainer visuals.",
        "personality": "Curious, relaxed, funny, expressive, clever, friendly, slightly surprised by weird facts, but never arrogant.",
        "speaking_style": "Fast, clear, punchy, curious and simple. Short sentences. Strong hooks. No long academic paragraphs.",
        "default_outfit": "Red shorts, black belt with silver buckle, red-and-white sneakers.",
        "required_traits_json": json.dumps(NERO_REQUIRED_TRAITS, ensure_ascii=False),
        "forbidden_traits_json": json.dumps(NERO_FORBIDDEN_TRAITS, ensure_ascii=False),
        "color_palette_json": json.dumps(
            {
                "brain_pink": "#f58bc4",
                "shorts_red": "#e73632",
                "sneaker_white": "#ffffff",
                "outline": "#1e1e1e",
                "belt_black": "#111111",
            },
            ensure_ascii=False,
        ),
        "proportions_json": json.dumps(
            {
                "head_body": "rounded brain-shaped head/body",
                "limbs": "thin cartoon arms and legs",
                "eyes": "large expressive eyes",
            },
            ensure_ascii=False,
        ),
        "reference_image_paths_json": "[]",
        "is_default": True,
    }


def get_default_character(session: Session) -> models.CharacterProfile:
    character = session.scalar(select(models.CharacterProfile).where(models.CharacterProfile.is_default.is_(True)))
    if character is not None:
        return character
    return seed_nero_character_system(session)


def get_character_by_slug(session: Session, slug: str) -> models.CharacterProfile | None:
    return session.scalar(select(models.CharacterProfile).where(models.CharacterProfile.slug == slug))


def list_character_poses(session: Session, character_id: int) -> list[models.CharacterPose]:
    return list(
        session.scalars(
            select(models.CharacterPose)
            .where(models.CharacterPose.character_id == character_id)
            .order_by(models.CharacterPose.name)
        ).all()
    )


def list_character_variants(session: Session, character_id: int) -> list[models.CharacterVariant]:
    return list(
        session.scalars(
            select(models.CharacterVariant)
            .where(models.CharacterVariant.character_id == character_id)
            .order_by(models.CharacterVariant.name)
        ).all()
    )


def character_bible_markdown(
    character: models.CharacterProfile,
    poses: list[models.CharacterPose] | None = None,
    variants: list[models.CharacterVariant] | None = None,
) -> str:
    poses = poses or []
    variants = variants or []
    required = _json_list(character.required_traits_json)
    forbidden = _json_list(character.forbidden_traits_json)
    pose_lines = "\n".join(f"- {pose.name}: {pose.description}" for pose in poses) or "- No poses saved yet."
    variant_lines = "\n".join(
        f"- {variant.name}: {variant.description}. Outfit: {variant.outfit_description}"
        for variant in variants
    ) or "- No variants saved yet."
    return f"""# Character Bible: {character.name}

## Channel
Daily Brain Break

## Role
{character.role}

## Short Description
{character.short_description}

## Canonical Visual Description
{character.canonical_description}

## Personality
{character.personality}

## Speaking Style
{character.speaking_style}

## Default Outfit
{character.default_outfit}

## Required Traits
{_markdown_list(required)}

## Forbidden Traits
{_markdown_list(forbidden)}

## Master Prompt
{character.master_prompt}

## Negative Prompt
{character.negative_prompt}

## Poses
{pose_lines}

## Variants
{variant_lines}
"""


def export_character_bible_markdown(
    session: Session,
    character_id: int,
    output_dir: str | Path | None = None,
    overwrite: bool = True,
) -> Path:
    character = session.get(models.CharacterProfile, character_id)
    if character is None:
        raise ValueError(f"CharacterProfile not found: {character_id}")
    base_dir = Path(output_dir) if output_dir else safe_join(get_settings().output_dir, "character_bibles")
    path = base_dir / f"{character.slug}_character_bible.md"
    content = character_bible_markdown(
        character,
        poses=list_character_poses(session, character.id),
        variants=list_character_variants(session, character.id),
    )
    return write_text_file(path, content, overwrite=overwrite)


def update_character_profile(session: Session, character_id: int, **data: Any) -> models.CharacterProfile:
    character = session.get(models.CharacterProfile, character_id)
    if character is None:
        raise ValueError(f"CharacterProfile not found: {character_id}")
    for key, value in data.items():
        setattr(character, key, value)
    return add_and_commit(session, character)


def _seed_poses(session: Session, character: models.CharacterProfile) -> None:
    existing = {
        pose.name
        for pose in session.scalars(
            select(models.CharacterPose).where(models.CharacterPose.character_id == character.id)
        ).all()
    }
    for payload in DEFAULT_POSES:
        if payload["name"] not in existing:
            session.add(models.CharacterPose(character_id=character.id, **payload))
    session.commit()


def _seed_variants(session: Session, character: models.CharacterProfile) -> None:
    existing = {
        variant.name
        for variant in session.scalars(
            select(models.CharacterVariant).where(models.CharacterVariant.character_id == character.id)
        ).all()
    }
    for payload in DEFAULT_VARIANTS:
        if payload["name"] in existing:
            continue
        session.add(
            models.CharacterVariant(
                character_id=character.id,
                name=payload["name"],
                description=payload["description"],
                allowed_changes_json=json.dumps(payload["allowed_changes"], ensure_ascii=False),
                must_preserve_json=json.dumps(payload["must_preserve"], ensure_ascii=False),
                outfit_description=payload["outfit_description"],
                use_cases_json=json.dumps(payload["use_cases"], ensure_ascii=False),
                prompt_fragment=payload["prompt_fragment"],
                negative_prompt_fragment=payload["negative_prompt_fragment"],
            )
        )
    session.commit()


def _json_list(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        decoded = json.loads(value)
    except json.JSONDecodeError:
        return []
    return [str(item) for item in decoded] if isinstance(decoded, list) else []


def _markdown_list(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items) if items else "- None"
