from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - dependency is optional until installed.
    load_dotenv = None


if load_dotenv:
    load_dotenv()


@dataclass(frozen=True)
class Settings:
    app_env: str
    database_url: str
    output_dir: Path
    assets_dir: Path
    default_video_width: int
    default_video_height: int
    default_fps: int
    target_duration_seconds: int
    enable_auto_llm: bool
    default_llm_provider: str
    openai_text_model: str
    openai_tts_model: str
    openai_tts_voice: str
    enable_openai_llm: bool
    enable_openai_tts: bool
    ollama_base_url: str
    ollama_model: str
    enable_ollama: bool
    default_tts_provider: str
    enable_local_tts: bool
    enable_elevenlabs_tts: bool
    enable_external_tools: bool
    default_external_mode: str
    enable_elevenlabs: bool
    elevenlabs_api_key: str
    elevenlabs_default_voice_id: str
    elevenlabs_model_id: str
    elevenlabs_output_format: str
    elevenlabs_max_text_chars: int
    elevenlabs_stability: float
    elevenlabs_similarity_boost: float
    elevenlabs_style: float
    elevenlabs_use_speaker_boost: bool
    elevenlabs_require_confirmation: bool
    elevenlabs_estimated_cost_per_1000_chars: float
    enable_higgsfield_manual: bool
    enable_higgsfield_mcp: bool
    higgsfield_mcp_url: str
    higgsfield_output_dir: Path
    enable_picsart_manual: bool
    enable_picsart_api: bool
    picsart_output_dir: Path
    require_confirmation_for_paid_tools: bool
    max_estimated_cost_per_job: float
    cost_currency: str
    max_imported_asset_mb: int
    allowed_video_extensions: tuple[str, ...]
    allowed_audio_extensions: tuple[str, ...]
    allowed_image_extensions: tuple[str, ...]
    piper_tts_path: str
    pyttsx3_enabled: bool
    default_music_volume: float
    default_voice_volume: float
    ffmpeg_path: str
    ffprobe_path: str

    @property
    def database_path(self) -> Path:
        if self.database_url.startswith("sqlite:///"):
            return Path(self.database_url.removeprefix("sqlite:///"))
        raise ValueError("Only sqlite:/// DATABASE_URL values are supported in the MVP.")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        app_env=os.getenv("APP_ENV", "local"),
        database_url=os.getenv("DATABASE_URL", "sqlite:///data/shorts_factory.db"),
        output_dir=Path(os.getenv("OUTPUT_DIR", "outputs")),
        assets_dir=Path(os.getenv("ASSETS_DIR", "assets")),
        default_video_width=int(os.getenv("DEFAULT_VIDEO_WIDTH", "1080")),
        default_video_height=int(os.getenv("DEFAULT_VIDEO_HEIGHT", "1920")),
        default_fps=int(os.getenv("DEFAULT_FPS", "30")),
        target_duration_seconds=int(os.getenv("TARGET_DURATION_SECONDS", "38")),
        enable_auto_llm=_env_bool("ENABLE_AUTO_LLM", False),
        default_llm_provider=os.getenv("DEFAULT_LLM_PROVIDER", "manual"),
        openai_text_model=os.getenv("OPENAI_TEXT_MODEL") or os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        openai_tts_model=os.getenv("OPENAI_TTS_MODEL", ""),
        openai_tts_voice=os.getenv("OPENAI_TTS_VOICE", ""),
        enable_openai_llm=_env_bool("ENABLE_OPENAI_LLM", False),
        enable_openai_tts=_env_bool("ENABLE_OPENAI_TTS", False),
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        ollama_model=os.getenv("OLLAMA_MODEL", "llama3.1"),
        enable_ollama=_env_bool("ENABLE_OLLAMA", False),
        default_tts_provider=os.getenv("DEFAULT_TTS_PROVIDER", "manual"),
        enable_local_tts=_env_bool("ENABLE_LOCAL_TTS", False),
        enable_elevenlabs_tts=_env_bool("ENABLE_ELEVENLABS_TTS", False),
        enable_external_tools=_env_bool("ENABLE_EXTERNAL_TOOLS", True),
        default_external_mode=os.getenv("DEFAULT_EXTERNAL_MODE", "manual"),
        enable_elevenlabs=_env_bool("ENABLE_ELEVENLABS", False),
        elevenlabs_api_key=os.getenv("ELEVENLABS_API_KEY", ""),
        elevenlabs_default_voice_id=os.getenv("ELEVENLABS_DEFAULT_VOICE_ID", ""),
        elevenlabs_model_id=os.getenv("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2"),
        elevenlabs_output_format=os.getenv("ELEVENLABS_OUTPUT_FORMAT", "mp3_44100_128"),
        elevenlabs_max_text_chars=int(
            os.getenv("ELEVENLABS_MAX_CHARS_PER_REQUEST")
            or os.getenv("ELEVENLABS_MAX_TEXT_CHARS", "5000")
        ),
        elevenlabs_stability=float(os.getenv("ELEVENLABS_STABILITY", "0.55")),
        elevenlabs_similarity_boost=float(os.getenv("ELEVENLABS_SIMILARITY_BOOST", "0.75")),
        elevenlabs_style=float(os.getenv("ELEVENLABS_STYLE", "0.20")),
        elevenlabs_use_speaker_boost=_env_bool("ELEVENLABS_USE_SPEAKER_BOOST", True),
        elevenlabs_require_confirmation=_env_bool("ELEVENLABS_REQUIRE_CONFIRMATION", True),
        elevenlabs_estimated_cost_per_1000_chars=float(
            os.getenv("ELEVENLABS_ESTIMATED_COST_PER_1000_CHARS", "0")
        ),
        enable_higgsfield_manual=_env_bool("ENABLE_HIGGSFIELD_MANUAL", True),
        enable_higgsfield_mcp=_env_bool("ENABLE_HIGGSFIELD_MCP", False),
        higgsfield_mcp_url=os.getenv("HIGGSFIELD_MCP_URL", "https://mcp.higgsfield.ai/mcp"),
        higgsfield_output_dir=Path(os.getenv("HIGGSFIELD_OUTPUT_DIR", "external_outputs/higgsfield")),
        enable_picsart_manual=_env_bool("ENABLE_PICSART_MANUAL", True),
        enable_picsart_api=_env_bool("ENABLE_PICSART_API", False),
        picsart_output_dir=Path(os.getenv("PICSART_OUTPUT_DIR", "external_outputs/picsart")),
        require_confirmation_for_paid_tools=_env_bool("REQUIRE_CONFIRMATION_FOR_PAID_TOOLS", True),
        max_estimated_cost_per_job=float(os.getenv("MAX_ESTIMATED_COST_PER_JOB", "1.00")),
        cost_currency=os.getenv("COST_CURRENCY", "USD"),
        max_imported_asset_mb=int(os.getenv("MAX_IMPORTED_ASSET_MB", "500")),
        allowed_video_extensions=_env_csv("ALLOWED_VIDEO_EXTENSIONS", ".mp4,.mov,.webm"),
        allowed_audio_extensions=_env_csv("ALLOWED_AUDIO_EXTENSIONS", ".mp3,.wav,.m4a,.aac,.ogg"),
        allowed_image_extensions=_env_csv("ALLOWED_IMAGE_EXTENSIONS", ".png,.jpg,.jpeg,.webp"),
        piper_tts_path=os.getenv("PIPER_TTS_PATH", ""),
        pyttsx3_enabled=_env_bool("PYTTSX3_ENABLED", False),
        default_music_volume=float(os.getenv("DEFAULT_MUSIC_VOLUME", "0.12")),
        default_voice_volume=float(os.getenv("DEFAULT_VOICE_VOLUME", "1.0")),
        ffmpeg_path=os.getenv("FFMPEG_PATH", "ffmpeg"),
        ffprobe_path=os.getenv("FFPROBE_PATH", "ffprobe"),
    )


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_csv(name: str, default: str) -> tuple[str, ...]:
    raw = os.getenv(name, default)
    return tuple(item.strip().lower() for item in raw.split(",") if item.strip())
