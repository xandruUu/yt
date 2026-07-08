from __future__ import annotations

import unittest

from app.core.scoring import calculate_topic_score, score_band


class TopicScoringTests(unittest.TestCase):
    def test_calculates_normalized_score(self) -> None:
        score = calculate_topic_score(10, 10, 10, 10, 10, 0, 0)
        self.assertEqual(score, 100.0)

    def test_high_risk_reduces_score(self) -> None:
        low_risk = calculate_topic_score(8, 8, 8, 8, 8, 0, 0)
        high_risk = calculate_topic_score(8, 8, 8, 8, 8, 10, 10)
        self.assertLess(high_risk, low_risk)

    def test_scores_out_of_range_fail(self) -> None:
        with self.assertRaises(ValueError):
            calculate_topic_score(11, 5, 5, 5, 5, 0, 0)

    def test_score_band(self) -> None:
        self.assertEqual(score_band(85), "high_priority")
        self.assertEqual(score_band(65), "interesting_test")
        self.assertEqual(score_band(45), "hook_dependent")
        self.assertEqual(score_band(20), "discard_or_archive")


if __name__ == "__main__":
    unittest.main()

