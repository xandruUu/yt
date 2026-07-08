from __future__ import annotations

import hashlib
from dataclasses import dataclass

from app.providers.base import TrendItem, TrendProvider, normalize_title
from app.providers.google_trends_provider import GoogleTrendsProvider
from app.providers.hackernews_provider import HackerNewsProvider
from app.providers.manual_input_provider import ManualInputProvider
from app.providers.reddit_provider import RedditProvider
from app.providers.rss_provider import RSSFeedProvider
from app.providers.youtube_search_provider import YouTubeSearchProvider


@dataclass(frozen=True)
class TrendResearchResult:
    items: list[TrendItem]
    warnings: list[str]
    providers_used: list[str]


class TrendResearchService:
    def __init__(self, provider_registry: dict[str, TrendProvider] | None = None) -> None:
        self.provider_registry = provider_registry or {}

    def research(
        self,
        providers: list[str],
        query: str | None,
        market: str,
        language: str,
        category: str,
        limit: int,
        manual_input: str = "",
    ) -> TrendResearchResult:
        selected_providers = providers or ["manual"]
        raw_items: list[TrendItem] = []
        warnings: list[str] = []
        used: list[str] = []

        for provider_name in selected_providers:
            provider = self._provider(provider_name, manual_input)
            if provider is None:
                warnings.append(f"Proveedor desconocido: {provider_name}")
                continue
            try:
                items = provider.fetch_trends(query, market, language, category, limit)
                raw_items.extend(items)
                used.append(provider.name)
            except Exception as exc:  # noqa: BLE001 - research must degrade gracefully.
                warnings.append(f"{provider_name}: {exc}")

        items = _dedupe_items(raw_items)
        items.sort(key=_trend_sort_score, reverse=True)
        return TrendResearchResult(items=items[:limit], warnings=warnings, providers_used=used)

    def _provider(self, provider_name: str, manual_input: str) -> TrendProvider | None:
        if provider_name in self.provider_registry:
            return self.provider_registry[provider_name]
        if provider_name == "manual":
            return ManualInputProvider(manual_input)
        if provider_name == "rss":
            return RSSFeedProvider()
        if provider_name == "hackernews":
            return HackerNewsProvider()
        if provider_name == "youtube":
            return YouTubeSearchProvider()
        if provider_name == "google_trends":
            return GoogleTrendsProvider()
        if provider_name == "reddit":
            return RedditProvider()
        return None


def _dedupe_items(items: list[TrendItem]) -> list[TrendItem]:
    seen: set[str] = set()
    deduped: list[TrendItem] = []
    for item in items:
        key = _dedupe_key(item)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _dedupe_key(item: TrendItem) -> str:
    if item.source_url:
        return f"url:{item.source_url.strip().lower()}"
    digest = hashlib.sha1(normalize_title(item.title).encode("utf-8")).hexdigest()
    return f"title:{digest}"


def _trend_sort_score(item: TrendItem) -> float:
    signals = item.popularity_signals
    if signals.get("provider_error"):
        return -1
    return float(
        signals.get("hn_score")
        or signals.get("points")
        or signals.get("views")
        or signals.get("comments")
        or (1 if signals else 0)
    )

