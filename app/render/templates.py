from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RenderTemplate:
    name: str
    background_color: str
    subtitle_color: str
    subtitle_outline: str
    description: str


TEMPLATES = {
    "clean_text_focus": RenderTemplate(
        name="clean_text_focus",
        background_color="#18212f",
        subtitle_color="&H00FFFFFF",
        subtitle_outline="&H00000000",
        description="Dark neutral background with large readable subtitles.",
    ),
    "tech_dark": RenderTemplate(
        name="tech_dark",
        background_color="#070b10",
        subtitle_color="&H00F4F8FF",
        subtitle_outline="&H0000A3FF",
        description="Dark tech visual direction.",
    ),
    "documentary_alert": RenderTemplate(
        name="documentary_alert",
        background_color="#170b0b",
        subtitle_color="&H00FFFFFF",
        subtitle_outline="&H000024DD",
        description="High-contrast alert style.",
    ),
    "minimal_educational": RenderTemplate(
        name="minimal_educational",
        background_color="#edf2f7",
        subtitle_color="&H00111111",
        subtitle_outline="&H00FFFFFF",
        description="Light educational style.",
    ),
}


def get_template(name: str) -> RenderTemplate:
    return TEMPLATES.get(name, TEMPLATES["clean_text_focus"])

