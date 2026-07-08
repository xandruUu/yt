from __future__ import annotations

import json
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.ai.llm_orchestrator import get_llm_provider
from app.core.enums import MetadataSuggestionStatus
from app.db import models
from app.db.repositories import create_metadata_suggestion
from app.llm.base import LLMProviderUnavailable
from app.utils.text import normalize_hashtags


@dataclass(frozen=True)
class MetadataPayload:
    description: str
    hashtags: list[str]
    pinned_comment: str
    upload_notes: str
    synthetic_media_note: bool = False
    made_for_kids_recommendation: bool = False


@dataclass(frozen=True)
class MetadataGenerationResult:
    metadata: models.MetadataSuggestion
    provider_name: str
    prompt: str
    warnings: list[str]


def generate_metadata(
    session: Session,
    *,
    generated_idea_id: int | None,
    topic_id: int | None,
    hook_id: int,
    title_id: int,
    script_id: int | None,
    language: str,
    market: str,
    provider_name: str = "manual",
) -> MetadataGenerationResult:
    topic = session.get(models.Topic, topic_id) if topic_id else None
    idea = session.get(models.GeneratedIdea, generated_idea_id) if generated_idea_id else None
    hook = session.get(models.Hook, hook_id)
    title = session.get(models.GeneratedTitle, title_id)
    script = session.get(models.Script, script_id) if script_id else None
    if hook is None or title is None:
        raise ValueError("Se necesita hook y titulo para generar metadata.")
    if topic is None and idea is None:
        raise ValueError("Se necesita idea o topic para generar metadata.")

    result = generate_metadata_payload(
        idea_title=idea.title if idea else topic.title,
        idea_summary=idea.summary if idea else topic.summary,
        hook_text=hook.text,
        title=title.title,
        script_text=script.script_text if script else "",
        language=language,
        market=market,
        provider_name=provider_name,
    )
    metadata = create_metadata_suggestion(
        session,
        generated_idea_id=generated_idea_id,
        topic_id=topic_id,
        hook_id=hook_id,
        title_id=title_id,
        script_id=script_id,
        language=language,
        market=market,
        description=result.metadata.description,
        hashtags_json=result.metadata.hashtags_json,
        pinned_comment=result.metadata.pinned_comment,
        upload_notes=result.metadata.upload_notes,
        synthetic_media_note=result.metadata.synthetic_media_note,
        made_for_kids_recommendation=result.metadata.made_for_kids_recommendation,
        status=MetadataSuggestionStatus.SUGGESTED.value,
    )
    return MetadataGenerationResult(metadata, result.provider_name, result.prompt, result.warnings)


def generate_metadata_payload(
    *,
    idea_title: str,
    idea_summary: str,
    hook_text: str,
    title: str,
    script_text: str,
    language: str,
    market: str,
    provider_name: str = "manual",
) -> MetadataGenerationResult:
    system_prompt, user_prompt = build_metadata_prompt(
        idea_title=idea_title,
        idea_summary=idea_summary,
        hook_text=hook_text,
        title=title,
        script_text=script_text,
        language=language,
        market=market,
    )
    provider = get_llm_provider(provider_name)
    prompt = provider.generate_text(system_prompt, user_prompt) if provider.name == "manual" else user_prompt
    warnings: list[str] = []
    payload: MetadataPayload | None = None
    if provider.name != "manual":
        try:
            payload = _payload_from_json(provider.generate_json(system_prompt, user_prompt, schema_name="metadata"))
        except (LLMProviderUnavailable, ValueError, TypeError) as exc:
            warnings.append(f"{provider.name} no genero metadata valida; se uso fallback heuristico: {exc}")
    if payload is None:
        payload = generate_heuristic_metadata(
            idea_title=idea_title,
            idea_summary=idea_summary,
            hook_text=hook_text,
            title=title,
            language=language,
            market=market,
        )

    empty = models.MetadataSuggestion(
        description=payload.description,
        hashtags_json=json.dumps(payload.hashtags, ensure_ascii=False),
        pinned_comment=payload.pinned_comment,
        upload_notes=payload.upload_notes,
        synthetic_media_note=payload.synthetic_media_note,
        made_for_kids_recommendation=payload.made_for_kids_recommendation,
        language=language,
        market=market,
    )
    return MetadataGenerationResult(empty, provider.name, prompt, warnings)


def build_metadata_prompt(
    *,
    idea_title: str,
    idea_summary: str,
    hook_text: str,
    title: str,
    script_text: str,
    language: str,
    market: str,
) -> tuple[str, str]:
    system_prompt = "Crea metadata segura y util para YouTube Shorts sin spam ni claims inventados."
    user_prompt = f"""
Idea:
{idea_title}

Resumen:
{idea_summary}

Gancho:
{hook_text}

Titulo elegido:
{title}

Guion si existe:
{script_text}

Idioma: {language}
Mercado: {market}

Reglas:
- Descripcion breve: 1-2 parrafos cortos.
- Hashtags: 3-5 maximo.
- Incluye #shorts.
- No hagas spam.
- No prometas resultados falsos.
- Devuelve JSON valido.

Formato:
{{
  "description": "...",
  "hashtags": ["#shorts", "..."],
  "pinned_comment": "...",
  "upload_notes": "...",
  "synthetic_media_note": false,
  "made_for_kids_recommendation": false
}}
""".strip()
    return system_prompt, user_prompt


def generate_heuristic_metadata(
    *,
    idea_title: str,
    idea_summary: str,
    hook_text: str,
    title: str,
    language: str,
    market: str,
) -> MetadataPayload:
    if language == "en":
        description = f"{title}\n\nA quick Short explaining {idea_summary or idea_title} without fake claims."
        pinned = "Which part should be explained next?"
    else:
        description = f"{title}\n\nUn Short rapido para entender {idea_summary or idea_title} sin promesas falsas."
        pinned = "Que parte quieres que explique despues?"
    tags = _safe_hashtags(["#shorts", "#youtubeShorts", *_topic_tags(idea_title, hook_text, market)])
    return MetadataPayload(
        description=description.strip(),
        hashtags=tags,
        pinned_comment=pinned,
        upload_notes="Subida manual. Revisar claims, fuentes y contenido sintetico antes de publicar.",
        synthetic_media_note=False,
        made_for_kids_recommendation=False,
    )


def _payload_from_json(value: dict[str, object] | list[object]) -> MetadataPayload:
    if not isinstance(value, dict):
        raise ValueError("La metadata debe ser un objeto JSON.")
    description = str(value.get("description") or "").strip()
    if not description:
        raise ValueError("La metadata necesita descripcion.")
    return MetadataPayload(
        description=description,
        hashtags=_safe_hashtags(value.get("hashtags", [])),
        pinned_comment=str(value.get("pinned_comment") or ""),
        upload_notes=str(value.get("upload_notes") or ""),
        synthetic_media_note=bool(value.get("synthetic_media_note", False)),
        made_for_kids_recommendation=bool(value.get("made_for_kids_recommendation", False)),
    )


def _safe_hashtags(raw: object) -> list[str]:
    tags = normalize_hashtags(raw if isinstance(raw, list) else [])
    lowered = {tag.lower() for tag in tags}
    if "#shorts" not in lowered:
        tags.insert(0, "#shorts")
    deduped: list[str] = []
    seen: set[str] = set()
    for tag in tags:
        key = tag.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(tag)
    return deduped[:5]


def _topic_tags(idea_title: str, hook_text: str, market: str) -> list[str]:
    text = f"{idea_title} {hook_text}".lower()
    tags = []
    if "ai" in text or "ia" in text:
        tags.append("#ai")
    if any(word in text for word in ("tech", "software", "codigo", "code")):
        tags.append("#tech")
    if any(word in text for word in ("money", "dinero", "business", "startup")):
        tags.append("#business")
    if market in {"spain", "latam", "spain_latam"}:
        tags.append("#aprende")
    return tags or ["#curiosidades", "#explicado"]
