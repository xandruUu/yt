from __future__ import annotations

import json

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base, GeneratedTitle, Hook, Topic
from app.services.metadata_generation_service import generate_heuristic_metadata, generate_metadata


def test_heuristic_metadata_has_description_and_short_hashtag() -> None:
    metadata = generate_heuristic_metadata(
        idea_title="QR codes still work when damaged",
        idea_summary="Error correction explained",
        hook_text="La razon oculta detras de los QR",
        title="Como funcionan los QR danados",
        language="es",
        market="spain_latam",
    )

    assert metadata.description
    assert "#shorts" in [tag.lower() for tag in metadata.hashtags]
    assert len(metadata.hashtags) <= 5
    assert not metadata.made_for_kids_recommendation


def test_generate_metadata_persists_suggestion() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, future=True)()
    topic = Topic(title="QR codes still work when damaged", summary="Error correction explained")
    session.add(topic)
    session.commit()
    session.refresh(topic)
    hook = Hook(topic_id=topic.id, language="es", text="La razon oculta detras de los QR")
    session.add(hook)
    session.commit()
    session.refresh(hook)
    title = GeneratedTitle(topic_id=topic.id, hook_id=hook.id, language="es", market="global", title="Como funcionan los QR danados")
    session.add(title)
    session.commit()
    session.refresh(title)

    result = generate_metadata(
        session,
        generated_idea_id=None,
        topic_id=topic.id,
        hook_id=hook.id,
        title_id=title.id,
        script_id=None,
        language="es",
        market="global",
    )

    assert result.metadata.id
    assert result.metadata.description
    hashtags = json.loads(result.metadata.hashtags_json)
    assert "#shorts" in [tag.lower() for tag in hashtags]

    session.close()
