from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import ExternalAssetStatus
from app.db import models
from app.db.repositories import add_and_commit


def list_external_assets(
    session: Session,
    *,
    script_id: int | None = None,
    visual_plan_id: int | None = None,
    provider_name: str | None = None,
    scene_order: int | None = None,
    status: str | None = None,
) -> list[models.ExternalAsset]:
    statement = select(models.ExternalAsset).order_by(models.ExternalAsset.created_at.desc())
    if script_id is not None:
        statement = statement.where(models.ExternalAsset.script_id == script_id)
    if visual_plan_id is not None:
        statement = statement.where(models.ExternalAsset.visual_plan_id == visual_plan_id)
    if provider_name is not None:
        statement = statement.where(models.ExternalAsset.provider_name == provider_name)
    if scene_order is not None:
        statement = statement.where(models.ExternalAsset.scene_order == scene_order)
    if status is not None:
        statement = statement.where(models.ExternalAsset.status == status)
    return list(session.scalars(statement).all())


def set_external_asset_license(
    session: Session,
    *,
    external_asset_id: int,
    license_type: str,
    commercial_use_confirmed: bool,
    license_notes: str | None = None,
) -> models.ExternalAsset:
    asset = _get_asset(session, external_asset_id)
    asset.license_type = license_type
    asset.commercial_use_confirmed = commercial_use_confirmed
    asset.license_notes = license_notes
    asset.status = (
        ExternalAssetStatus.APPROVED.value
        if commercial_use_confirmed and license_type
        else ExternalAssetStatus.NEEDS_LICENSE_REVIEW.value
    )
    return add_and_commit(session, asset)


def associate_asset_to_visual_scene(
    session: Session,
    *,
    visual_plan_id: int,
    external_asset_id: int,
    scene_order: int,
) -> models.VisualPlan:
    plan = session.get(models.VisualPlan, visual_plan_id)
    asset = _get_asset(session, external_asset_id)
    if plan is None:
        raise ValueError(f"VisualPlan not found: {visual_plan_id}")
    if asset.status != ExternalAssetStatus.APPROVED.value:
        raise ValueError("Solo se pueden asociar assets externos aprobados.")
    scenes = json.loads(plan.scenes_json or "[]")
    for scene in scenes:
        if int(scene.get("order") or 0) == scene_order:
            scene["external_asset_id"] = asset.id
            scene["provider_name"] = asset.provider_name
            scene["visual_type"] = "external_video" if asset.asset_type == "video" else "external_image"
            scene["fallback_visual_type"] = scene.get("fallback_visual_type") or "text_focus"
            break
    else:
        raise ValueError(f"Scene order not found: {scene_order}")
    plan.scenes_json = json.dumps(scenes, ensure_ascii=False)
    return add_and_commit(session, plan)


def _get_asset(session: Session, external_asset_id: int) -> models.ExternalAsset:
    asset = session.get(models.ExternalAsset, external_asset_id)
    if asset is None:
        raise ValueError(f"ExternalAsset not found: {external_asset_id}")
    return asset
