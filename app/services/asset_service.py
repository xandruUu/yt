from __future__ import annotations

from pathlib import Path
from typing import Any

from app.core.constants import (
    SAFE_AUDIO_EXTENSIONS,
    SAFE_FONT_EXTENSIONS,
    SAFE_IMAGE_EXTENSIONS,
    SAFE_VIDEO_EXTENSIONS,
)
from app.core.enums import AssetType
from app.utils.licenses import asset_license_ready
from app.utils.safe_paths import ensure_allowed_extension

ASSET_EXTENSIONS_BY_TYPE = {
    AssetType.BACKGROUND.value: SAFE_IMAGE_EXTENSIONS | SAFE_VIDEO_EXTENSIONS,
    AssetType.IMAGE.value: SAFE_IMAGE_EXTENSIONS,
    AssetType.VIDEO_CLIP.value: SAFE_VIDEO_EXTENSIONS,
    AssetType.ICON.value: SAFE_IMAGE_EXTENSIONS,
    AssetType.SFX.value: SAFE_AUDIO_EXTENSIONS,
    AssetType.FONT.value: SAFE_FONT_EXTENSIONS,
    AssetType.OTHER.value: SAFE_IMAGE_EXTENSIONS | SAFE_VIDEO_EXTENSIONS | SAFE_AUDIO_EXTENSIONS,
}


def build_asset_payload(
    *,
    name: str,
    asset_type: str,
    file_path: str,
    source: str,
    source_url: str | None,
    license_type: str,
    attribution_required: bool,
    attribution_text: str | None,
    safe_for_commercial_use: bool,
    notes: str | None = None,
) -> dict[str, Any]:
    allowed = ASSET_EXTENSIONS_BY_TYPE.get(asset_type, ASSET_EXTENSIONS_BY_TYPE[AssetType.OTHER.value])
    ensure_allowed_extension(Path(file_path), allowed)
    payload = {
        "name": name.strip(),
        "asset_type": asset_type,
        "file_path": file_path,
        "source": source.strip(),
        "source_url": source_url or None,
        "license_type": license_type.strip(),
        "attribution_required": bool(attribution_required),
        "attribution_text": attribution_text or None,
        "safe_for_commercial_use": bool(safe_for_commercial_use),
        "notes": notes,
    }
    if not asset_license_ready(payload):
        raise ValueError("Asset license data is incomplete or not marked safe for commercial use.")
    return payload

