from __future__ import annotations

from app.services.content_quality_service import analyze_script_quality
from app.services.fact_check_helper_service import analyze_claims


def test_fact_check_detects_numbers_money_dates_and_absolutes() -> None:
    warnings = analyze_claims(
        [
            {"text": "En 2024 esto costo 20 millones."},
            {"text": "Siempre es el sistema mas grande."},
        ]
    )

    claim_types = {warning.claim_type for warning in warnings}
    assert "money" in claim_types
    assert "absolute" in claim_types
    assert all(warning.needs_source for warning in warnings)


def test_quality_detects_generic_intro_and_missing_visuals() -> None:
    report = analyze_script_quality(
        lines=[
            {"text": "Hola, en este video vamos a explicar algo muy importante.", "duration_seconds": 3},
            {"text": "Esta frase no tiene visual.", "duration_seconds": 3},
        ],
        hook_text="La razon oculta",
        title="La razon oculta",
        target_duration_seconds=40,
    )

    assert report.blocking_issues
    assert report.warnings
    assert report.score < 100
