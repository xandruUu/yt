from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class QualityReport:
    score: int
    warnings: list[str]
    blocking_issues: list[str]


WEAK_STARTS = ("hola", "bienvenidos", "en este video", "hoy vamos", "hello", "welcome", "in this video")
SPAM_CTA = ("suscribete suscribete", "like y comparte ya", "compra ahora", "hazte rico")


def analyze_script_quality(
    *,
    lines: list[dict[str, object]],
    hook_text: str,
    title: str,
    target_duration_seconds: int,
) -> QualityReport:
    warnings: list[str] = []
    blocking: list[str] = []
    score = 100

    if not lines:
        return QualityReport(0, [], ["El guion no tiene lineas."])

    first_line = str(lines[0].get("text") or "").strip().lower()
    if first_line.startswith(WEAK_STARTS):
        blocking.append("El guion empieza con una intro generica.")
        score -= 25
    if len(first_line.split()) < 4:
        warnings.append("La primera linea puede ser demasiado floja o corta.")
        score -= 8

    total_duration = sum(float(line.get("duration_seconds") or line.get("estimated_duration_seconds") or 0) for line in lines)
    if total_duration <= 0:
        blocking.append("La duracion estimada debe ser mayor que 0.")
        score -= 30
    elif abs(total_duration - target_duration_seconds) > max(12, target_duration_seconds * 0.45):
        warnings.append("La duracion estimada se aleja bastante del objetivo.")
        score -= 10

    if len(lines) > 24:
        warnings.append("Hay demasiadas lineas para un Short rapido.")
        score -= 8

    for index, line in enumerate(lines, start=1):
        text = str(line.get("text") or "")
        if len(text.split()) > 24:
            warnings.append(f"Linea {index}: frase larga para subtitulo.")
            score -= 3
        if not str(line.get("visual_suggestion") or "").strip():
            warnings.append(f"Linea {index}: falta sugerencia visual.")
            score -= 2
        lowered = text.lower()
        if any(pattern in lowered for pattern in SPAM_CTA):
            blocking.append(f"Linea {index}: CTA spam o promesa agresiva.")
            score -= 20

    if hook_text and hook_text.lower().split()[0] not in " ".join(line.get("text", "") for line in lines[:2]).lower():
        warnings.append("El inicio no conecta claramente con el hook elegido.")
        score -= 5
    if title and not any(word.lower() in " ".join(str(line.get("text") or "") for line in lines).lower() for word in title.split()[:3]):
        warnings.append("El guion podria responder mejor al titulo elegido.")
        score -= 5

    return QualityReport(max(0, min(100, score)), warnings, blocking)
