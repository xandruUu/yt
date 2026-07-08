from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image
from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.core.enums import ExternalAssetStatus
from app.db import models
from app.db.repositories import add_and_commit, create_external_asset
from app.utils.files import copy_file
from app.utils.safe_paths import ensure_allowed_extension, safe_join
from app.utils.slugs import slugify


def import_external_asset(
    session: Session,
    *,
    file_path: str | Path,
    asset_type: str,
    provider_name: str | None = None,
    wizard_session_id: int | None = None,
    script_id: int | None = None,
    visual_plan_id: int | None = None,
    scene_order: int | None = None,
    license_info: dict[str, Any] | None = None,
    overwrite: bool = False,
) -> models.ExternalAsset:
    source = Path(file_path).expanduser().resolve()
    if not source.exists():
        raise FileNotFoundError(source)
    _validate_extension(source, asset_type)
    _validate_size(source)
    license_info = license_info or {}
    provider_folder = slugify(provider_name or "manual")
    project_folder = f"script_{script_id}" if script_id else "unassigned"
    destination_dir = safe_join(get_settings().assets_dir, "external", provider_folder, project_folder)
    destination_name = _destination_name(source, scene_order)
    copied = copy_file(source, destination_dir / destination_name, overwrite=overwrite)
    metadata = _media_metadata(copied, asset_type)
    commercial = bool(license_info.get("commercial_use_confirmed", False))
    status = (
        ExternalAssetStatus.APPROVED.value
        if commercial and license_info.get("license_type")
        else ExternalAssetStatus.NEEDS_LICENSE_REVIEW.value
    )
    return create_external_asset(
        session,
        wizard_session_id=wizard_session_id,
        script_id=script_id,
        visual_plan_id=visual_plan_id,
        scene_order=scene_order,
        provider_name=provider_name,
        asset_type=asset_type,
        file_path=str(copied),
        source=license_info.get("source"),
        source_url=license_info.get("source_url"),
        license_type=license_info.get("license_type"),
        license_notes=license_info.get("license_notes"),
        commercial_use_confirmed=commercial,
        duration_seconds=metadata.get("duration_seconds"),
        width=metadata.get("width"),
        height=metadata.get("height"),
        fps=metadata.get("fps"),
        status=status,
    )


def approve_external_asset(session: Session, external_asset_id: int) -> models.ExternalAsset:
    asset = _get_external_asset(session, external_asset_id)
    if not asset.commercial_use_confirmed or not asset.license_type:
        raise ValueError("No se puede aprobar un asset externo sin licencia y uso comercial confirmado.")
    asset.status = ExternalAssetStatus.APPROVED.value
    return add_and_commit(session, asset)


def reject_external_asset(session: Session, external_asset_id: int, reason: str | None = None) -> models.ExternalAsset:
    asset = _get_external_asset(session, external_asset_id)
    asset.status = ExternalAssetStatus.REJECTED.value
    asset.license_notes = reason or asset.license_notes
    return add_and_commit(session, asset)


def _get_external_asset(session: Session, external_asset_id: int) -> models.ExternalAsset:
    asset = session.get(models.ExternalAsset, external_asset_id)
    if asset is None:
        raise ValueError(f"ExternalAsset not found: {external_asset_id}")
    return asset


def _validate_extension(path: Path, asset_type: str) -> None:
    settings = get_settings()
    if asset_type == "video":
        ensure_allowed_extension(path, set(settings.allowed_video_extensions))
    elif asset_type in {"audio", "sfx"}:
        ensure_allowed_extension(path, set(settings.allowed_audio_extensions))
    elif asset_type == "image":
        ensure_allowed_extension(path, set(settings.allowed_image_extensions))
    else:
        raise ValueError(f"Unsupported external asset type: {asset_type}")


def _validate_size(path: Path) -> None:
    max_bytes = get_settings().max_imported_asset_mb * 1024 * 1024
    if path.stat().st_size > max_bytes:
        raise ValueError(f"Imported asset exceeds MAX_IMPORTED_ASSET_MB={get_settings().max_imported_asset_mb}.")


def _destination_name(path: Path, scene_order: int | None) -> str:
    prefix = f"scene_{scene_order:02}_" if scene_order else ""
    return f"{prefix}{slugify(path.stem)}{path.suffix.lower()}"


def _media_metadata(path: Path, asset_type: str) -> dict[str, Any]:
    if asset_type == "image":
        try:
            with Image.open(path) as image:
                return {"width": image.width, "height": image.height}
        except Exception:  # noqa: BLE001 - metadata is optional.
            return {}
    return {}
