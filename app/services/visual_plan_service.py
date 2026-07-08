from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.core.enums import ScriptStatus, VisualPlanStatus
from app.db import models
from app.db.repositories import add_and_commit, create_visual_plan

TEMPLATE_BY_CATEGORY = {
    "ai_tools": "tech_dark",
    "tech_explained": "tech_dark",
    "business_case": "documentary_alert",
    "science_explained": "minimal_educational",
    "engineering": "minimal_educational",
    "history_explained": "documentary_alert",
    "mystery_explained": "documentary_alert",
}


def generate_visual_plan(
    session: Session,
    *,
    script_id: int,
    template_name: str | None = None,
    wizard_session_id: int | None = None,
) -> models.VisualPlan:
    script = _get_approved_script(session, script_id)
    chosen_template = template_name or TEMPLATE_BY_CATEGORY.get(script.topic.category, "clean_text_focus")
    scenes = [_scene_from_line(script, line) for line in script.lines]
    if not scenes:
        raise ValueError("El guion no tiene lineas para plan visual.")
    return create_visual_plan(
        session,
        script_id=script.id,
        wizard_session_id=wizard_session_id,
        template_name=chosen_template,
        global_style=_global_style(chosen_template),
        background_style=_background_style(chosen_template),
        caption_style="large_high_contrast",
        scenes_json=json.dumps(scenes, ensure_ascii=False),
        status=VisualPlanStatus.GENERATED.value,
    )


def approve_visual_plan(session: Session, visual_plan_id: int) -> models.VisualPlan:
    plan = _get_visual_plan(session, visual_plan_id)
    if not plan.scenes_json or plan.scenes_json == "[]":
        raise ValueError("No se puede aprobar un plan visual sin escenas.")
    plan.status = VisualPlanStatus.APPROVED.value
    return add_and_commit(session, plan)


def visual_plan_scenes(plan: models.VisualPlan) -> list[dict[str, Any]]:
    value = json.loads(plan.scenes_json or "[]")
    return value if isinstance(value, list) else []


def _get_approved_script(session: Session, script_id: int) -> models.Script:
    script = session.get(models.Script, script_id)
    if script is None:
        raise ValueError(f"Script not found: {script_id}")
    if script.status != ScriptStatus.APPROVED.value:
        raise ValueError("El guion debe estar aprobado antes de generar el plan visual.")
    return script


def _get_visual_plan(session: Session, visual_plan_id: int) -> models.VisualPlan:
    plan = session.get(models.VisualPlan, visual_plan_id)
    if plan is None:
        raise ValueError(f"Visual plan not found: {visual_plan_id}")
    return plan


def _scene_from_line(script: models.Script, line: models.ScriptLine) -> dict[str, object]:
    text = line.subtitle_text or line.text
    visual_type = _visual_type_for_line(script, line)
    return {
        "line_id": line.id,
        "script_line_id": line.id,
        "order": line.line_order,
        "duration_seconds": line.duration_seconds,
        "text": text,
        "visual_type": visual_type,
        "visual_prompt": line.visual_suggestion or _fallback_visual_prompt(script, text),
        "asset_id": None,
        "external_asset_id": None,
        "provider_name": None,
        "prompt_pack_scene_id": f"scene_{line.line_order:02}",
        "fallback_visual_type": visual_type,
        "animation": _animation_for_visual_type(visual_type),
        "emphasis_words": _emphasis_words(text),
    }


def _visual_type_for_line(script: models.Script, line: models.ScriptLine) -> str:
    text = f"{line.text} {line.visual_suggestion or ''}".lower()
    if "codigo" in text or "code" in text or script.topic.category in {"ai_tools", "tech_explained"}:
        return "code_or_ui_screen"
    if "dato" in text or "%" in text or "numero" in text:
        return "data_callout"
    if "historia" in text or "caso" in text:
        return "documentary_card"
    return "text_focus"


def _fallback_visual_prompt(script: models.Script, text: str) -> str:
    return f"Vertical short scene about {script.topic.title}: {text[:120]}"


def _animation_for_visual_type(visual_type: str) -> str:
    return {
        "code_or_ui_screen": "slow_zoom_in",
        "data_callout": "number_pop",
        "documentary_card": "subtle_push",
        "text_focus": "kinetic_text",
    }.get(visual_type, "subtle_push")


def _emphasis_words(text: str) -> list[str]:
    words = [word.strip(".,;:!?()[]").lower() for word in text.split()]
    useful = [word for word in words if len(word) >= 5]
    return useful[:3]


def _global_style(template_name: str) -> str:
    return {
        "tech_dark": "Oscuro, tecnico, alto contraste y ritmo rapido.",
        "documentary_alert": "Documental oscuro, tension moderada y alertas visuales.",
        "minimal_educational": "Claro, limpio, didactico y facil de leer.",
        "clean_text_focus": "Texto grande, fondo limpio y subtitulos protagonistas.",
    }.get(template_name, "Texto vertical limpio y legible.")


def _background_style(template_name: str) -> str:
    return {
        "tech_dark": "dark_tech",
        "documentary_alert": "dark_documentary",
        "minimal_educational": "light_educational",
        "clean_text_focus": "neutral_clean",
    }.get(template_name, "neutral_clean")
