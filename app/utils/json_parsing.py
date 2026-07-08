from __future__ import annotations

import json
import re
from typing import Any


def extract_json_array(text: str) -> list[dict[str, Any]]:
    cleaned = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", cleaned, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        cleaned = fenced.group(1)
    elif "[" in cleaned and "]" in cleaned:
        cleaned = cleaned[cleaned.index("[") : cleaned.rindex("]") + 1]
    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError("No se pudo extraer un array JSON válido.") from exc
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise ValueError("La respuesta debe ser un array JSON de objetos.")
    return value


def extract_json_object(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        cleaned = fenced.group(1)
    elif "{" in cleaned and "}" in cleaned:
        cleaned = cleaned[cleaned.index("{") : cleaned.rindex("}") + 1]
    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError("No se pudo extraer un objeto JSON vÃ¡lido.") from exc
    if not isinstance(value, dict):
        raise ValueError("La respuesta debe ser un objeto JSON.")
    return value


def safe_int_score(value: Any, default: int = 5) -> int:
    try:
        numeric = int(round(float(value)))
    except (TypeError, ValueError):
        numeric = default
    return max(0, min(10, numeric))
