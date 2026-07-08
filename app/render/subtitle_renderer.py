from __future__ import annotations

from app.render.templates import get_template


def ass_force_style(template_name: str) -> str:
    template = get_template(template_name)
    return (
        "FontName=Arial,"
        "FontSize=18,"
        f"PrimaryColour={template.subtitle_color},"
        f"OutlineColour={template.subtitle_outline},"
        "BorderStyle=3,"
        "Outline=2,"
        "Shadow=0,"
        "Alignment=2,"
        "MarginV=280"
    )

