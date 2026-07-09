from __future__ import annotations

from pydantic import BaseModel, Field


class TitleOption(BaseModel):
    title: str
    score: int = Field(default=70, ge=0, le=100)
    reason: str = ""
    clickbait_risk: str = "low"


class HookOption(BaseModel):
    hook: str
    style: str = "curiosity"
    reason: str = ""


class DescriptionOption(BaseModel):
    description: str
    reason: str = ""


class HashtagSetOption(BaseModel):
    hashtags: list[str] = Field(default_factory=lambda: ["#shorts"])
    strategy: str = ""


class MetadataRecipeResponse(BaseModel):
    titles: list[TitleOption]
    hooks: list[HookOption]
    descriptions: list[DescriptionOption]
    hashtag_sets: list[HashtagSetOption]

