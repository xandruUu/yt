from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any


def asset_license_ready(asset: Mapping[str, Any]) -> bool:
    return bool(
        asset.get("license_type")
        and asset.get("source")
        and asset.get("safe_for_commercial_use")
        and (
            not asset.get("attribution_required")
            or bool(asset.get("attribution_text"))
        )
    )


def music_license_ready(track: Mapping[str, Any]) -> bool:
    return bool(
        track.get("license_type")
        and track.get("source")
        and track.get("safe_for_monetization")
        and (
            not track.get("attribution_required")
            or bool(track.get("attribution_text"))
        )
    )


def build_license_manifest(
    music: Iterable[Mapping[str, Any]] | None = None,
    assets: Iterable[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    music_items = music or []
    asset_items = assets or []
    return {
        "music": [
            {
                "title": item.get("title"),
                "source": item.get("source"),
                "license": item.get("license_type"),
                "attribution_required": bool(item.get("attribution_required")),
                "attribution_text": item.get("attribution_text"),
            }
            for item in music_items
        ],
        "assets": [
            {
                "name": item.get("name"),
                "source": item.get("source"),
                "license": item.get("license_type"),
                "attribution_required": bool(item.get("attribution_required")),
                "attribution_text": item.get("attribution_text"),
            }
            for item in asset_items
        ],
    }

