from __future__ import annotations

import json

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.enums import HookType
from app.db.models import Base, Hook, Topic
from app.services.hook_generation_service import (
    HOOK_TYPES,
    generate_heuristic_hook_candidates,
    generate_hook_candidates,
    generate_hooks_for_topic,
)


def test_heuristic_generation_creates_25_hooks() -> None:
    hooks = generate_heuristic_hook_candidates(
        topic_title="QR codes still work when damaged",
        topic_summary="Error correction makes damaged QR codes readable.",
        language="es",
        category="tech_explained",
    )

    assert len(hooks) == 25
    assert {hook.hook_type for hook in hooks} == set(HOOK_TYPES)
    assert all(hook.text.strip() for hook in hooks)
    assert all(0 <= hook.total_score <= 100 for hook in hooks)
    assert all(0 <= hook.risk_score <= 10 for hook in hooks)


def test_manual_provider_result_includes_prompt_and_candidates() -> None:
    result = generate_hook_candidates(
        topic_title="AI agents automate repetitive work",
        topic_summary="A practical automation explainer.",
        language="en",
        market="global",
        category="ai_tools",
        provider_name="manual",
    )

    assert len(result.candidates) == 25
    assert result.provider_name == "manual"
    assert "Generate 25 hooks" in result.prompt or "Genera 25 hooks" in result.prompt


def test_generate_hooks_for_topic_saves_hooks() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, future=True)
    session = session_factory()
    topic = Topic(
        title="A startup failed because of one software bug",
        summary="A business mistake explained safely.",
        category="business_case",
        target_markets="global",
    )
    session.add(topic)
    session.commit()
    session.refresh(topic)

    result = generate_hooks_for_topic(
        session,
        topic,
        language="es",
        market="global",
        provider_name="manual",
        save=True,
    )

    assert len(result.saved_hook_ids) == 25
    saved = session.get(Hook, result.saved_hook_ids[0])
    assert saved is not None
    assert saved.hook_type in {item.value for item in HookType}
    notes = json.loads(saved.notes)
    assert 0 <= notes["total_score"] <= 100

    session.close()
