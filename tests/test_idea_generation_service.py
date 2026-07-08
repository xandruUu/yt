from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.enums import GeneratedIdeaStatus, TopicStatus
from app.db.models import Base
from app.providers.base import TrendItem
from app.services.idea_generation_service import (
    convert_generated_idea_to_topic,
    generate_ideas_from_trend,
    generate_ideas_from_trends,
    persist_generated_ideas,
)


def test_generates_heuristic_ideas_without_llm() -> None:
    ideas = generate_ideas_from_trend(
        TrendItem(
            title="QR codes still work when damaged",
            summary="Error correction makes damaged codes readable",
            source="manual",
        ),
        target_language="es",
        target_market="spain_latam",
        category="tech_explained",
        ideas_per_trend=3,
    )

    assert len(ideas) == 3
    assert all(idea["title"].strip() for idea in ideas)
    assert all(0 <= idea["total_score"] <= 100 for idea in ideas)
    assert all(idea["status"] == GeneratedIdeaStatus.SUGGESTED.value for idea in ideas)


def test_generation_skips_provider_errors() -> None:
    ideas = generate_ideas_from_trends(
        [
            TrendItem(
                title="Broken provider result",
                source="manual",
                popularity_signals={"provider_error": "missing key"},
            )
        ],
        target_language="es",
        target_market="global",
        category="tech_explained",
    )

    assert ideas == []


def test_persist_and_convert_generated_idea_to_topic() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, future=True)
    session = session_factory()

    ideas = generate_ideas_from_trend(
        TrendItem(title="A startup failed because of one software bug", source="manual"),
        target_language="es",
        target_market="global",
        category="business_case",
        ideas_per_trend=1,
    )
    saved = persist_generated_ideas(session, ideas)
    topic = convert_generated_idea_to_topic(session, saved[0])

    assert len(saved) == 1
    assert topic.title == saved[0].title
    assert topic.status == TopicStatus.APPROVED_FOR_HOOKS.value
    assert saved[0].status == GeneratedIdeaStatus.CONVERTED_TO_TOPIC.value
    assert saved[0].converted_topic_id == topic.id

    same_topic = convert_generated_idea_to_topic(session, saved[0])
    assert same_topic.id == topic.id

    session.close()
