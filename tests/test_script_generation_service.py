from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.enums import ScriptStatus
from app.db.models import Base, GeneratedTitle, Hook, Topic
from app.services.script_generation_service import (
    approve_script,
    generate_script,
    generate_script_payload,
    parse_generated_script_json,
)


def test_parse_generated_script_json_requires_lines() -> None:
    payload = parse_generated_script_json(
        '{"lines": [{"text": "Hook fuerte", "visual_suggestion": "Texto grande"}]}'
    )

    assert payload["lines"]


def test_generate_script_payload_fallback_has_lines_and_visuals() -> None:
    payload = generate_script_payload(
        idea_title="QR codes still work when damaged",
        idea_summary="Error correction explained",
        idea_angle="Explain the mechanism",
        hook_text="La razon oculta detras de los QR",
        title="Como funcionan los QR danados",
        language="es",
        market="global",
        category="tech_explained",
        format_type="documental_rapido",
        target_duration_seconds=40,
        tone="claro",
    )

    lines = payload["lines"]
    assert len(lines) >= 5
    assert all(line["visual_suggestion"] for line in lines)
    assert sum(float(line["duration_seconds"]) for line in lines) > 0


def test_generate_and_approve_script() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, future=True)()
    topic = Topic(title="QR codes still work when damaged", summary="Error correction explained", category="tech_explained")
    session.add(topic)
    session.commit()
    session.refresh(topic)
    hook = Hook(topic_id=topic.id, language="es", text="La razon oculta detras de los QR")
    session.add(hook)
    session.commit()
    session.refresh(hook)
    title = GeneratedTitle(topic_id=topic.id, hook_id=hook.id, language="es", market="global", title="Como funcionan los QR danados", selected=True)
    session.add(title)
    session.commit()
    session.refresh(title)

    result = generate_script(
        session,
        generated_idea_id=None,
        topic_id=topic.id,
        hook_id=hook.id,
        title_id=title.id,
        language="es",
        market="global",
        format_type="documental_rapido",
        target_duration_seconds=40,
        tone="claro",
    )
    approved = approve_script(session, result.script.id)

    assert result.script.lines
    assert result.script.estimated_duration_seconds > 0
    assert approved.status == ScriptStatus.APPROVED.value

    session.close()
