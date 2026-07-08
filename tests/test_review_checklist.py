from __future__ import annotations

import unittest

from app.core.validation import REQUIRED_REVIEW_FLAGS
from app.services.review_service import (
    build_review_payload,
    checklist_can_export,
    checklist_missing_items,
)


class ReviewChecklistTests(unittest.TestCase):
    def test_complete_checklist_can_export(self) -> None:
        flags = {flag: True for flag in REQUIRED_REVIEW_FLAGS}
        payload = build_review_payload(**flags, approved=True)
        self.assertTrue(checklist_can_export(payload))
        self.assertEqual(checklist_missing_items(payload), [])

    def test_incomplete_checklist_cannot_export(self) -> None:
        flags = {flag: True for flag in REQUIRED_REVIEW_FLAGS}
        flags["music_license_ok"] = False
        payload = build_review_payload(**flags, approved=True)
        self.assertFalse(checklist_can_export(payload))
        self.assertIn("music_license_ok", checklist_missing_items(payload))


if __name__ == "__main__":
    unittest.main()

