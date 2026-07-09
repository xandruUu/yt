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
    app_ui_language: str
    content_language: str
    target_market: str
    database_url: str
    output_dir: Path
    outputs_dir: Path
    assets_dir: Path
    exports_dir: Path
    max_upload_mb: int
    default_video_width: int
    default_video_height: int
    default_fps: int
    target_duration_seconds: int
    max_video_duration_seconds: int
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
    ollama_num_ctx: int
    ollama_temperature_research: float
    ollama_temperature_metadata: float
    ollama_temperature_script: float
    ollama_temperature_scenes: float
    ollama_temperature_prompts: float
    ollama_timeout_seconds: int
    enable_youtube_provider: bool
    youtube_api_key: str
    youtube_region_code: str
    youtube_lookback_days: int
    youtube_max_results_per_query: int
    enable_rss_provider: bool
    rss_feeds_file: Path
    enable_news_provider: bool
    news_api_key: str
    enable_hackernews_provider: bool
    hackernews_lookback_days: int
    enable_tiktok_research_provider: bool
    enable_google_trends_provider: bool
    google_trends_region: str
    enable_instagram_provider: bool
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
    elevenlabs_confirm_cost_above_usd: float
    elevenlabs_estimated_cost_per_1000_chars: float
    enable_higgsfield_manual: bool
    enable_higgsfield_mcp: bool
    enable_higgsfield_automation: bool
    higgsfield_automation_mode: str
    higgsfield_cli_bin: str
    higgsfield_skills_enabled: bool
    higgsfield_default_aspect_ratio: str
    higgsfield_default_duration_seconds: int
    higgsfield_max_scene_duration_seconds: int
    higgsfield_confirm_credits_above: float
    higgsfield_download_dir: Path
    higgsfield_poll_interval_seconds: int
    higgsfield_job_timeout_seconds: int
    higgsfield_mcp_url: str
    higgsfield_output_dir: Path
    enable_picsart_manual: bool
    enable_picsart_api: bool
    picsart_output_dir: Path
    enable_obsidian_sync: bool
    obsidian_vault_path: Path
    obsidian_auto_export_on_approval: bool
    obsidian_import_notes: bool
    require_confirmation_for_paid_tools: bool
    require_confirmation_for_external_jobs: bool
    enable_cost_guardrails: bool
    daily_max_external_cost_usd: float
    daily_max_higgsfield_credits: float
    daily_max_elevenlabs_chars: int
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
    output_dir = Path(os.getenv("OUTPUT_DIR") or os.getenv("OUTPUTS_DIR", "outputs"))
    return Settings(
        app_env=os.getenv("APP_ENV", "local"),
        app_ui_language=os.getenv("APP_UI_LANGUAGE", "es"),
        content_language=os.getenv("CONTENT_LANGUAGE", "en"),
        target_market=os.getenv("TARGET_MARKET", "global"),
        database_url=os.getenv("DATABASE_URL", "sqlite:///data/shorts_factory.db"),
        output_dir=output_dir,
        outputs_dir=Path(os.getenv("OUTPUTS_DIR", str(output_dir))),
        assets_dir=Path(os.getenv("ASSETS_DIR", "assets")),
        exports_dir=Path(os.getenv("EXPORTS_DIR", "exports")),
        max_upload_mb=int(os.getenv("MAX_UPLOAD_MB", "250")),
        default_video_width=int(os.getenv("DEFAULT_VIDEO_WIDTH", "1080")),
        default_video_height=int(os.getenv("DEFAULT_VIDEO_HEIGHT", "1920")),
        default_fps=int(os.getenv("DEFAULT_FPS", "30")),
        target_duration_seconds=int(os.getenv("TARGET_DURATION_SECONDS", "38")),
        max_video_duration_seconds=int(os.getenv("MAX_VIDEO_DURATION_SECONDS", "90")),
        enable_auto_llm=_env_bool("ENABLE_AUTO_LLM", False),
        default_llm_provider=os.getenv("DEFAULT_LLM_PROVIDER", "manual"),
        openai_text_model=os.getenv("OPENAI_TEXT_MODEL") or os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        openai_tts_model=os.getenv("OPENAI_TTS_MODEL", ""),
        openai_tts_voice=os.getenv("OPENAI_TTS_VOICE", ""),
        enable_openai_llm=_env_bool("ENABLE_OPENAI_LLM", False),
        enable_openai_tts=_env_bool("ENABLE_OPENAI_TTS", False),
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        ollama_model=os.getenv("OLLAMA_MODEL", "llama3.1"),
        enable_ollama=_env_bool("ENABLE_OLLAMA_LLM", _env_bool("ENABLE_OLLAMA", False)),
        ollama_num_ctx=int(os.getenv("OLLAMA_NUM_CTX", "16384")),
        ollama_temperature_research=float(os.getenv("OLLAMA_TEMPERATURE_RESEARCH", "0.75")),
        ollama_temperature_metadata=float(os.getenv("OLLAMA_TEMPERATURE_METADATA", "0.65")),
        ollama_temperature_script=float(os.getenv("OLLAMA_TEMPERATURE_SCRIPT", "0.55")),
        ollama_temperature_scenes=float(os.getenv("OLLAMA_TEMPERATURE_SCENES", "0.55")),
        ollama_temperature_prompts=float(os.getenv("OLLAMA_TEMPERATURE_PROMPTS", "0.40")),
        ollama_timeout_seconds=int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "180")),
        enable_youtube_provider=_env_bool("ENABLE_YOUTUBE_PROVIDER", _env_bool("ENABLE_YOUTUBE_RESEARCH", False)),
        youtube_api_key=os.getenv("YOUTUBE_API_KEY") or os.getenv("YOUTUBE_DATA_API_KEY", ""),
        youtube_region_code=os.getenv("YOUTUBE_REGION_CODE", "US"),
        youtube_lookback_days=int(os.getenv("YOUTUBE_LOOKBACK_DAYS", "30")),
        youtube_max_results_per_query=int(os.getenv("YOUTUBE_MAX_RESULTS_PER_QUERY", "25")),
        enable_rss_provider=_env_bool("ENABLE_RSS_PROVIDER", True),
        rss_feeds_file=Path(os.getenv("RSS_FEEDS_FILE", "config/rss_sources.json")),
        enable_news_provider=_env_bool("ENABLE_NEWS_PROVIDER", False),
        news_api_key=os.getenv("NEWS_API_KEY", ""),
        enable_hackernews_provider=_env_bool("ENABLE_HACKERNEWS_PROVIDER", True),
        hackernews_lookback_days=int(os.getenv("HACKERNEWS_LOOKBACK_DAYS", "30")),
        enable_tiktok_research_provider=_env_bool("ENABLE_TIKTOK_RESEARCH_PROVIDER", False),
        enable_google_trends_provider=_env_bool(
            "ENABLE_GOOGLE_TRENDS_PROVIDER",
            _env_bool("ENABLE_GOOGLE_TRENDS", False),
        ),
        google_trends_region=os.getenv("GOOGLE_TRENDS_REGION", "US"),
        enable_instagram_provider=_env_bool("ENABLE_INSTAGRAM_PROVIDER", False),
        default_tts_provider=os.getenv("DEFAULT_TTS_PROVIDER", "manual"),
        enable_local_tts=_env_bool("ENABLE_LOCAL_TTS", False),
        enable_elevenlabs_tts=_env_bool("ENABLE_ELEVENLABS_TTS", False),
        enable_external_tools=_env_bool("ENABLE_EXTERNAL_TOOLS", True),
        default_external_mode=os.getenv("DEFAULT_EXTERNAL_MODE", "manual"),
        enable_elevenlabs=_env_bool("ENABLE_ELEVENLABS", False),
        elevenlabs_api_key=os.getenv("ELEVENLABS_API_KEY", ""),
        elevenlabs_default_voice_id=os.getenv("ELEVENLABS_VOICE_ID")
        or os.getenv("ELEVENLABS_DEFAULT_VOICE_ID", ""),
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
        elevenlabs_confirm_cost_above_usd=float(os.getenv("ELEVENLABS_CONFIRM_COST_ABOVE_USD", "1.00")),
        elevenlabs_estimated_cost_per_1000_chars=float(
            os.getenv("ELEVENLABS_ESTIMATED_COST_PER_1000_CHARS", "0")
        ),
        enable_higgsfield_manual=_env_bool("ENABLE_HIGGSFIELD_MANUAL", True),
        enable_higgsfield_mcp=_env_bool("ENABLE_HIGGSFIELD_MCP", False),
        enable_higgsfield_automation=_env_bool("ENABLE_HIGGSFIELD_AUTOMATION", False),
        higgsfield_automation_mode=os.getenv("HIGGSFIELD_AUTOMATION_MODE", "manual"),
        higgsfield_cli_bin=os.getenv("HIGGSFIELD_CLI_BIN", "higgsfield"),
        higgsfield_skills_enabled=_env_bool("HIGGSFIELD_SKILLS_ENABLED", True),
        higgsfield_default_aspect_ratio=os.getenv("HIGGSFIELD_DEFAULT_ASPECT_RATIO", "9:16"),
        higgsfield_default_duration_seconds=int(os.getenv("HIGGSFIELD_DEFAULT_DURATION_SECONDS", "8")),
        higgsfield_max_scene_duration_seconds=int(os.getenv("HIGGSFIELD_MAX_SCENE_DURATION_SECONDS", "15")),
        higgsfield_confirm_credits_above=float(os.getenv("HIGGSFIELD_CONFIRM_CREDITS_ABOVE", "10")),
        higgsfield_download_dir=Path(os.getenv("HIGGSFIELD_DOWNLOAD_DIR", "assets/higgsfield_clips")),
        higgsfield_poll_interval_seconds=int(os.getenv("HIGGSFIELD_POLL_INTERVAL_SECONDS", "20")),
        higgsfield_job_timeout_seconds=int(os.getenv("HIGGSFIELD_JOB_TIMEOUT_SECONDS", "1800")),
        higgsfield_mcp_url=os.getenv("HIGGSFIELD_MCP_URL", "https://mcp.higgsfield.ai/mcp"),
        higgsfield_output_dir=Path(os.getenv("HIGGSFIELD_OUTPUT_DIR", "external_outputs/higgsfield")),
        enable_picsart_manual=_env_bool("ENABLE_PICSART_MANUAL", True),
        enable_picsart_api=_env_bool("ENABLE_PICSART_API", False),
        picsart_output_dir=Path(os.getenv("PICSART_OUTPUT_DIR", "external_outputs/picsart")),
        enable_obsidian_sync=_env_bool("ENABLE_OBSIDIAN_SYNC", False),
        obsidian_vault_path=Path(os.getenv("OBSIDIAN_VAULT_PATH", "ShortsFactoryBrain")),
        obsidian_auto_export_on_approval=_env_bool("OBSIDIAN_AUTO_EXPORT_ON_APPROVAL", True),
        obsidian_import_notes=_env_bool("OBSIDIAN_IMPORT_NOTES", True),
        require_confirmation_for_paid_tools=_env_bool("REQUIRE_CONFIRMATION_FOR_PAID_TOOLS", True),
        require_confirmation_for_external_jobs=_env_bool("REQUIRE_CONFIRMATION_FOR_EXTERNAL_JOBS", True),
        enable_cost_guardrails=_env_bool("ENABLE_COST_GUARDRAILS", True),
        daily_max_external_cost_usd=float(os.getenv("DAILY_MAX_EXTERNAL_COST_USD", "5.00")),
        daily_max_higgsfield_credits=float(os.getenv("DAILY_MAX_HIGGSFIELD_CREDITS", "50")),
        daily_max_elevenlabs_chars=int(os.getenv("DAILY_MAX_ELEVENLABS_CHARS", "20000")),
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
