from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from typing import Any

from app.config.settings import get_settings

JsonData = dict[str, Any] | list[Any]


@dataclass(frozen=True)
class HiggsfieldStatus:
    available: bool
    mode: str
    detail: str
    cli_path: str | None = None


@dataclass(frozen=True)
class HiggsfieldCliResult:
    ok: bool
    command: list[str]
    stdout: str
    stderr: str
    returncode: int
    data: JsonData | None
    error: str | None = None


@dataclass(frozen=True)
class HiggsfieldCostResult:
    credits: float
    raw: dict[str, Any]
    cli_result: HiggsfieldCliResult


@dataclass(frozen=True)
class HiggsfieldCreateResult:
    external_job_id: str | None
    raw: dict[str, Any]
    cli_result: HiggsfieldCliResult
    output_url: str | None = None


@dataclass(frozen=True)
class HiggsfieldJobResult:
    external_job_id: str | None
    status: str | None
    raw: dict[str, Any]
    cli_result: HiggsfieldCliResult
    output_url: str | None = None
    output_urls: list[str] | None = None


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


def estimate_generation_cost(
    *,
    prompt: str,
    model_name: str | None = None,
    aspect_ratio: str | None = None,
    duration_seconds: int | float | None = None,
    generate_audio: bool = False,
    timeout_seconds: int | None = None,
) -> HiggsfieldCostResult:
    settings = get_settings()
    command = _generation_command(
        "cost",
        prompt=prompt,
        model_name=model_name,
        aspect_ratio=aspect_ratio,
        duration_seconds=duration_seconds,
        generate_audio=generate_audio,
    )
    result = _run_cli(command, timeout_seconds or settings.higgsfield_job_timeout_seconds)
    if not result.ok:
        raise RuntimeError(result.error or "Higgsfield cost command failed.")
    raw = _ensure_dict(result.data)
    credits = _extract_credits(raw)
    if credits is None:
        raise ValueError("No se pudo extraer el coste en creditos de Higgsfield.")
    return HiggsfieldCostResult(credits=credits, raw=raw, cli_result=result)


def create_generation_job(
    *,
    prompt: str,
    confirmed_credits: bool,
    model_name: str | None = None,
    aspect_ratio: str | None = None,
    duration_seconds: int | float | None = None,
    generate_audio: bool = False,
    real_generation_enabled: bool | None = None,
    timeout_seconds: int | None = None,
) -> HiggsfieldCreateResult:
    settings = get_settings()
    enabled = (
        settings.higgsfield_real_generation_enabled
        if real_generation_enabled is None
        else real_generation_enabled
    )
    if not enabled:
        raise ValueError("La generacion real de Higgsfield esta desactivada.")
    if not confirmed_credits:
        raise ValueError("Falta confirmacion explicita de gasto de creditos.")
    command = _generation_command(
        "create",
        prompt=prompt,
        model_name=model_name,
        aspect_ratio=aspect_ratio,
        duration_seconds=duration_seconds,
        generate_audio=generate_audio,
    )
    result = _run_cli(command, timeout_seconds or settings.higgsfield_job_timeout_seconds)
    if not result.ok:
        raise RuntimeError(result.error or "Higgsfield create command failed.")
    raw = _ensure_dict(result.data)
    return HiggsfieldCreateResult(
        external_job_id=extract_job_id(raw),
        raw=raw,
        cli_result=result,
        output_url=extract_primary_output_url(raw),
    )


def wait_generation_job(
    external_job_id: str,
    *,
    timeout: str | None = None,
    interval: str | None = None,
    timeout_seconds: int | None = None,
) -> HiggsfieldJobResult:
    settings = get_settings()
    command = [
        settings.higgsfield_cli_bin,
        "generate",
        "wait",
        external_job_id,
        "--timeout",
        timeout or settings.higgsfield_wait_timeout,
        "--interval",
        interval or settings.higgsfield_wait_interval,
        "--json",
    ]
    result = _run_cli(command, timeout_seconds or settings.higgsfield_job_timeout_seconds)
    if not result.ok:
        raise RuntimeError(result.error or "Higgsfield wait command failed.")
    raw = _ensure_dict(result.data)
    output_urls = extract_output_urls(raw)
    return HiggsfieldJobResult(
        external_job_id=extract_job_id(raw) or external_job_id,
        status=extract_status(raw),
        raw=raw,
        cli_result=result,
        output_url=output_urls[0] if output_urls else None,
        output_urls=output_urls,
    )


def get_generation_job(
    external_job_id: str,
    *,
    timeout_seconds: int | None = None,
) -> HiggsfieldJobResult:
    settings = get_settings()
    command = [
        settings.higgsfield_cli_bin,
        "generate",
        "get",
        external_job_id,
        "--json",
    ]
    result = _run_cli(command, timeout_seconds or settings.higgsfield_job_timeout_seconds)
    if not result.ok:
        raise RuntimeError(result.error or "Higgsfield get command failed.")
    raw = _ensure_dict(result.data)
    output_urls = extract_output_urls(raw)
    return HiggsfieldJobResult(
        external_job_id=extract_job_id(raw) or external_job_id,
        status=extract_status(raw),
        raw=raw,
        cli_result=result,
        output_url=output_urls[0] if output_urls else None,
        output_urls=output_urls,
    )


def list_generation_jobs(
    *,
    video: bool = True,
    size: int = 50,
    timeout_seconds: int | None = None,
) -> HiggsfieldCliResult:
    settings = get_settings()
    command = [settings.higgsfield_cli_bin, "generate", "list"]
    if video:
        command.append("--video")
    command.extend(["--size", str(size), "--json"])
    return _run_cli(command, timeout_seconds or settings.higgsfield_job_timeout_seconds)


def extract_job_id(data: JsonData | None) -> str | None:
    return _first_string_at_keys(
        data,
        (
            "id",
            "job_id",
            "jobId",
            "uuid",
            "generation_id",
            "generationId",
        ),
    )


def extract_status(data: JsonData | None) -> str | None:
    return _first_string_at_keys(data, ("status", "state"))


def extract_output_urls(data: JsonData | None) -> list[str]:
    urls: list[str] = []
    _collect_output_urls(data, urls)
    return list(dict.fromkeys(urls))


def extract_primary_output_url(data: JsonData | None) -> str | None:
    urls = extract_output_urls(data)
    return urls[0] if urls else None


def _generation_command(
    operation: str,
    *,
    prompt: str,
    model_name: str | None,
    aspect_ratio: str | None,
    duration_seconds: int | float | None,
    generate_audio: bool,
) -> list[str]:
    settings = get_settings()
    return [
        settings.higgsfield_cli_bin,
        "generate",
        operation,
        model_name or settings.higgsfield_default_model,
        "--prompt",
        prompt,
        "--aspect-ratio",
        aspect_ratio or settings.higgsfield_default_aspect_ratio,
        "--duration",
        str(int(duration_seconds or settings.higgsfield_default_test_duration_seconds)),
        "--generate-audio",
        _bool_cli(generate_audio),
        "--json",
    ]


def _run_cli(command: list[str], timeout_seconds: int) -> HiggsfieldCliResult:
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            check=False,
        )
    except FileNotFoundError as exc:
        return HiggsfieldCliResult(
            ok=False,
            command=command,
            stdout="",
            stderr=str(exc),
            returncode=127,
            data=None,
            error=f"CLI no encontrado: {command[0]}",
        )
    except subprocess.TimeoutExpired as exc:
        return HiggsfieldCliResult(
            ok=False,
            command=command,
            stdout=exc.stdout or "",
            stderr=exc.stderr or "",
            returncode=124,
            data=None,
            error="Timeout ejecutando Higgsfield CLI.",
        )

    data = _parse_json_fallback(completed.stdout)
    error = completed.stderr.strip() or None
    return HiggsfieldCliResult(
        ok=completed.returncode == 0,
        command=command,
        stdout=completed.stdout,
        stderr=completed.stderr,
        returncode=completed.returncode,
        data=data,
        error=error,
    )


def _parse_json_fallback(text: str) -> JsonData | None:
    cleaned = text.strip()
    if not cleaned:
        return None
    for candidate in (cleaned, _slice_json_candidate(cleaned)):
        if not candidate:
            continue
        try:
            value = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict | list):
            return value
    return None


def _slice_json_candidate(text: str) -> str | None:
    object_start = text.find("{")
    object_end = text.rfind("}")
    array_start = text.find("[")
    array_end = text.rfind("]")
    candidates: list[tuple[int, str]] = []
    if object_start >= 0 and object_end > object_start:
        candidates.append((object_start, text[object_start : object_end + 1]))
    if array_start >= 0 and array_end > array_start:
        candidates.append((array_start, text[array_start : array_end + 1]))
    if not candidates:
        return None
    return sorted(candidates, key=lambda item: item[0])[0][1]


def _ensure_dict(data: JsonData | None) -> dict[str, Any]:
    if isinstance(data, dict):
        return data
    if isinstance(data, list):
        return {"items": data}
    return {}


def _extract_credits(data: JsonData | None) -> float | None:
    direct = _first_number_at_keys(data, ("credits", "cost_credits", "costCredits"))
    if direct is not None:
        return direct
    if isinstance(data, dict):
        cost = data.get("cost")
        if isinstance(cost, int | float | str):
            try:
                return float(cost)
            except ValueError:
                return None
    return None


def _first_string_at_keys(data: Any, keys: tuple[str, ...]) -> str | None:
    if isinstance(data, dict):
        for key in keys:
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
            if isinstance(value, int):
                return str(value)
        nested = data.get("data")
        found = _first_string_at_keys(nested, keys)
        if found:
            return found
        for value in data.values():
            found = _first_string_at_keys(value, keys)
            if found:
                return found
    elif isinstance(data, list):
        for item in data:
            found = _first_string_at_keys(item, keys)
            if found:
                return found
    return None


def _first_number_at_keys(data: Any, keys: tuple[str, ...]) -> float | None:
    if isinstance(data, dict):
        for key in keys:
            value = data.get(key)
            if isinstance(value, int | float):
                return float(value)
            if isinstance(value, str):
                try:
                    return float(value)
                except ValueError:
                    pass
        for value in data.values():
            found = _first_number_at_keys(value, keys)
            if found is not None:
                return found
    elif isinstance(data, list):
        for item in data:
            found = _first_number_at_keys(item, keys)
            if found is not None:
                return found
    return None


def _collect_output_urls(data: Any, urls: list[str]) -> None:
    output_keys = {
        "url",
        "output_url",
        "outputUrl",
        "result_url",
        "resultUrl",
        "video_url",
        "videoUrl",
        "download_url",
        "downloadUrl",
    }
    nested_keys = {"outputs", "assets", "results", "data"}
    if isinstance(data, dict):
        for key, value in data.items():
            if key in output_keys and isinstance(value, str) and _looks_like_url(value):
                urls.append(value)
            if key in nested_keys or isinstance(value, dict | list):
                _collect_output_urls(value, urls)
    elif isinstance(data, list):
        for item in data:
            _collect_output_urls(item, urls)


def _looks_like_url(value: str) -> bool:
    return value.startswith(("http://", "https://"))


def _bool_cli(value: bool) -> str:
    return "true" if value else "false"
