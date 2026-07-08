from __future__ import annotations

import csv
from io import StringIO

from app.providers.base import TrendItem


class ManualInputProvider:
    name = "manual"

    def __init__(self, raw_input: str = "") -> None:
        self.raw_input = raw_input

    def fetch_trends(
        self,
        query: str | None,
        market: str,
        language: str,
        category: str,
        limit: int,
    ) -> list[TrendItem]:
        rows = _parse_csv_like(self.raw_input)
        if rows:
            return [
                TrendItem(
                    title=row["title"],
                    summary=row.get("summary"),
                    source="Manual",
                    source_url=row.get("source_url"),
                    language=language,
                    market=market,
                    category=category,
                    popularity_signals={"manual_signal": True},
                    raw_data=row,
                )
                for row in rows[:limit]
                if row.get("title")
            ]

        items: list[TrendItem] = []
        for line in self.raw_input.splitlines():
            cleaned = line.strip(" -\t")
            if not cleaned:
                continue
            title, summary = _split_title_summary(cleaned)
            if query and query.lower() not in cleaned.lower():
                continue
            items.append(
                TrendItem(
                    title=title,
                    summary=summary,
                    source="Manual",
                    source_url=title if title.startswith(("http://", "https://")) else None,
                    language=language,
                    market=market,
                    category=category,
                    popularity_signals={"manual_signal": True},
                    raw_data={"line": cleaned},
                )
            )
            if len(items) >= limit:
                break
        return items


def _parse_csv_like(raw_input: str) -> list[dict[str, str]]:
    sample = raw_input.strip()
    if "," not in sample or "\n" not in sample:
        return []
    reader = csv.DictReader(StringIO(sample))
    if not reader.fieldnames or "title" not in [field.lower() for field in reader.fieldnames]:
        return []
    normalized_rows = []
    for row in reader:
        normalized_rows.append({(key or "").lower().strip(): (value or "").strip() for key, value in row.items()})
    return normalized_rows


def _split_title_summary(line: str) -> tuple[str, str | None]:
    if " - " in line:
        title, summary = line.split(" - ", 1)
        return title.strip(), summary.strip()
    if ": " in line and not line.startswith(("http://", "https://")):
        title, summary = line.split(": ", 1)
        return title.strip(), summary.strip()
    return line, None

