from __future__ import annotations

import hashlib
from io import BytesIO
from pathlib import Path

from PIL import Image
from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.db import models
from app.db.repositories import add_and_commit
from app.services.character_service import list_character_cells
from app.utils.safe_paths import safe_join
from app.utils.slugs import slugify

CELL_TYPES = (
    "front",
    "profile_left",
    "profile_right",
    "three_quarter",
    "back",
    "pose",
    "expression",
    "action",
    "outfit",
    "detail",
    "prop",
    "other",
)


def create_character_skin(
    session: Session,
    *,
    family_id: int | None,
    name: str,
    short_description: str,
    canonical_description: str,
    visual_style: str = "",
    personality: str = "",
    role: str = "",
) -> models.CharacterProfile:
    slug = _unique_character_slug(session, slugify(name))
    character = models.CharacterProfile(
        family_id=family_id,
        name=name,
        slug=slug,
        role=role,
        short_description=short_description,
        canonical_description=canonical_description,
        visual_style=visual_style,
        personality=personality,
        master_prompt=canonical_description,
        negative_prompt="Do not change the character identity, proportions, colors or face.",
        prompt_fragment=canonical_description,
        negative_prompt_fragment="Do not change the character identity, proportions, colors or face.",
        status="active",
    )
    return add_and_commit(session, character)


def create_character_cell(
    session: Session,
    *,
    character: models.CharacterProfile,
    title: str,
    cell_type: str,
    description: str,
    prompt_notes: str,
    image_filename: str | None = None,
    image_bytes: bytes | None = None,
    is_primary: bool = False,
) -> models.CharacterCell:
    slug = _unique_cell_slug(session, character.id, slugify(title))
    image_path = None
    width = None
    height = None
    mime_type = None
    sha256 = None

    if image_bytes and image_filename:
        stored = _store_character_image(character.slug, slug, image_filename, image_bytes)
        image_path = str(stored["path"])
        width = int(stored["width"])
        height = int(stored["height"])
        mime_type = str(stored["mime_type"])
        sha256 = str(stored["sha256"])

    if is_primary:
        for cell in list_character_cells(session, character.id):
            cell.is_primary = False
        session.commit()

    cell = models.CharacterCell(
        character_profile_id=character.id,
        title=title,
        slug=slug,
        description=description,
        cell_type=cell_type if cell_type in CELL_TYPES else "other",
        image_path=image_path,
        prompt_notes=prompt_notes,
        is_primary=is_primary,
        sort_order=(len(list_character_cells(session, character.id)) + 1) * 10,
        width=width,
        height=height,
        mime_type=mime_type,
        sha256=sha256,
    )
    return add_and_commit(session, cell)


def character_reference_images(session: Session, character_id: int) -> list[dict[str, object]]:
    return [
        {
            "cell_id": cell.id,
            "title": cell.title,
            "path": cell.image_path,
            "cell_type": cell.cell_type,
            "reason": cell.prompt_notes,
            "is_primary": cell.is_primary,
        }
        for cell in list_character_cells(session, character_id)
        if cell.image_path
    ]


def _store_character_image(
    character_slug: str,
    cell_slug: str,
    filename: str,
    data: bytes,
) -> dict[str, object]:
    suffix = Path(filename).suffix.lower() or ".png"
    directory = safe_join(get_settings().assets_dir, "characters", character_slug)
    path = directory / f"{cell_slug}{suffix}"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)

    image = Image.open(BytesIO(data))
    return {
        "path": path,
        "width": image.width,
        "height": image.height,
        "mime_type": Image.MIME.get(image.format or "", "application/octet-stream"),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def _unique_character_slug(session: Session, base_slug: str) -> str:
    slug = base_slug or "character"
    candidate = slug
    counter = 2
    while session.query(models.CharacterProfile).filter_by(slug=candidate).first() is not None:
        candidate = f"{slug}-{counter}"
        counter += 1
    return candidate


def _unique_cell_slug(session: Session, character_id: int, base_slug: str) -> str:
    slug = base_slug or "cell"
    candidate = slug
    counter = 2
    while (
        session.query(models.CharacterCell)
        .filter_by(character_profile_id=character_id, slug=candidate)
        .first()
        is not None
    ):
        candidate = f"{slug}-{counter}"
        counter += 1
    return candidate

