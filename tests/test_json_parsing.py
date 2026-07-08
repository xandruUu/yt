from __future__ import annotations

import pytest

from app.utils.json_parsing import extract_json_array, safe_int_score


def test_extracts_plain_json_array() -> None:
    assert extract_json_array('[{"titulo": "Idea"}]') == [{"titulo": "Idea"}]


def test_extracts_json_array_from_fenced_block() -> None:
    text = """
    Respuesta:
    ```json
    [{"titulo": "Idea", "potencial_viral": 8}]
    ```
    """

    assert extract_json_array(text)[0]["potencial_viral"] == 8


def test_invalid_json_fails_controlled() -> None:
    with pytest.raises(ValueError, match="JSON"):
        extract_json_array("no hay json aqui")


def test_safe_int_score_normalizes_values() -> None:
    assert safe_int_score("8.7") == 9
    assert safe_int_score(99) == 10
    assert safe_int_score(-5) == 0
    assert safe_int_score(None, default=6) == 6
