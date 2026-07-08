from __future__ import annotations

import unittest

from app.providers.base import TrendItem
from app.services.trend_research_service import TrendResearchService


class FakeProvider:
    name = "fake"

    def fetch_trends(self, query, market, language, category, limit):
        return [
            TrendItem(
                title="AI agents automate support",
                source="Fake",
                source_url="https://example.com/a",
                language=language,
                market=market,
                category=category,
                popularity_signals={"points": 10},
            ),
            TrendItem(
                title="AI agents automate support duplicate",
                source="Fake",
                source_url="https://example.com/a",
                language=language,
                market=market,
                category=category,
                popularity_signals={"points": 99},
            ),
            TrendItem(
                title="Low signal",
                source="Fake",
                language=language,
                market=market,
                category=category,
                popularity_signals={"points": 1},
            ),
        ]


class TrendResearchServiceTests(unittest.TestCase):
    def test_research_dedupes_and_sorts(self) -> None:
        service = TrendResearchService(provider_registry={"fake": FakeProvider()})
        result = service.research(["fake"], None, "global", "en", "tech_explained", 10)
        self.assertEqual(result.providers_used, ["fake"])
        self.assertEqual(len(result.items), 2)
        self.assertEqual(result.items[0].title, "AI agents automate support")

    def test_unknown_provider_returns_warning(self) -> None:
        result = TrendResearchService().research(["missing"], None, "global", "en", "tech_explained", 10)
        self.assertEqual(result.items, [])
        self.assertIn("Proveedor desconocido", result.warnings[0])


if __name__ == "__main__":
    unittest.main()

