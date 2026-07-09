from __future__ import annotations

import unittest

from app.core.enums import WizardStep
from app.core.wizard import (
    WIZARD_STEPS,
    next_step,
    previous_step,
    wizard_progress,
    wizard_step_values,
)
from app.i18n.es import NAVIGATION, WIZARD_STEP_LABELS


class WizardTests(unittest.TestCase):
    def test_wizard_has_nero_storyboard_steps(self) -> None:
        self.assertEqual(len(WIZARD_STEPS), 18)
        self.assertEqual(WIZARD_STEPS[0].step, WizardStep.BASIC_DATA)
        self.assertEqual(WIZARD_STEPS[-1].step, WizardStep.EXPORT)
        self.assertEqual(wizard_step_values()[0], "basic_data")
        self.assertIn("storyboard", wizard_step_values())
        self.assertIn("scene_mapping", wizard_step_values())

    def test_progress_and_navigation(self) -> None:
        self.assertAlmostEqual(wizard_progress(WizardStep.BASIC_DATA), 1 / 18)
        self.assertEqual(next_step(WizardStep.BASIC_DATA), WizardStep.RESEARCH)
        self.assertIsNone(previous_step(WizardStep.BASIC_DATA))
        self.assertIsNone(next_step(WizardStep.EXPORT))

    def test_spanish_navigation_contains_guided_flow(self) -> None:
        labels = [label for label, _module in NAVIGATION]
        self.assertEqual(labels[0], "Investigacion")
        self.assertIn("Crear Short paso a paso", labels)
        self.assertIn("Creacion", labels)
        self.assertIn("Produccion", labels)
        self.assertIn("Personajes", labels)
        self.assertIn("Storyboard Nero", labels)
        self.assertEqual(WIZARD_STEP_LABELS[WizardStep.RESEARCH], "Investigar")


if __name__ == "__main__":
    unittest.main()
