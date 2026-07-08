from __future__ import annotations

import importlib

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.enums import WizardStep
from app.db.models import Base, Script, Topic


def test_idea_selection_cannot_advance_without_selected_idea(monkeypatch) -> None:
    wizard_page = importlib.import_module("app.ui.pages.00_wizard")
    monkeypatch.setattr(wizard_page.st, "session_state", {})

    assert wizard_page._can_advance(WizardStep.RESEARCH)
    assert not wizard_page._can_advance(WizardStep.IDEA_SELECTION)


def test_idea_selection_can_advance_with_generated_idea(monkeypatch) -> None:
    wizard_page = importlib.import_module("app.ui.pages.00_wizard")
    monkeypatch.setattr(
        wizard_page.st,
        "session_state",
        {wizard_page.SESSION_SELECTED_GENERATED_IDEA_KEY: 42},
    )

    assert wizard_page._can_advance(WizardStep.IDEA_SELECTION)


def test_idea_selection_can_advance_with_topic(monkeypatch) -> None:
    wizard_page = importlib.import_module("app.ui.pages.00_wizard")
    monkeypatch.setattr(
        wizard_page.st,
        "session_state",
        {wizard_page.SESSION_SELECTED_TOPIC_KEY: 7},
    )

    assert wizard_page._can_advance(WizardStep.IDEA_SELECTION)


def test_hook_selection_cannot_advance_without_selected_hook(monkeypatch) -> None:
    wizard_page = importlib.import_module("app.ui.pages.00_wizard")
    monkeypatch.setattr(wizard_page.st, "session_state", {})

    assert not wizard_page._can_advance(WizardStep.HOOK_SELECTION)


def test_hook_selection_can_advance_with_selected_hook(monkeypatch) -> None:
    wizard_page = importlib.import_module("app.ui.pages.00_wizard")
    monkeypatch.setattr(
        wizard_page.st,
        "session_state",
        {wizard_page.SESSION_SELECTED_HOOK_KEY: 99},
    )

    assert wizard_page._can_advance(WizardStep.HOOK_SELECTION)


def test_title_selection_requires_selected_title(monkeypatch) -> None:
    wizard_page = importlib.import_module("app.ui.pages.00_wizard")
    monkeypatch.setattr(wizard_page.st, "session_state", {})

    assert not wizard_page._can_advance(WizardStep.TITLE_SELECTION)

    monkeypatch.setattr(
        wizard_page.st,
        "session_state",
        {wizard_page.SESSION_SELECTED_TITLE_KEY: 12},
    )
    assert wizard_page._can_advance(WizardStep.TITLE_SELECTION)


def test_script_generation_requires_approved_script(monkeypatch) -> None:
    wizard_page = importlib.import_module("app.ui.pages.00_wizard")

    class SessionContext:
        def __enter__(self):
            return session

        def __exit__(self, exc_type, exc, tb):
            return False

    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, future=True)()
    topic = Topic(title="Idea", summary="Resumen")
    session.add(topic)
    session.commit()
    session.refresh(topic)
    script = Script(topic_id=topic.id, language="es", script_text="Linea", status="needs_review")
    session.add(script)
    session.commit()
    session.refresh(script)
    monkeypatch.setattr(wizard_page, "new_session", lambda: SessionContext())
    monkeypatch.setattr(
        wizard_page.st,
        "session_state",
        {wizard_page.SESSION_SELECTED_SCRIPT_KEY: script.id},
    )

    assert not wizard_page._can_advance(WizardStep.SCRIPT_GENERATION)

    script.status = "approved"
    session.commit()
    assert wizard_page._can_advance(WizardStep.SCRIPT_GENERATION)

    session.close()
