from __future__ import annotations

import unittest

from app.providers.hackernews_provider import HackerNewsProvider
from app.providers.manual_input_provider import ManualInputProvider
from app.providers.rss_provider import RSSFeedProvider
from app.providers.youtube_search_provider import YouTubeSearchProvider


class TrendProviderTests(unittest.TestCase):
    def test_manual_input_provider_converts_lines_to_trends(self) -> None:
        provider = ManualInputProvider(
            "AI agents are replacing tasks\n"
            "QR codes still work when damaged - error correction explained"
        )
        items = provider.fetch_trends(None, "global", "en", "tech_explained", 10)
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0].source, "Manual")
        self.assertEqual(items[1].summary, "error correction explained")

    def test_rss_provider_parses_valid_feed(self) -> None:
        feed = b"""
        <rss><channel>
          <item>
            <title>AI chip demand keeps growing</title>
            <link>https://example.com/ai-chip</link>
            <description>Semiconductor trend</description>
          </item>
        </channel></rss>
        """

        provider = RSSFeedProvider(
            sources_path="missing.json",
            fetcher=lambda _url, _timeout: feed,
        )
        provider._load_sources = lambda: [  # type: ignore[method-assign]
            {
                "name": "Example RSS",
                "url": "https://example.com/feed",
                "category": "tech_explained",
                "language": "en",
            }
        ]
        items = provider.fetch_trends(None, "global", "en", "tech_explained", 5)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].title, "AI chip demand keeps growing")

    def test_rss_provider_handles_invalid_feed(self) -> None:
        provider = RSSFeedProvider(
            sources_path="missing.json",
            fetcher=lambda _url, _timeout: b"<not-valid",
        )
        provider._load_sources = lambda: [  # type: ignore[method-assign]
            {"name": "Broken", "url": "https://example.com/feed", "category": "tech_explained"}
        ]
        items = provider.fetch_trends(None, "global", "en", "tech_explained", 5)
        self.assertEqual(items[0].source, "RSS")
        self.assertTrue(items[0].popularity_signals["provider_error"])

    def test_hackernews_provider_normalizes_mocked_stories(self) -> None:
        def fetcher(url: str, _timeout: int):
            if url.endswith("topstories.json"):
                return [123]
            return {
                "id": 123,
                "title": "SQLite on the edge",
                "url": "https://example.com/sqlite-edge",
                "score": 380,
                "descendants": 120,
                "by": "tester",
                "time": 1,
            }

        provider = HackerNewsProvider(fetcher=fetcher)
        items = provider.fetch_trends(None, "global", "en", "tech_explained", 5)
        self.assertEqual(items[0].source, "Hacker News")
        self.assertEqual(items[0].popularity_signals["hn_score"], 380)

    def test_youtube_provider_degrades_without_api_key(self) -> None:
        provider = YouTubeSearchProvider(api_key="")
        items = provider.fetch_trends("ai", "global", "en", "ai_tools", 5)
        self.assertFalse(provider.is_available())
        self.assertTrue(items[0].popularity_signals["missing_api_key"])


if __name__ == "__main__":
    unittest.main()

