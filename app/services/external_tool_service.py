from __future__ import annotations

from app.external_tools.registry import ExternalToolRegistry


def list_external_tool_statuses() -> list[dict[str, object]]:
    return ExternalToolRegistry().status_rows()
