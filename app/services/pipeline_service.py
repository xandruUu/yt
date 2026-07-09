from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.llm_gateway import LLMGateway
from app.ai.ollama_client import compact_json
from app.ai.prompt_context_builder import (
    build_deep_research_context,
    build_metadata_context,
    build_research_context,
)
from app.ai.schemas.creation import DeepIdeaPayload, DeepResearchResponse
from app.ai.schemas.metadata import MetadataRecipeResponse
from app.ai.schemas.research import ResearchIdeaPayload, ResearchIdeasResponse
from app.config.settings import get_settings
from app.db import models
from app.db.repositories import (
    add_and_commit,
    create_creation_inbox_item,
    create_deep_idea_candidate,
    create_deep_research_run,
    create_idea_candidate,
    create_metadata_recipe_draft,
    create_provider_fetch_log,
    create_research_run,
    create_trend_item,
    create_video_project,
)
from app.providers.base import TrendItem as ProviderTrendItem
from app.services.trend_research_service import TrendResearchService
from app.services.trend_scoring_service import score_trend_item

GENERAL_SEED_SIGNALS = """Scientists found a strange deep sea animal that looks animated
NASA released new images that explain how tiny space rocks become dangerous
An old engineering mistake is suddenly going viral because it explains a modern problem
A simple AI tool changed how creators edit short videos
A forgotten historical survival trick is getting attention again
"""

RESEARCH_SYSTEM_PROMPT = """You are the creative research director of a YouTube Shorts factory.
The app interface is Spanish, but all generated creative content must be English.
You receive normalized trend signals from APIs and public feeds.
You must identify viral short ideas without being constrained by category.
Do not invent current facts that are not supported by the provided trend signals.
Return valid JSON only."""

DEEP_RESEARCH_SYSTEM_PROMPT = """You are a YouTube Shorts creative strategist.
The UI is Spanish, but all creative outputs must be English.
Turn one broad idea into specific, visual, high-retention short concepts.
Return valid JSON only."""

METADATA_SYSTEM_PROMPT = """You are a YouTube Shorts packaging expert.
The UI is Spanish, but titles, hooks, descriptions and hashtags must be English.
Avoid false clickbait and unsafe claims.
Return valid JSON only."""


@dataclass(frozen=True)
class PipelineResearchResult:
    research_run: models.ResearchRun
    ideas: list[models.IdeaCandidate]
    warnings: list[str]


def run_general_research(
    session: Session,
    *,
    idea_count: int = 5,
    market: str | None = None,
    lookback_days: int = 30,
    include_youtube: bool | None = None,
    include_rss: bool | None = None,
    include_hackernews: bool | None = None,
    manual_input: str = "",
    llm_gateway: LLMGateway | None = None,
) -> PipelineResearchResult:
    settings = get_settings()
    idea_count = max(1, min(15, int(idea_count)))
    market = market or settings.target_market
    run = create_research_run(
        session,
        started_at=datetime.now(UTC),
        idea_count_requested=idea_count,
        lookback_days=lookback_days,
        target_market=market,
        content_language=settings.content_language,
        status="running",
        provider_summary_json="{}",
    )
    providers = _selected_research_providers(
        include_youtube=include_youtube,
        include_rss=include_rss,
        include_hackernews=include_hackernews,
    )
    provider_input = manual_input.strip() or GENERAL_SEED_SIGNALS
    service = TrendResearchService()
    result = service.research(
        providers=providers,
        query=None,
        market=market,
        language=settings.content_language,
        category="general",
        limit=max(idea_count * 4, 12),
        manual_input=provider_input,
    )
    trend_records = _persist_trend_research_result(session, run, result.items, providers)
    ideas_payload = _generate_research_ideas(
        session,
        run.id,
        idea_count,
        llm_gateway=llm_gateway,
    )
    ideas = [
        create_idea_candidate(
            session,
            research_run_id=run.id,
            title=idea.title,
            short_description=idea.short_description,
            viral_angle=idea.viral_angle,
            why_now=idea.why_now,
            visual_potential=idea.visual_potential,
            estimated_duration_seconds=idea.estimated_duration_seconds,
            source_item_ids_json=json.dumps(idea.source_item_ids, ensure_ascii=False),
            risk_level=idea.risk_level,
            risk_notes=idea.risk_notes,
            status="suggested",
        )
        for idea in ideas_payload[:idea_count]
    ]
    run.finished_at = datetime.now(UTC)
    run.status = "completed"
    run.provider_summary_json = json.dumps(
        {
            "providers_used": result.providers_used,
            "warnings": result.warnings,
            "trend_items": len(trend_records),
            "ideas": len(ideas),
        },
        ensure_ascii=False,
    )
    add_and_commit(session, run)
    return PipelineResearchResult(research_run=run, ideas=ideas, warnings=result.warnings)


def send_idea_to_creation(session: Session, idea_candidate_id: int) -> models.CreationInboxItem:
    idea = _get_or_raise(session, models.IdeaCandidate, idea_candidate_id)
    idea.status = "sent_to_creation"
    session.commit()
    inbox = create_creation_inbox_item(
        session,
        idea_candidate_id=idea.id,
        status="pending",
        notes="Sent from Investigacion.",
    )
    return inbox


def run_deep_research(
    session: Session,
    *,
    idea_candidate_id: int,
    count: int = 4,
    llm_gateway: LLMGateway | None = None,
) -> tuple[models.DeepResearchRun, list[models.DeepIdeaCandidate]]:
    idea = _get_or_raise(session, models.IdeaCandidate, idea_candidate_id)
    run = create_deep_research_run(
        session,
        idea_candidate_id=idea.id,
        started_at=datetime.now(UTC),
        status="running",
    )
    payloads = _generate_deep_ideas(session, idea.id, count=count, llm_gateway=llm_gateway)
    deep_ideas = [
        create_deep_idea_candidate(
            session,
            deep_research_run_id=run.id,
            title=payload.title,
            detailed_description=payload.detailed_description,
            specific_angle=payload.specific_angle,
            why_it_can_go_viral=payload.why_it_can_go_viral,
            possible_hook=payload.possible_hook,
            facts_to_verify_json=json.dumps(payload.facts_to_verify, ensure_ascii=False),
            visual_opportunities_json=json.dumps(payload.visual_opportunities, ensure_ascii=False),
            risk_level=payload.risk_level,
            risk_notes=payload.risk_notes,
            status="suggested",
        )
        for payload in payloads[:count]
    ]
    run.finished_at = datetime.now(UTC)
    run.status = "completed"
    add_and_commit(session, run)
    return run, deep_ideas


def send_deep_idea_to_ideas(session: Session, deep_idea_candidate_id: int) -> models.MetadataRecipeDraft:
    deep_idea = _get_or_raise(session, models.DeepIdeaCandidate, deep_idea_candidate_id)
    deep_idea.status = "selected"
    session.commit()
    return create_metadata_recipe(session, deep_idea.id)


def create_metadata_recipe(
    session: Session,
    deep_idea_candidate_id: int,
    llm_gateway: LLMGateway | None = None,
) -> models.MetadataRecipeDraft:
    payload = _generate_metadata_recipe(session, deep_idea_candidate_id, llm_gateway=llm_gateway)
    return create_metadata_recipe_draft(
        session,
        deep_idea_candidate_id=deep_idea_candidate_id,
        titles_json=json.dumps([item.model_dump() for item in payload.titles], ensure_ascii=False),
        hooks_json=json.dumps([item.model_dump() for item in payload.hooks], ensure_ascii=False),
        descriptions_json=json.dumps([item.model_dump() for item in payload.descriptions], ensure_ascii=False),
        hashtag_sets_json=json.dumps([item.model_dump() for item in payload.hashtag_sets], ensure_ascii=False),
        status="generated",
    )


def create_project_from_recipe(
    session: Session,
    *,
    metadata_recipe_id: int,
    title: str,
    hook: str,
    description: str,
    hashtags: list[str],
    character_profile_id: int | None = None,
) -> models.VideoProject:
    settings = get_settings()
    recipe = _get_or_raise(session, models.MetadataRecipeDraft, metadata_recipe_id)
    recipe.selected_title = title
    recipe.selected_hook = hook
    recipe.selected_description = description
    recipe.selected_hashtags_json = json.dumps(hashtags, ensure_ascii=False)
    recipe.status = "selected"
    session.commit()
    return create_video_project(
        session,
        deep_idea_candidate_id=recipe.deep_idea_candidate_id,
        metadata_recipe_id=recipe.id,
        character_profile_id=character_profile_id,
        title=title,
        description=description,
        hashtags_json=json.dumps(hashtags, ensure_ascii=False),
        hook=hook,
        content_language=settings.content_language,
        ui_language=settings.app_ui_language,
        target_market=settings.target_market,
        target_duration_seconds=60,
        max_duration_seconds=settings.max_video_duration_seconds,
        status="metadata_selected",
    )


def pending_creation_inbox(session: Session) -> list[models.CreationInboxItem]:
    return list(
        session.scalars(
            select(models.CreationInboxItem)
            .where(models.CreationInboxItem.status == "pending")
            .order_by(models.CreationInboxItem.created_at.desc())
        ).all()
    )


def pending_metadata_recipes(session: Session) -> list[models.MetadataRecipeDraft]:
    return list(
        session.scalars(
            select(models.MetadataRecipeDraft)
            .where(models.MetadataRecipeDraft.status.in_(["generated", "draft"]))
            .order_by(models.MetadataRecipeDraft.created_at.desc())
        ).all()
    )


def _selected_research_providers(
    *,
    include_youtube: bool | None,
    include_rss: bool | None,
    include_hackernews: bool | None,
) -> list[str]:
    settings = get_settings()
    providers = ["manual"]
    if include_rss if include_rss is not None else settings.enable_rss_provider:
        providers.append("rss")
    if include_hackernews if include_hackernews is not None else settings.enable_hackernews_provider:
        providers.append("hackernews")
    if include_youtube if include_youtube is not None else settings.enable_youtube_provider:
        providers.append("youtube")
    return providers


def _persist_trend_research_result(
    session: Session,
    run: models.ResearchRun,
    items: list[ProviderTrendItem],
    providers: list[str],
) -> list[models.TrendItem]:
    for provider in providers:
        create_provider_fetch_log(
            session,
            research_run_id=run.id,
            provider_name=provider,
            request_payload_json=json.dumps({"mode": "general_viral_research"}, ensure_ascii=False),
            response_summary_json=json.dumps({"items_seen": len(items)}, ensure_ascii=False),
            status="completed",
            started_at=run.started_at,
            finished_at=datetime.now(UTC),
        )
    records = []
    for item in items:
        score = score_trend_item(item, run.target_market, run.content_language, "other")
        signals = item.popularity_signals
        views = _int_or_none(signals.get("views"))
        likes = _int_or_none(signals.get("likes"))
        comments = _int_or_none(signals.get("comments") or signals.get("hn_score"))
        age_hours = max(float(signals.get("age_hours") or 24), 1.0)
        velocity = (views or comments or 1) / age_hours
        engagement = ((likes or 0) + (comments or 0) * 3) / max(views or 1, 1)
        records.append(
            create_trend_item(
                session,
                research_run_id=run.id,
                provider_name=item.source,
                external_id=str(item.raw_data.get("id") or ""),
                url=item.source_url,
                title=item.title,
                summary=item.summary or "",
                published_at=item.published_at,
                author_or_channel=str(item.raw_data.get("author") or item.raw_data.get("channel") or ""),
                views=views,
                likes=likes,
                comments=comments,
                shares=_int_or_none(signals.get("shares")),
                duration_seconds=_float_or_none(signals.get("duration_seconds")),
                language=item.language,
                region=item.market,
                raw_json=json.dumps(item.model_dump(mode="json"), ensure_ascii=False),
                viral_score=float(score.viral_score),
                velocity_score=velocity,
                engagement_score=engagement,
                novelty_score=float(score.novelty_score),
                visual_potential_score=float(score.visual_score),
                shorts_suitability_score=float(score.narrative_clarity_score),
                risk_score=float(max(score.copyright_risk, score.monetization_risk)),
                source_reliability_score=7.0 if item.source != "manual" else 4.0,
            )
        )
    return records


def _generate_research_ideas(
    session: Session,
    research_run_id: int,
    idea_count: int,
    llm_gateway: LLMGateway | None,
) -> list[ResearchIdeaPayload]:
    context = build_research_context(session, research_run_id)
    gateway = llm_gateway or LLMGateway()
    user_prompt = (
        f"Generate {idea_count} viral YouTube Shorts ideas in English. "
        "Do not limit yourself to a predefined category. Use the trend signals below. "
        "Each idea must be suitable for a 45-90 second short. "
        "Avoid unsafe, defamatory, medical, financial or legal claims.\n\n"
        f"Context JSON:\n{compact_json(context)}"
    )
    result = gateway.generate_json(
        system_prompt=RESEARCH_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        schema=ResearchIdeasResponse,
        temperature=get_settings().ollama_temperature_research,
    )
    if result.ok and isinstance(result.data, ResearchIdeasResponse) and result.data.ideas:
        return result.data.ideas
    return _fallback_research_ideas(context, idea_count)


def _generate_deep_ideas(
    session: Session,
    idea_candidate_id: int,
    count: int,
    llm_gateway: LLMGateway | None,
) -> list[DeepIdeaPayload]:
    context = build_deep_research_context(session, idea_candidate_id)
    gateway = llm_gateway or LLMGateway()
    result = gateway.generate_json(
        system_prompt=DEEP_RESEARCH_SYSTEM_PROMPT,
        user_prompt=f"Generate {count} deep short ideas in English from this JSON:\n{compact_json(context)}",
        schema=DeepResearchResponse,
        temperature=get_settings().ollama_temperature_research,
    )
    if result.ok and isinstance(result.data, DeepResearchResponse) and result.data.deep_ideas:
        return result.data.deep_ideas
    idea = context["idea"]
    title = str(idea["title"])
    return [
        DeepIdeaPayload(
            title=f"{title}: the hidden visual story",
            detailed_description=f"A specific version of '{title}' focused on one surprising visual reveal.",
            specific_angle="One concrete example, explained with escalating curiosity and a strong payoff.",
            why_it_can_go_viral="It turns a broad trend into a simple question with a visual answer.",
            possible_hook=f"This looks random, but it explains why {title.lower()} is everywhere.",
            facts_to_verify=["Verify the source trend and avoid unsupported claims."],
            visual_opportunities=["Animated comparison", "Nero pointing at a visual clue", "Quick before/after reveal"],
        ),
        DeepIdeaPayload(
            title=f"{title}: what most people miss",
            detailed_description="A myth-busting version that explains the overlooked detail behind the trend.",
            specific_angle="Contrast what viewers assume with what the sources actually suggest.",
            why_it_can_go_viral="Curiosity gap plus correction creates retention.",
            possible_hook="Most people are missing the weirdest part.",
            facts_to_verify=["Check any factual claim before final script approval."],
            visual_opportunities=["Split-screen assumption vs reality", "Nero detective board"],
        ),
    ]


def _generate_metadata_recipe(
    session: Session,
    deep_idea_candidate_id: int,
    llm_gateway: LLMGateway | None,
) -> MetadataRecipeResponse:
    context = build_metadata_context(session, deep_idea_candidate_id)
    gateway = llm_gateway or LLMGateway()
    result = gateway.generate_json(
        system_prompt=METADATA_SYSTEM_PROMPT,
        user_prompt=f"Generate metadata recipe options in English from this JSON:\n{compact_json(context)}",
        schema=MetadataRecipeResponse,
        temperature=get_settings().ollama_temperature_metadata,
    )
    if result.ok and isinstance(result.data, MetadataRecipeResponse):
        return result.data
    idea = context["deep_idea"]
    title = str(idea["title"])
    hook = str(idea.get("possible_hook") or "This story has one detail almost everyone misses.")
    return MetadataRecipeResponse.model_validate(
        {
            "titles": [
                {"title": title[:95], "score": 82, "reason": "Clear and curiosity-driven.", "clickbait_risk": "low"},
                {"title": f"The Strange Truth Behind {title}"[:95], "score": 78, "reason": "Strong mystery frame.", "clickbait_risk": "medium"},
            ],
            "hooks": [
                {"hook": hook, "style": "curiosity", "reason": "Starts with a clear curiosity gap."},
                {"hook": "This looks simple, but the explanation is weird.", "style": "contrast", "reason": "Fast contrast hook."},
            ],
            "descriptions": [
                {"description": f"A quick visual breakdown of {title}.", "reason": "Short and direct."},
                {"description": f"Nero explains the surprising detail behind {title}.", "reason": "Brand-consistent."},
            ],
            "hashtag_sets": [
                {"hashtags": ["#shorts", "#science", "#facts"], "strategy": "General discovery"},
                {"hashtags": ["#shorts", "#learnontiktok", "#dailybrainbreak"], "strategy": "Brand + learning"},
            ],
        }
    )


def _fallback_research_ideas(context: dict[str, object], idea_count: int) -> list[ResearchIdeaPayload]:
    signals = list(context.get("trend_signals", []))
    ideas = []
    for signal in signals[:idea_count]:
        title = str(signal.get("title") or "A strange trend explained")
        source_id = int(signal.get("id") or 0)
        ideas.append(
            ResearchIdeaPayload(
                title=_english_title_from_signal(title),
                short_description=f"A fast visual explainer based on this trend signal: {title}",
                viral_angle="It creates a clear curiosity gap and can be explained visually in under 90 seconds.",
                why_now="It appears in recent trend signals collected by the app.",
                visual_potential="Nero can guide a quick animated breakdown with comparisons, reveals and simple props.",
                estimated_duration_seconds=60,
                source_item_ids=[source_id] if source_id else [],
                risk_level="low",
                risk_notes="Verify factual claims before production.",
            )
        )
    while len(ideas) < idea_count:
        index = len(ideas) + 1
        ideas.append(
            ResearchIdeaPayload(
                title=f"Why This Weird Internet Pattern Keeps Going Viral #{index}",
                short_description="A general viral-pattern explainer generated from fallback research signals.",
                viral_angle="Mystery plus quick explanation.",
                why_now="Fallback mode keeps the pipeline moving when providers or LLM are unavailable.",
                visual_potential="Animated detective board, Nero reactions, and visual cause-effect reveals.",
                estimated_duration_seconds=60,
                source_item_ids=[],
                risk_level="low",
                risk_notes="Use as a draft until real sources are attached.",
            )
        )
    return ideas


def _english_title_from_signal(title: str) -> str:
    cleaned = " ".join(title.split())
    if cleaned.endswith("?"):
        return cleaned
    return f"Why {cleaned[:120]} Matters"


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _float_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _get_or_raise(session: Session, model: type[models.Base], entity_id: int):
    entity = session.get(model, entity_id)
    if entity is None:
        raise ValueError(f"{model.__name__} not found: {entity_id}")
    return entity

