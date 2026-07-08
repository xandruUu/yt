from __future__ import annotations

from app.providers.base import TrendItem


class GoogleTrendsProvider:
    name = "google_trends"

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
                title="Google Trends no configurado",
                summary="pytrends es opcional y no oficial. Usa modo manual, RSS o Hacker News.",
                source="Google Trends",
                language=language,
                market=market,
                category=category,
                popularity_signals={"provider_stub": True},
                raw_data={"query": query, "limit": limit},
            )
        ]

