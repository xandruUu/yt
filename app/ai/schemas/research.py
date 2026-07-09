from __future__ import annotations

from pydantic import BaseModel, Field


class ResearchIdeaPayload(BaseModel):
    title: str
    short_description: str = ""
    viral_angle: str = ""
    why_now: str = ""
    visual_potential: str = ""
    estimated_duration_seconds: int = Field(default=60, ge=30, le=90)
    source_item_ids: list[int] = Field(default_factory=list)
    risk_level: str = "low"
    risk_notes: str = ""


class ResearchIdeasResponse(BaseModel):
    ideas: list[ResearchIdeaPayload]

