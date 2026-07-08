from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models


def build_external_license_manifest(
    session: Session,
    *,
    script_id: int | None = None,
    visual_plan_id: int | None = None,
) -> dict[str, object]:
    statement = select(models.ExternalAsset).order_by(models.ExternalAsset.created_at.desc())
    if script_id is not None:
        statement = statement.where(models.ExternalAsset.script_id == script_id)
    if visual_plan_id is not None:
        statement = statement.where(models.ExternalAsset.visual_plan_id == visual_plan_id)
    assets = session.scalars(statement).all()
    return {
        "external_assets": [
            {
                "id": asset.id,
                "provider_name": asset.provider_name,
                "asset_type": asset.asset_type,
                "file_path": asset.file_path,
                "source": asset.source,
                "source_url": asset.source_url,
                "license_type": asset.license_type,
                "license_notes": asset.license_notes,
                "commercial_use_confirmed": asset.commercial_use_confirmed,
                "status": asset.status,
            }
            for asset in assets
        ]
    }


def external_assets_missing_license(session: Session, visual_plan: models.VisualPlan) -> list[models.ExternalAsset]:
    import json

    scenes = json.loads(visual_plan.scenes_json or "[]")
    asset_ids = [
        int(scene["external_asset_id"])
        for scene in scenes
        if isinstance(scene, dict) and scene.get("external_asset_id")
    ]
    if not asset_ids:
        return []
    assets = session.scalars(select(models.ExternalAsset).where(models.ExternalAsset.id.in_(asset_ids))).all()
    return [
        asset
        for asset in assets
        if asset.status != "approved" or not asset.commercial_use_confirmed or not asset.license_type
    ]
