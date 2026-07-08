from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HiggsfieldScenePrompt:
    order: int
    narration: str
    duration_seconds: float
    visual_prompt: str
    camera_motion: str
    style: str
