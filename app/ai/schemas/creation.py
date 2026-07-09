from __future__ import annotations

from pydantic import BaseModel, Field


class DeepIdeaPayload(BaseModel):
    title: str
    detailed_description: str = ""
    specific_angle: str = ""
    why_it_can_go_viral: str = ""
    possible_hook: str = ""
    facts_to_verify: list[str] = Field(default_factory=list)
    visual_opportunities: list[str] = Field(default_factory=list)
    risk_level: str = "low"
    risk_notes: str = ""


class DeepResearchResponse(BaseModel):
    deep_ideas: list[DeepIdeaPayload]

