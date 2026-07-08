from __future__ import annotations

import json
import urllib.request
import xml.etree.ElementTree as ET
from collections.abc import Callable
from pathlib import Path

from app.providers.base import TrendItem

Fetcher = Callable[[str, int], bytes]


class RSSFeedProvider:
    name = "rss"

    def __init__(
        self,
        sources_path: str | Path = "config/rss_sources.json",
        fetcher: Fetcher | None = None,
    ) -> None:
        self.sources_path = Path(sources_path)
        self.fetcher = fetcher or _default_fetcher

    def fetch_trends(
        self,
        query: str | None,
        market: str,
        language: str,
        category: str,
        limit: int,
    ) -> list[TrendItem]:
        items: list[TrendItem] = []
        for source in self._load_sources():
            if source.get("category") and source["category"] not in {category, "technology", "tech_explained"}:
                continue
            try:
                feed_bytes = self.fetcher(source["url"], 10)
                items.extend(self._parse_feed(feed_bytes, source, market, language, category, limit - len(items)))
            except Exception as exc:  # noqa: BLE001 - providers must not break the app.
                items.append(
                    TrendItem(
                        title=f"RSS no disponible: {source.get('name', source.get('url', 'feed'))}",
                        summary=str(exc),
                        source="RSS",
                        source_url=source.get("url"),
                        language=language,
                        market=market,
                        category=category,
                        popularity_signals={"provider_error": True},
                        raw_data={"error": str(exc), "source": source},
                    )
                )
            if len(items) >= limit:
                break
        return [item for item in items if not query or query.lower() in item.title.lower()][:limit]

    def _load_sources(self) -> list[dict[str, str]]:
        if not self.sources_path.exists():
            return []
        return json.loads(self.sources_path.read_text(encoding="utf-8"))

    def _parse_feed(
        self,
        feed_bytes: bytes,
        source: dict[str, str],
        market: str,
        language: str,
        category: str,
        limit: int,
    ) -> list[TrendItem]:
        root = ET.fromstring(feed_bytes)
        entries = root.findall(".//item") or root.findall("{http://www.w3.org/2005/Atom}entry")
        results: list[TrendItem] = []
        for entry in entries[:limit]:
            title = _text(entry, "title")
            if not title:
                continue
            link = _text(entry, "link") or _attr(entry, "{http://www.w3.org/2005/Atom}link", "href")
            summary = _text(entry, "description") or _text(entry, "summary")
            results.append(
                TrendItem(
                    title=title,
                    summary=summary,
                    source=source.get("name", "RSS"),
                    source_url=link,
                    language=source.get("language") or language,
                    market=market,
                    category=source.get("category") or category,
                    popularity_signals={"rss_item": True},
                    raw_data={"source": source},
                )
            )
        return results


def _default_fetcher(url: str, timeout: int) -> bytes:
    with urllib.request.urlopen(url, timeout=timeout) as response:  # noqa: S310
        return response.read()


def _text(entry: ET.Element, tag: str) -> str | None:
    node = entry.find(tag)
    if node is None:
        node = entry.find(f"{{http://www.w3.org/2005/Atom}}{tag}")
    if node is None or node.text is None:
        return None
    return " ".join(node.text.split())


def _attr(entry: ET.Element, tag: str, attr: str) -> str | None:
    node = entry.find(tag)
    if node is None:
        return None
    return node.attrib.get(attr)
