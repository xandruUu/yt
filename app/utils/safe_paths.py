from __future__ import annotations

from pathlib import Path

DANGEROUS_EXTENSIONS = {
    ".bat",
    ".cmd",
    ".com",
    ".cpl",
    ".dll",
    ".exe",
    ".js",
    ".msi",
    ".ps1",
    ".scr",
    ".sh",
    ".vbs",
}


def safe_join(base_dir: str | Path, *parts: str | Path) -> Path:
    base = Path(base_dir).resolve()
    target = base.joinpath(*parts).resolve()
    try:
        target.relative_to(base)
    except ValueError as exc:
        raise ValueError(f"Path escapes allowed directory: {target}") from exc
    return target


def reject_dangerous_extension(path: str | Path) -> None:
    suffix = Path(path).suffix.lower()
    if suffix in DANGEROUS_EXTENSIONS:
        raise ValueError(f"Dangerous file extension rejected: {suffix}")


def ensure_allowed_extension(path: str | Path, allowed_extensions: set[str]) -> None:
    reject_dangerous_extension(path)
    suffix = Path(path).suffix.lower()
    normalized = {extension.lower() for extension in allowed_extensions}
    if suffix not in normalized:
        allowed = ", ".join(sorted(normalized))
        raise ValueError(f"Extension {suffix!r} is not allowed. Expected one of: {allowed}")


def ensure_no_overwrite(path: str | Path, overwrite: bool = False) -> None:
    target = Path(path)
    if target.exists() and not overwrite:
        raise FileExistsError(f"Refusing to overwrite existing file: {target}")

