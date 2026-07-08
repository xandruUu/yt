from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base, Hook, Topic
from app.services.title_generation_service import (
    TITLE_TYPES,
    generate_heuristic_title_candidates,
    generate_titles_for_hook,
    select_title,
)


def test_heuristic_titles_generate_25_candidates() -> None:
    titles = generate_heuristic_title_candidates(
        concept="QR codes still work when damaged",
        selected_hook="La razon oculta por la que los QR funcionan",
        language="es",
        category="tech_explained",
    )

    assert len(titles) == 25
    assert {title.title_type for title in titles} == set(TITLE_TYPES)
    assert all(title.title.strip() for title in titles)
    assert all(0 <= title.total_score <= 100 for title in titles)
    assert all(0 <= title.clickbait_risk <= 10 for title in titles)


def test_generate_titles_for_hook_persists_and_selects() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, future=True)()
    topic = Topic(title="AI agents automate repetitive work", summary="Automation explained", category="ai_tools")
    session.add(topic)
    session.commit()
    session.refresh(topic)
    hook = Hook(topic_id=topic.id, language="es", text="La razon oculta detras de los agentes IA")
    session.add(hook)
    session.commit()
    session.refresh(hook)

    result = generate_titles_for_hook(
        session,
        generated_idea_id=None,
        topic_id=topic.id,
        hook_id=hook.id,
        language="es",
        market="global",
        provider_name="manual",
    )
    selected = select_title(session, result.saved_title_ids[0])

    assert len(result.saved_title_ids) == 25
    assert selected.selected
    assert selected.status == "selected"
    assert selected.length_chars == len(selected.title)

    session.close()
