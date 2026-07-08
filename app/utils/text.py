from __future__ import annotations

import re


def split_script_text(script_text: str) -> list[str]:
    lines: list[str] = []
    for raw_line in script_text.splitlines():
        line = raw_line.strip()
        line = re.sub(r"^\s*[-*0-9.)]+\s*", "", line)
        if line:
            lines.append(line)
    return lines


def normalize_hashtags(raw: str | list[str], max_items: int = 5) -> list[str]:
    candidates = re.split(r"[\s,]+", raw) if isinstance(raw, str) else raw
    tags: list[str] = []
    for candidate in candidates:
        tag = candidate.strip()
        if not tag:
            continue
        if not tag.startswith("#"):
            tag = f"#{tag}"
        tag = re.sub(r"[^#A-Za-z0-9_]", "", tag)
        if tag != "#" and tag.lower() not in {item.lower() for item in tags}:
            tags.append(tag)
        if len(tags) >= max_items:
            break
    return tags


def compact_text(value: str, max_length: int = 280) -> str:
    compact = re.sub(r"\s+", " ", value).strip()
    if len(compact) <= max_length:
        return compact
    return compact[: max_length - 1].rstrip() + "..."
