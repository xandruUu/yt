from __future__ import annotations

import shutil
from dataclasses import dataclass

from app.config.settings import get_settings


@dataclass(frozen=True)
class HiggsfieldStatus:
    available: bool
    mode: str
    detail: str
    cli_path: str | None = None


class HiggsfieldClient:
    def check_status(self) -> HiggsfieldStatus:
        settings = get_settings()
        mode = settings.higgsfield_automation_mode
        if not settings.enable_higgsfield_automation or mode == "manual":
            return HiggsfieldStatus(
                available=False,
                mode="manual",
                detail="Automatizacion Higgsfield desactivada; usar fallback manual.",
            )
        if mode == "cli":
            cli_path = shutil.which(settings.higgsfield_cli_bin)
            if not cli_path:
                return HiggsfieldStatus(
                    available=False,
                    mode="cli",
                    detail=f"CLI no encontrado: {settings.higgsfield_cli_bin}",
                )
            return HiggsfieldStatus(
                available=True,
                mode="cli",
                detail="CLI Higgsfield detectado. La ejecucion requiere confirmacion humana.",
                cli_path=cli_path,
            )
        if mode == "mcp":
            return HiggsfieldStatus(
                available=settings.enable_higgsfield_mcp,
                mode="mcp",
                detail="Modo MCP configurado; requiere adaptador de agente.",
            )
        return HiggsfieldStatus(available=False, mode=mode, detail=f"Modo no soportado: {mode}")

