from __future__ import annotations

from app.external_tools.picsart.video_provider import PicsartAPIProvider


class PicsartAssetProvider(PicsartAPIProvider):
    name = "picsart_asset_api"
