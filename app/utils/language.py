from __future__ import annotations

LANGUAGE_LABELS = {
    "en": "English",
    "es": "Spanish",
    "hi": "Hindi",
    "hi_hinglish": "Hindi/Hinglish",
}

EXPORT_LANGUAGE_FOLDERS = {
    "en": "EN",
    "es": "ES",
    "hi": "HI",
    "hi_hinglish": "HI",
}


def language_label(language: str) -> str:
    return LANGUAGE_LABELS.get(language, language)


def export_language_folder(language: str) -> str:
    return EXPORT_LANGUAGE_FOLDERS.get(language, language.upper())


def needs_native_review(language: str) -> bool:
    return language == "hi_hinglish"

