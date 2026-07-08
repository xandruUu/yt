from __future__ import annotations

import json
import urllib.request
from collections.abc import Callable
from typing import Any

from app.providers.base import TrendItem

JSONFetcher = Callable[[str, int], Any]


class HackerNewsProvider:
    name = "hackernews"
    base_url = "https://hacker-news.firebaseio.com/v0"

    def __init__(self, fetcher: JSONFetcher | None = None) -> None:
        self.fetcher = fetcher or _default_json_fetcher

    def fetch_trends(
        self,
        query: str | None,
        market: str,
        language: str,
        category: str,
        limit: int,
    ) -> list[TrendItem]:
        try:
            story_ids = self.fetcher(f"{self.base_url}/topstories.json", 10)[: max(limit * 2, limit)]
        except Exception as exc:  # noqa: BLE001
            return [
                TrendItem(
                    title="Hacker News no disponible",
                    summary=str(exc),
                    source="Hacker News",
                    language=language,
                    market=market,
                    category=category,
                    popularity_signals={"provider_error": True},
                    raw_data={"error": str(exc)},
                )
            ]

        items: list[TrendItem] = []
        for rank, story_id in enumerate(story_ids, start=1):
            if len(items) >= limit:
                break
            try:
                story = self.fetcher(f"{self.base_url}/item/{story_id}.json", 10)
            except Exception:
                continue
            title = story.get("title")
            if not title or (query and query.lower() not in title.lower()):
                continue
            items.append(
                TrendItem(
                    title=title,
                    summary=None,
                    source="Hacker News",
                    source_url=story.get("url") or f"https://news.ycombinator.com/item?id={story_id}",
                    language=language,
                    market=market,
                    category=category,
                    popularity_signals={
                        "hn_score": story.get("score", 0),
                        "comments": story.get("descendants", 0),
                        "rank": rank,
                    },
                    raw_data={"id": story_id, "by": story.get("by"), "time": story.get("time")},
                )
            )
        return items


def _default_json_fetcher(url: str, timeout: int) -> Any:
    with urllib.request.urlopen(url, timeout=timeout) as response:  # noqa: S310
        return json.loads(response.read().decode("utf-8"))

