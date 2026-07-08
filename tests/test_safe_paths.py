from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.utils.safe_paths import ensure_allowed_extension, ensure_no_overwrite, safe_join


class SafePathTests(unittest.TestCase):
    def test_rejects_path_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, self.assertRaises(ValueError):
            safe_join(temp_dir, "..", "outside.txt")

    def test_rejects_dangerous_extension(self) -> None:
        with self.assertRaises(ValueError):
            ensure_allowed_extension("payload.exe", {".png"})

    def test_allows_expected_extension(self) -> None:
        ensure_allowed_extension("image.png", {".png", ".jpg"})

    def test_does_not_overwrite_without_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "file.txt"
            path.write_text("x", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                ensure_no_overwrite(path)


if __name__ == "__main__":
    unittest.main()

