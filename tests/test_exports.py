from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.core.constants import EXPORT_FILE_NAMES
from app.core.validation import REQUIRED_REVIEW_FLAGS
from app.services.export_service import create_export_package


class ExportTests(unittest.TestCase):
    def test_creates_expected_export_package(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            video = root / "source.mp4"
            video.write_bytes(b"fake mp4")
            checklist = {flag: True for flag in REQUIRED_REVIEW_FLAGS}
            checklist["approved"] = True

            package = create_export_package(
                output_dir=root / "outputs",
                topic_title="Tiny bug that cost millions",
                language="en",
                video_path=video,
                title="A Tiny Bug Cost Millions",
                description="Short description.",
                hashtags=["#shorts", "#tech"],
                script_text="Line one.\nLine two.",
                metadata={"category": "tech_explained"},
                review_checklist=checklist,
                license_manifest={"music": [], "assets": []},
            )

            export_folder = Path(package["export_folder"])
            for file_name in EXPORT_FILE_NAMES:
                self.assertTrue((export_folder / file_name).exists(), file_name)

            metadata = json.loads((export_folder / "metadata.json").read_text(encoding="utf-8"))
            self.assertEqual(metadata["language"], "en")
            self.assertEqual(metadata["hashtags"], ["#shorts", "#tech"])

    def test_blocks_unapproved_export(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            video = root / "source.mp4"
            video.write_bytes(b"fake mp4")
            with self.assertRaises(ValueError):
                create_export_package(
                    output_dir=root / "outputs",
                    topic_title="Blocked",
                    language="en",
                    video_path=video,
                    title="Title",
                    description="Description",
                    hashtags=[],
                    script_text="Script",
                    metadata={},
                    review_checklist={"approved": False},
                    license_manifest={"music": [], "assets": []},
                )


if __name__ == "__main__":
    unittest.main()

