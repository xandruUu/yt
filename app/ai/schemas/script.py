from __future__ import annotations

from pydantic import BaseModel, Field


class ScriptBeatPayload(BaseModel):
    beat_number: int
    purpose: str
    start_second: float
    end_second: float
    text: str
    visual_intent: str = ""


class ScriptDraftPayload(BaseModel):
    language: str = "en"
    target_duration_seconds: int = Field(default=60, ge=30, le=90)
    estimated_words: int = 0
    tone: str = "energetic, curious, educational"
    voiceover_text: str
    beats: list[ScriptBeatPayload] = Field(default_factory=list)
    fact_check_notes: list[str] = Field(default_factory=list)
    risk_notes: list[str] = Field(default_factory=list)


class ScriptDraftResponse(BaseModel):
    script: ScriptDraftPayload

