from __future__ import annotations

from pathlib import Path

PROMPT_DIR = Path(__file__).resolve().parents[1] / "prompts"


def load_prompt(name: str) -> str:
    path = PROMPT_DIR / name
    if not path.exists():
        raise FileNotFoundError(path)
    return path.read_text(encoding="utf-8")


def render_prompt(template_name: str, **values: object) -> str:
    rendered = load_prompt(template_name)
    for key, value in values.items():
        rendered = rendered.replace("{{" + key + "}}", str(value))
    return rendered

