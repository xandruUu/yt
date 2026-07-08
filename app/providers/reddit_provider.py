from __future__ import annotations

import os

from app.providers.base import TrendItem


class RedditProvider:
    name = "reddit"

    def is_available(self) -> bool:
        return bool(os.getenv("REDDIT_CLIENT_ID") and os.getenv("REDDIT_CLIENT_SECRET"))

    def fetch_trends(
        self,
        query: str | None,
        market: str,
        language: str,
        category: str,
        limit: int,
    ) -> list[TrendItem]:
        return [
            TrendItem(
                title="Reddit API no configurada",
                summary="Configura la API oficial de Reddit para activar este proveedor. No se usará scraping HTML.",
                source="Reddit API",
                language=language,
                market=market,
                category=category,
                popularity_signals={"provider_stub": True, "available": self.is_available()},
                raw_data={"query": query, "limit": limit},
            )
        ]
