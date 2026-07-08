from __future__ import annotations

import json
from typing import Any

from app.services.prompt_service import render_prompt
from app.utils.language import needs_native_review
from app.utils.text import normalize_hashtags, split_script_text


def build_script_prompt(
    *,
    topic_title: str,
    selected_hook: str,
    language: str,
    market: str,
    duration_seconds: int,
) -> str:
    return render_prompt(
        "script_prompt.md",
        topic_title=topic_title,
        selected_hook=selected_hook,
        language=language,
        market=market,
        duration_seconds=duration_seconds,
    )


def parse_script_response(response_text: str, language: str = "en") -> dict[str, Any]:
    payload = _try_json(response_text)
    if payload:
        lines = payload.get("lines", [])
        normalized_lines = []
        for item in lines:
            if isinstance(item, str):
                normalized_lines.append(_line_payload(item))
            elif isinstance(item, dict) and item.get("text"):
                normalized_lines.append(
                    {
                        "text": str(item["text"]).strip(),
                        "visual_suggestion": item.get("visual_suggestion"),
                        "duration_seconds": float(
                            item.get("estimated_duration_seconds")
                            or item.get("duration_seconds")
                            or 2.5
                        ),
                        "needs_source": bool(item.get("needs_source", False)),
                        "source_hint": item.get("source_hint") or item.get("source_url"),
                    }
                )
        return {
            "title_suggestion": payload.get("title_suggestion"),
            "description_suggestion": payload.get("description_suggestion"),
            "hashtags": normalize_hashtags(payload.get("hashtags", [])),
            "lines": normalized_lines,
            "script_text": "\n".join(item["text"] for item in normalized_lines),
            "needs_native_review": needs_native_review(language),
        }

    lines = [_line_payload(line) for line in split_script_text(response_text)]
    return {
        "title_suggestion": None,
        "description_suggestion": None,
        "hashtags": [],
        "lines": lines,
        "script_text": "\n".join(line["text"] for line in lines),
        "needs_native_review": needs_native_review(language),
    }


def _line_payload(text: str) -> dict[str, Any]:
    return {
        "text": text.strip(),
        "visual_suggestion": None,
        "duration_seconds": 2.5,
        "needs_source": False,
        "source_hint": None,
    }


def _try_json(text: str) -> dict[str, Any] | None:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].strip()
    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None

