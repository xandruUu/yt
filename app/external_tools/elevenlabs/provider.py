from __future__ import annotations

import base64
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.config.settings import get_settings
from app.external_tools.base import CostEstimate, ProviderStatus
from app.external_tools.elevenlabs.schemas import ElevenLabsSpeechResult
from app.utils.files import ensure_dir, write_json_file

HttpPost = Callable[[str, dict[str, str], bytes, int], tuple[int, bytes, str]]


class ElevenLabsProvider:
    name = "elevenlabs"
    provider_type = "api"
    requires_api_key = True
    can_cost_money = True
    api_base_url = "https://api.elevenlabs.io/v1"

    def __init__(self, http_post: HttpPost | None = None) -> None:
        self._http_post = http_post or _default_http_post

    def is_available(self) -> bool:
        settings = get_settings()
        enabled = settings.enable_external_tools and (
            settings.enable_elevenlabs or settings.enable_elevenlabs_tts
        )
        return enabled and bool(_api_key()) and bool(settings.elevenlabs_default_voice_id)

    def get_status(self) -> ProviderStatus:
        settings = get_settings()
        enabled = settings.enable_external_tools and (
            settings.enable_elevenlabs or settings.enable_elevenlabs_tts
        )
        has_key = bool(_api_key())
        has_voice = bool(settings.elevenlabs_default_voice_id)
        detail = "Disponible: ElevenLabs API configurada."
        if not enabled:
            detail = "Desactivado. Activa ENABLE_ELEVENLABS=true o ENABLE_ELEVENLABS_TTS=true."
        elif not has_key:
            detail = "Falta ELEVENLABS_API_KEY en .env."
        elif not has_voice:
            detail = "Falta ELEVENLABS_DEFAULT_VOICE_ID en .env."
        return ProviderStatus(
            name=self.name,
            provider_type=self.provider_type,
            configured=enabled and has_key and has_voice,
            available=enabled and has_key and has_voice,
            requires_api_key=True,
            can_cost_money=True,
            mode="api" if enabled else "no_disponible",
            detail=detail,
            metadata={
                "default_voice_id_configured": bool(settings.elevenlabs_default_voice_id),
                "default_voice_id_masked": _mask_secret(settings.elevenlabs_default_voice_id),
                "model_id": settings.elevenlabs_model_id,
                "output_format": settings.elevenlabs_output_format,
                "max_chars_per_request": settings.elevenlabs_max_text_chars,
                "require_confirmation": settings.elevenlabs_require_confirmation,
            },
        )

    def estimate_cost(self, payload: dict[str, object]) -> CostEstimate:
        settings = get_settings()
        text = str(payload.get("text") or "")
        chars = len(text)
        rate = settings.elevenlabs_estimated_cost_per_1000_chars
        estimated = (chars / 1000) * rate if rate > 0 else None
        return CostEstimate(
            provider_name=self.name,
            operation=str(payload.get("operation") or "tts"),
            estimated_cost=estimated,
            currency=settings.cost_currency,
            units_type="characters",
            input_units=float(chars),
            notes="Estimacion local; revisa tu plan real de ElevenLabs antes de monetizar.",
        )

    def create_prompt_pack(self, project_context: dict[str, object]) -> dict[str, object]:
        text = str(project_context.get("script_text") or "")
        return {
            "provider": self.name,
            "pack_type": "tts_handoff",
            "text": clean_tts_text(text),
            "voice_id": project_context.get("voice_id") or get_settings().elevenlabs_default_voice_id,
            "model_id": project_context.get("model_id") or get_settings().elevenlabs_model_id,
        }

    def submit_job(self, payload: dict[str, object]) -> dict[str, object]:
        output_path = Path(str(payload["output_path"]))
        result = self.synthesize_text(
            text=str(payload["text"]),
            language=str(payload.get("language") or "es"),
            voice_id=str(payload.get("voice_id") or get_settings().elevenlabs_default_voice_id),
            model_id=str(payload.get("model_id") or get_settings().elevenlabs_model_id),
            output_path=output_path,
            confirmed_paid=bool(payload.get("confirmed_paid", False)),
            with_timestamps=bool(payload.get("with_timestamps", True)),
        )
        return {
            "status": "completed" if result.ok else "failed",
            "output_path": result.audio_path,
            "error_message": result.error_message,
            "metadata": result.metadata,
            "estimated_cost": result.estimated_cost,
            "actual_cost": result.actual_cost,
        }

    def poll_job(self, job_id: str) -> dict[str, object]:
        return {"job_id": job_id, "status": "not_applicable", "detail": "TTS is synchronous."}

    def import_result(self, result: dict[str, object]) -> dict[str, object]:
        return {"status": "imported" if result.get("output_path") else "missing_output", "result": result}

    def synthesize_text(
        self,
        *,
        text: str,
        language: str,
        voice_id: str | None,
        model_id: str | None,
        output_path: str | Path,
        confirmed_paid: bool = False,
        with_timestamps: bool = True,
        timeout_seconds: int = 120,
    ) -> ElevenLabsSpeechResult:
        settings = get_settings()
        status = self.get_status()
        if not status.available:
            return ElevenLabsSpeechResult(ok=False, error_message=status.detail)
        clean_text = clean_tts_text(text)
        if not clean_text:
            return ElevenLabsSpeechResult(ok=False, error_message="El texto para voz esta vacio.")
        if len(clean_text) > settings.elevenlabs_max_text_chars:
            return ElevenLabsSpeechResult(
                ok=False,
                error_message=(
                    "Texto demasiado largo para esta configuracion: "
                    f"{len(clean_text)} caracteres > {settings.elevenlabs_max_text_chars}."
                ),
            )
        estimate = self.estimate_cost({"operation": "tts", "text": clean_text})
        if (
            estimate.estimated_cost is not None
            and settings.max_estimated_cost_per_job > 0
            and estimate.estimated_cost > settings.max_estimated_cost_per_job
        ):
            return ElevenLabsSpeechResult(
                ok=False,
                estimated_cost=estimate.estimated_cost,
                error_message=(
                    f"Coste estimado {estimate.estimated_cost:.4f} {estimate.currency} "
                    f"supera MAX_ESTIMATED_COST_PER_JOB={settings.max_estimated_cost_per_job}."
                ),
            )
        if (
            (settings.elevenlabs_require_confirmation or settings.require_confirmation_for_paid_tools)
            and not confirmed_paid
        ):
            return ElevenLabsSpeechResult(
                ok=False,
                estimated_cost=estimate.estimated_cost,
                error_message="Operacion de pago bloqueada hasta confirmar el coste en la UI.",
                metadata=_safe_metadata(clean_text, language, model_id, voice_id, estimate),
            )

        voice_id = voice_id or settings.elevenlabs_default_voice_id
        if not voice_id:
            return ElevenLabsSpeechResult(ok=False, error_message="Falta ELEVENLABS_DEFAULT_VOICE_ID o voice_id.")
        model_id = model_id or settings.elevenlabs_model_id
        output = Path(output_path)
        ensure_dir(output.parent)

        if with_timestamps:
            timestamp_result = self._synthesize_with_timestamps(
                text=clean_text,
                voice_id=voice_id,
                model_id=model_id,
                output_path=output,
                timeout_seconds=timeout_seconds,
                estimate=estimate,
            )
            if timestamp_result.ok:
                return timestamp_result

        return self._synthesize_audio_only(
            text=clean_text,
            voice_id=voice_id,
            model_id=model_id,
            output_path=output,
            timeout_seconds=timeout_seconds,
            estimate=estimate,
        )

    def _synthesize_with_timestamps(
        self,
        *,
        text: str,
        voice_id: str,
        model_id: str,
        output_path: Path,
        timeout_seconds: int,
        estimate: CostEstimate,
    ) -> ElevenLabsSpeechResult:
        settings = get_settings()
        query = urlencode({"output_format": settings.elevenlabs_output_format})
        url = f"{self.api_base_url}/text-to-speech/{voice_id}/with-timestamps?{query}"
        payload = json.dumps(_tts_payload(text, model_id)).encode("utf-8")
        try:
            _status, response_body, _content_type = self._http_post(
                url,
                _headers(),
                payload,
                timeout_seconds,
            )
            response = json.loads(response_body.decode("utf-8"))
            audio = base64.b64decode(str(response["audio_base64"]))
            output_path.write_bytes(audio)
            alignment_payload = {
                "alignment": response.get("alignment"),
                "normalized_alignment": response.get("normalized_alignment"),
            }
            alignment_path = output_path.with_suffix(".alignment.json")
            write_json_file(alignment_path, alignment_payload, overwrite=True)
            duration = _duration_from_alignment(alignment_payload)
            return ElevenLabsSpeechResult(
                ok=True,
                audio_path=str(output_path),
                duration_seconds=duration,
                alignment_path=str(alignment_path),
                estimated_cost=estimate.estimated_cost,
                metadata={
                    **_safe_metadata(text, "", model_id, voice_id, estimate),
                    "with_timestamps": True,
                    "output_format": settings.elevenlabs_output_format,
                },
            )
        except Exception as exc:  # noqa: BLE001 - fallback to audio-only with sanitized error.
            return ElevenLabsSpeechResult(
                ok=False,
                estimated_cost=estimate.estimated_cost,
                error_message=_sanitize_error(exc),
                metadata={"with_timestamps": True, "fallback_available": True},
            )

    def _synthesize_audio_only(
        self,
        *,
        text: str,
        voice_id: str,
        model_id: str,
        output_path: Path,
        timeout_seconds: int,
        estimate: CostEstimate,
    ) -> ElevenLabsSpeechResult:
        settings = get_settings()
        query = urlencode({"output_format": settings.elevenlabs_output_format})
        url = f"{self.api_base_url}/text-to-speech/{voice_id}?{query}"
        payload = json.dumps(_tts_payload(text, model_id)).encode("utf-8")
        try:
            _status, response_body, _content_type = self._http_post(
                url,
                _headers(),
                payload,
                timeout_seconds,
            )
            output_path.write_bytes(response_body)
            return ElevenLabsSpeechResult(
                ok=True,
                audio_path=str(output_path),
                duration_seconds=None,
                estimated_cost=estimate.estimated_cost,
                metadata={
                    **_safe_metadata(text, "", model_id, voice_id, estimate),
                    "with_timestamps": False,
                    "output_format": settings.elevenlabs_output_format,
                },
            )
        except Exception as exc:  # noqa: BLE001 - return sanitized provider error to UI.
            return ElevenLabsSpeechResult(
                ok=False,
                estimated_cost=estimate.estimated_cost,
                error_message=_sanitize_error(exc),
                metadata={"with_timestamps": False},
            )


def clean_tts_text(text: str) -> str:
    lines = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.lower().startswith(("fuente:", "source:", "riesgo:", "nota interna:")):
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def _api_key() -> str:
    return get_settings().elevenlabs_api_key.strip()


def _headers() -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "xi-api-key": _api_key(),
    }


def _tts_payload(text: str, model_id: str | None) -> dict[str, object]:
    settings = get_settings()
    return {
        "text": text,
        "model_id": model_id,
        "voice_settings": {
            "stability": settings.elevenlabs_stability,
            "similarity_boost": settings.elevenlabs_similarity_boost,
            "style": settings.elevenlabs_style,
            "use_speaker_boost": settings.elevenlabs_use_speaker_boost,
        },
    }


def _mask_secret(value: str | None) -> str:
    if not value:
        return "not_configured"
    clean = value.strip()
    if len(clean) <= 8:
        return "***"
    return f"{clean[:4]}...{clean[-4:]}"


def _default_http_post(
    url: str,
    headers: dict[str, str],
    body: bytes,
    timeout_seconds: int,
) -> tuple[int, bytes, str]:
    request = Request(url, data=body, headers=headers, method="POST")
    with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310 - official configured API URL.
        return response.status, response.read(), response.headers.get("Content-Type", "")


def _duration_from_alignment(payload: dict[str, Any]) -> float | None:
    alignment = payload.get("normalized_alignment") or payload.get("alignment") or {}
    if not isinstance(alignment, dict):
        return None
    end_times = alignment.get("character_end_times_seconds")
    if not isinstance(end_times, list) or not end_times:
        return None
    try:
        return float(max(end_times))
    except (TypeError, ValueError):
        return None


def _safe_metadata(
    text: str,
    language: str,
    model_id: str | None,
    voice_id: str | None,
    estimate: CostEstimate,
) -> dict[str, object]:
    return {
        "language": language,
        "input_chars": len(text),
        "model_id": model_id,
        "voice_id": voice_id,
        "estimated_cost": estimate.estimated_cost,
        "currency": estimate.currency,
        "units_type": estimate.units_type,
    }


def _sanitize_error(exc: Exception) -> str:
    if isinstance(exc, HTTPError):
        try:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
        except Exception:  # noqa: BLE001 - best-effort details only.
            detail = exc.reason
        return f"ElevenLabs HTTP {exc.code}: {detail}"
    if isinstance(exc, URLError):
        return f"ElevenLabs network error: {exc.reason}"
    message = str(exc)
    key = _api_key()
    if key:
        message = message.replace(key, "[redacted]")
    return message or exc.__class__.__name__
