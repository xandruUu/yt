from __future__ import annotations

from collections.abc import Mapping

from app.core.enums import RenderStatus, ScriptStatus, VideoWorkflowStatus

ALLOWED_TRANSITIONS: dict[VideoWorkflowStatus, set[VideoWorkflowStatus]] = {
    VideoWorkflowStatus.IDEA: {
        VideoWorkflowStatus.HOOKS_PENDING,
        VideoWorkflowStatus.REJECTED,
        VideoWorkflowStatus.ARCHIVED,
    },
    VideoWorkflowStatus.HOOKS_PENDING: {VideoWorkflowStatus.HOOKS_GENERATED},
    VideoWorkflowStatus.HOOKS_GENERATED: {VideoWorkflowStatus.HOOK_SELECTED},
    VideoWorkflowStatus.HOOK_SELECTED: {VideoWorkflowStatus.SCRIPT_PENDING},
    VideoWorkflowStatus.SCRIPT_PENDING: {VideoWorkflowStatus.SCRIPT_GENERATED},
    VideoWorkflowStatus.SCRIPT_GENERATED: {VideoWorkflowStatus.SCRIPT_REVIEW_PENDING},
    VideoWorkflowStatus.SCRIPT_REVIEW_PENDING: {
        VideoWorkflowStatus.SCRIPT_APPROVED,
        VideoWorkflowStatus.REJECTED,
    },
    VideoWorkflowStatus.SCRIPT_APPROVED: {VideoWorkflowStatus.ASSETS_PENDING},
    VideoWorkflowStatus.ASSETS_PENDING: {VideoWorkflowStatus.RENDER_PENDING},
    VideoWorkflowStatus.RENDER_PENDING: {VideoWorkflowStatus.RENDERED},
    VideoWorkflowStatus.RENDERED: {VideoWorkflowStatus.REVIEW_PENDING},
    VideoWorkflowStatus.REVIEW_PENDING: {
        VideoWorkflowStatus.APPROVED,
        VideoWorkflowStatus.REJECTED,
    },
    VideoWorkflowStatus.APPROVED: {VideoWorkflowStatus.EXPORTED},
    VideoWorkflowStatus.EXPORTED: {VideoWorkflowStatus.MANUALLY_PUBLISHED},
}


def as_workflow_status(value: str | VideoWorkflowStatus) -> VideoWorkflowStatus:
    if isinstance(value, VideoWorkflowStatus):
        return value
    return VideoWorkflowStatus(value)


def can_transition(
    current: str | VideoWorkflowStatus,
    target: str | VideoWorkflowStatus,
) -> bool:
    current_status = as_workflow_status(current)
    target_status = as_workflow_status(target)
    return target_status in ALLOWED_TRANSITIONS.get(current_status, set())


def can_render_script(script_status: str | ScriptStatus) -> bool:
    status = script_status if isinstance(script_status, ScriptStatus) else ScriptStatus(script_status)
    return status == ScriptStatus.APPROVED


def can_export_review(checklist: Mapping[str, object] | None) -> bool:
    if not checklist:
        return False
    return bool(checklist.get("approved"))


def can_mark_published(render_status: str | RenderStatus, has_export_package: bool) -> bool:
    status = render_status if isinstance(render_status, RenderStatus) else RenderStatus(render_status)
    return status == RenderStatus.EXPORTED and has_export_package


def require_transition(current: str, target: str) -> None:
    if not can_transition(current, target):
        raise ValueError(f"Cannot transition from {current!r} to {target!r}.")

