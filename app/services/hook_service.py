from __future__ import annotations

import csv
from io import StringIO
from typing import Any

from app.services.prompt_service import render_prompt


def build_hooks_prompt(
    *,
    topic_title: str,
    topic_summary: str,
    language: str,
    market: str,
    number_of_hooks: int = 8,
) -> str:
    return render_prompt(
        "hooks_prompt.md",
        number_of_hooks=number_of_hooks,
        topic_title=topic_title,
        topic_summary=topic_summary,
        language=language,
        market=market,
    )


def parse_hooks_response(response_text: str, default_language: str = "en") -> list[dict[str, Any]]:
    rows = _parse_markdown_table(response_text)
    if rows:
        parsed = []
        for row in rows:
            hook = row.get("hook") or row.get("text") or row.get("Hook")
            if not hook:
                continue
            parsed.append(
                {
                    "language": default_language,
                    "text": hook.strip(),
                    "hook_type": (row.get("hook_type") or row.get("type") or "mystery").strip(),
                    "notes": row.get("why_it_works") or row.get("suggested_visual"),
                    "risk_score": _safe_float(row.get("risk_level"), default=0.0),
                }
            )
        return parsed

    hooks: list[dict[str, Any]] = []
    for line in response_text.splitlines():
        cleaned = line.strip().strip("-* ")
        if not cleaned or cleaned.lower().startswith(("hook", "|")):
            continue
        if len(cleaned.split()) <= 20:
            hooks.append(
                {
                    "language": default_language,
                    "text": cleaned,
                    "hook_type": "mystery",
                    "notes": None,
                    "risk_score": 0.0,
                }
            )
    return hooks


def _parse_markdown_table(text: str) -> list[dict[str, str]]:
    table_lines = [line.strip() for line in text.splitlines() if line.strip().startswith("|")]
    if len(table_lines) < 2:
        return []
    reader = csv.reader(StringIO("\n".join(line.strip("|") for line in table_lines)), delimiter="|")
    rows = [[cell.strip() for cell in row] for row in reader]
    headers = [header.lower().replace(" ", "_") for header in rows[0]]
    data_rows = rows[2:] if set(rows[1][0]) <= {"-", ":"} else rows[1:]
    return [dict(zip(headers, row, strict=False)) for row in data_rows if any(row)]


def _safe_float(value: object, default: float) -> float:
    try:
        return float(value) if value is not None and value != "" else default
    except (TypeError, ValueError):
        return default

