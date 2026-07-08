from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import ExternalAssetStatus, StoryboardSceneStatus
from app.db import models
from app.db.repositories import add_and_commit
from app.services.storyboard_service import list_storyboard_scenes


@dataclass(frozen=True)
class SceneMappingValidation:
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def create_scene_asset_mapping(
    session: Session,
    *,
    scene_id: int,
    external_asset_id: int,
    usage_type: str = "foreground_clip",
    start_time: float = 0.0,
    duration: float | None = None,
    fit_mode: str = "cover",
    crop_anchor: str = "center",
    apply_ken_burns: bool = False,
    notes: str | None = None,
) -> models.SceneAssetMapping:
    scene = _get_scene(session, scene_id)
    asset = _get_asset(session, external_asset_id)
    _validate_asset_for_scene(scene, asset)
    mapping = models.SceneAssetMapping(
        scene_id=scene.id,
        external_asset_id=asset.id,
        usage_type=usage_type,
        start_time=float(start_time),
        duration=float(duration if duration is not None else scene.duration_seconds),
        fit_mode=fit_mode,
        crop_anchor=crop_anchor,
        apply_ken_burns=apply_ken_burns,
        notes=notes,
    )
    scene.external_asset_id = asset.id
    scene.status = StoryboardSceneStatus.MAPPED.value
    session.add(mapping)
    session.commit()
    session.refresh(mapping)
    return mapping


def list_scene_asset_mappings(session: Session, storyboard_id: int) -> list[models.SceneAssetMapping]:
    scene_ids = [scene.id for scene in list_storyboard_scenes(session, storyboard_id)]
    if not scene_ids:
        return []
    return list(
        session.scalars(
            select(models.SceneAssetMapping)
            .where(models.SceneAssetMapping.scene_id.in_(scene_ids))
            .order_by(models.SceneAssetMapping.scene_id, models.SceneAssetMapping.start_time)
        ).all()
    )


def validate_storyboard_asset_mappings(
    session: Session,
    storyboard_id: int,
    *,
    allow_fallback: bool = True,
) -> SceneMappingValidation:
    scenes = list_storyboard_scenes(session, storyboard_id)
    mappings = list_scene_asset_mappings(session, storyboard_id)
    mapped_by_scene = {mapping.scene_id: mapping for mapping in mappings}
    errors: list[str] = []
    warnings: list[str] = []
    for scene in scenes:
        mapping = mapped_by_scene.get(scene.id)
        if mapping is None:
            message = f"Scene {scene.scene_number:02} has no mapped external asset."
            if allow_fallback:
                warnings.append(message + " Fallback visual can be used.")
            else:
                errors.append(message)
            continue
        asset = session.get(models.ExternalAsset, mapping.external_asset_id)
        if asset is None:
            errors.append(f"Scene {scene.scene_number:02} maps to missing ExternalAsset #{mapping.external_asset_id}.")
            continue
        if not Path(asset.file_path).exists():
            errors.append(f"Scene {scene.scene_number:02} asset path does not exist: {asset.file_path}")
        if asset.status != ExternalAssetStatus.APPROVED.value:
            errors.append(f"Scene {scene.scene_number:02} asset #{asset.id} is not approved for commercial use.")
        if not asset.commercial_use_confirmed or not asset.license_type:
            errors.append(f"Scene {scene.scene_number:02} asset #{asset.id} is missing license confirmation.")
    return SceneMappingValidation(ok=not errors, errors=errors, warnings=warnings)


def storyboard_render_manifest(
    session: Session,
    storyboard_id: int,
    *,
    allow_fallback: bool = True,
) -> dict[str, object]:
    storyboard = session.get(models.VisualStoryboard, storyboard_id)
    if storyboard is None:
        raise ValueError(f"VisualStoryboard not found: {storyboard_id}")
    scenes = list_storyboard_scenes(session, storyboard_id)
    mappings = list_scene_asset_mappings(session, storyboard_id)
    mapped_by_scene = {mapping.scene_id: mapping for mapping in mappings}
    validation = validate_storyboard_asset_mappings(session, storyboard_id, allow_fallback=allow_fallback)
    manifest_scenes = []
    for scene in scenes:
        mapping = mapped_by_scene.get(scene.id)
        asset = session.get(models.ExternalAsset, mapping.external_asset_id) if mapping else None
        manifest_scenes.append(
            {
                "scene_number": scene.scene_number,
                "duration_seconds": scene.duration_seconds,
                "narration_line": scene.narration_line,
                "source": "external_asset" if asset else "fallback_prompt",
                "asset_path": asset.file_path if asset else None,
                "fit_mode": mapping.fit_mode if mapping else "cover",
                "crop_anchor": mapping.crop_anchor if mapping else "center",
                "apply_ken_burns": mapping.apply_ken_burns if mapping else False,
                "fallback_prompt": scene.higgsfield_prompt if asset is None else None,
            }
        )
    return {
        "storyboard_id": storyboard.id,
        "script_id": storyboard.script_id,
        "allow_fallback": allow_fallback,
        "ok": validation.ok,
        "errors": validation.errors,
        "warnings": validation.warnings,
        "scenes": manifest_scenes,
    }


def storyboard_render_manifest_json(
    session: Session,
    storyboard_id: int,
    *,
    allow_fallback: bool = True,
) -> str:
    return json.dumps(
        storyboard_render_manifest(session, storyboard_id, allow_fallback=allow_fallback),
        indent=2,
        ensure_ascii=False,
    )


def mark_scene_needs_asset(session: Session, scene_id: int) -> models.StoryboardScene:
    scene = _get_scene(session, scene_id)
    scene.status = StoryboardSceneStatus.NEEDS_ASSET.value
    return add_and_commit(session, scene)


def _validate_asset_for_scene(scene: models.StoryboardScene, asset: models.ExternalAsset) -> None:
    if asset.asset_type not in {"video", "image"}:
        raise ValueError("Solo se pueden mapear assets de tipo video o image a escenas visuales.")
    if asset.status != ExternalAssetStatus.APPROVED.value:
        raise ValueError("El asset externo debe estar aprobado antes de mapearlo a una escena.")
    if not asset.commercial_use_confirmed or not asset.license_type:
        raise ValueError("El asset externo necesita licencia y uso comercial confirmado.")
    if scene.duration_seconds <= 0:
        raise ValueError("La escena necesita duracion positiva.")


def _get_scene(session: Session, scene_id: int) -> models.StoryboardScene:
    scene = session.get(models.StoryboardScene, scene_id)
    if scene is None:
        raise ValueError(f"StoryboardScene not found: {scene_id}")
    return scene


def _get_asset(session: Session, external_asset_id: int) -> models.ExternalAsset:
    asset = session.get(models.ExternalAsset, external_asset_id)
    if asset is None:
        raise ValueError(f"ExternalAsset not found: {external_asset_id}")
    return asset
