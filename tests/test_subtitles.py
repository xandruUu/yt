from __future__ import annotations

import unittest

from app.services.subtitle_service import generate_srt, seconds_to_srt_timestamp


class SubtitleTests(unittest.TestCase):
    def test_generates_valid_srt(self) -> None:
        srt = generate_srt(
            [
                {"text": "This tiny mistake cost millions.", "duration_seconds": 2.0},
                {"text": "It was not a hacker.", "duration_seconds": 2.5},
            ]
        )
        self.assertIn("1\n00:00:00,000 --> 00:00:02,000", srt)
        self.assertIn("2\n00:00:02,000 --> 00:00:04,500", srt)

    def test_respects_line_order(self) -> None:
        srt = generate_srt(
            [
                {"text": "First.", "duration_seconds": 1.0},
                {"text": "Second.", "duration_seconds": 1.0},
            ]
        )
        self.assertLess(srt.index("First."), srt.index("Second."))

    def test_no_negative_timestamps(self) -> None:
        with self.assertRaises(ValueError):
            seconds_to_srt_timestamp(-0.1)

    def test_rejects_non_positive_duration(self) -> None:
        with self.assertRaises(ValueError):
            generate_srt([{"text": "Bad.", "duration_seconds": 0}])


if __name__ == "__main__":
    unittest.main()

