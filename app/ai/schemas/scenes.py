from __future__ import annotations

from pydantic import BaseModel, Field


class SceneCandidatePayload(BaseModel):
    option_code: str
    duration_seconds: float = Field(default=8.0, ge=1.0, le=15.0)
    voiceover_segment: str = ""
    visual_description: str
    character_action: str = ""
    camera_movement: str = ""
    setting: str = ""
    continuity_in: str = ""
    continuity_out: str = ""
    compatible_next_states: list[str] = Field(default_factory=list)
    required_character_cells: list[str] = Field(default_factory=list)
    notes: str = ""


class SceneSlotPayload(BaseModel):
    slot_number: int
    slot_type: str
    target_start_second: float
    target_end_second: float
    candidates: list[SceneCandidatePayload]


class ScenePlannerResponse(BaseModel):
    scene_slots: list[SceneSlotPayload]

