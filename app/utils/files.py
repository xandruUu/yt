from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_text_file(path: Path, content: str, overwrite: bool = False) -> Path:
    if path.exists() and not overwrite:
        raise FileExistsError(f"Refusing to overwrite existing file: {path}")
    ensure_dir(path.parent)
    path.write_text(content, encoding="utf-8")
    return path


def write_json_file(path: Path, payload: dict[str, Any], overwrite: bool = False) -> Path:
    return write_text_file(
        path,
        json.dumps(payload, indent=2, ensure_ascii=False),
        overwrite=overwrite,
    )


def copy_file(source: Path, destination: Path, overwrite: bool = False) -> Path:
    if not source.exists():
        raise FileNotFoundError(source)
    if destination.exists() and not overwrite:
        raise FileExistsError(f"Refusing to overwrite existing file: {destination}")
    ensure_dir(destination.parent)
    shutil.copy2(source, destination)
    return destination

