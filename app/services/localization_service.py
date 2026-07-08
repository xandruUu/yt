from __future__ import annotations

from app.services.prompt_service import render_prompt
from app.utils.language import needs_native_review


def build_localization_prompt(
    *,
    source_language: str,
    target_language: str,
    target_market: str,
    topic_title: str,
    script_text: str,
) -> str:
    return render_prompt(
        "localization_prompt.md",
        source_language=source_language,
        target_language=target_language,
        target_market=target_market,
        topic_title=topic_title,
        script_text=script_text,
    )


def localization_review_required(target_language: str) -> bool:
    return needs_native_review(target_language)

