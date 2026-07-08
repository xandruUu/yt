from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Channel
from app.db.repositories import add_and_commit
from app.services.character_service import DAILY_BRAIN_BREAK_CHANNEL, seed_nero_character_system

DEFAULT_CHANNELS = (
    {
        "name": DAILY_BRAIN_BREAK_CHANNEL,
        "language": "en",
        "market": "global",
        "youtube_handle": "@dailybrainbreak",
        "description": "Nero explains weird facts, history, science, tech and internet stories in quick visual Shorts.",
    },
    {
        "name": "Tech Explained EN",
        "language": "en",
        "market": "global",
        "youtube_handle": "@example_en",
        "description": "English technology and science explainers.",
    },
    {
        "name": "Tecnologia Explicada ES",
        "language": "es",
        "market": "spain_latam",
        "youtube_handle": "@example_es",
        "description": "Spanish neutral technology explainers.",
    },
    {
        "name": "Tech Explained Hinglish",
        "language": "hi_hinglish",
        "market": "india",
        "youtube_handle": "@example_hi",
        "description": "Urban India Hinglish explainers.",
    },
)


def seed_channels(session: Session) -> None:
    for payload in DEFAULT_CHANNELS:
        existing = session.scalar(select(Channel).where(Channel.name == payload["name"]))
        if existing is None:
            add_and_commit(session, Channel(**payload))


def seed_defaults(session: Session) -> None:
    seed_channels(session)
    seed_nero_character_system(session)
