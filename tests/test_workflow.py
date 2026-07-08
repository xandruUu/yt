from __future__ import annotations

import unittest

from app.core.enums import RenderStatus, ScriptStatus, VideoWorkflowStatus
from app.core.workflow import (
    can_export_review,
    can_mark_published,
    can_render_script,
    can_transition,
)


class WorkflowTests(unittest.TestCase):
    def test_cannot_render_without_approved_script(self) -> None:
        self.assertFalse(can_render_script(ScriptStatus.NEEDS_REVIEW))
        self.assertTrue(can_render_script(ScriptStatus.APPROVED))

    def test_cannot_export_without_approved_checklist(self) -> None:
        self.assertFalse(can_export_review({"approved": False}))
        self.assertTrue(can_export_review({"approved": True}))

    def test_cannot_mark_published_without_export(self) -> None:
        self.assertFalse(can_mark_published(RenderStatus.APPROVED, has_export_package=True))
        self.assertFalse(can_mark_published(RenderStatus.EXPORTED, has_export_package=False))
        self.assertTrue(can_mark_published(RenderStatus.EXPORTED, has_export_package=True))

    def test_allowed_transition(self) -> None:
        self.assertTrue(can_transition(VideoWorkflowStatus.IDEA, VideoWorkflowStatus.HOOKS_PENDING))
        self.assertFalse(can_transition(VideoWorkflowStatus.IDEA, VideoWorkflowStatus.EXPORTED))


if __name__ == "__main__":
    unittest.main()

