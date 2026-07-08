from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ClaimWarning:
    script_line_id: int | None
    text: str
    claim_type: str
    risk_level: str
    needs_source: bool
    suggestion: str


MONEY_RE = re.compile(r"(\$|€|£|\b\d+(?:[.,]\d+)?\s?(millones|millions|billion|billones|k|m)\b)", re.IGNORECASE)
NUMBER_RE = re.compile(r"\b\d{2,}\b")
YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")
ABSOLUTE_WORDS = {"nunca", "siempre", "primero", "mayor", "mas grande", "el mejor", "never", "always", "first", "biggest"}
HIGH_RISK_WORDS = {
    "salud": "health",
    "medicina": "health",
    "medical": "health",
    "inversion": "finance",
    "trading": "finance",
    "garantizado": "finance",
    "legal": "legal",
    "politica": "politics",
    "politics": "politics",
    "seguridad": "security",
    "hack": "security",
}


def analyze_claims(lines: list[dict[str, object]]) -> list[ClaimWarning]:
    warnings: list[ClaimWarning] = []
    for line in lines:
        text = str(line.get("text") or "").strip()
        if not text:
            continue
        lowered = text.lower()
        line_id = line.get("id")
        script_line_id = int(line_id) if isinstance(line_id, int) else None
        if MONEY_RE.search(text):
            warnings.append(_warning(script_line_id, text, "money", "medium", "Revisa cifra economica o coste."))
        elif YEAR_RE.search(text):
            warnings.append(_warning(script_line_id, text, "date", "medium", "Confirma fecha antes de publicar."))
        elif NUMBER_RE.search(text):
            warnings.append(_warning(script_line_id, text, "number", "medium", "Confirma numero o cantidad."))
        for word, claim_type in HIGH_RISK_WORDS.items():
            if word in lowered:
                warnings.append(_warning(script_line_id, text, claim_type, "high", "Anade fuente y revisa el claim."))
                break
        if any(word in lowered for word in ABSOLUTE_WORDS):
            warnings.append(_warning(script_line_id, text, "absolute", "medium", "Evita absolutos si no estan verificados."))
    return warnings


def line_needs_source(text: str) -> bool:
    return bool(
        MONEY_RE.search(text)
        or YEAR_RE.search(text)
        or NUMBER_RE.search(text)
        or any(word in text.lower() for word in ABSOLUTE_WORDS)
        or any(word in text.lower() for word in HIGH_RISK_WORDS)
    )


def claim_type_for_text(text: str) -> str | None:
    lowered = text.lower()
    if MONEY_RE.search(text):
        return "money"
    if YEAR_RE.search(text):
        return "date"
    if NUMBER_RE.search(text):
        return "number"
    for word, claim_type in HIGH_RISK_WORDS.items():
        if word in lowered:
            return claim_type
    if any(word in lowered for word in ABSOLUTE_WORDS):
        return "absolute"
    return None


def _warning(
    script_line_id: int | None,
    text: str,
    claim_type: str,
    risk_level: str,
    suggestion: str,
) -> ClaimWarning:
    return ClaimWarning(
        script_line_id=script_line_id,
        text=text,
        claim_type=claim_type,
        risk_level=risk_level,
        needs_source=True,
        suggestion=suggestion,
    )
