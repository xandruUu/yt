from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PicsartProcessingInstruction:
    scene_order: int | None
    input_path: str | None
    operation: str
    output_name: str
    notes: str
