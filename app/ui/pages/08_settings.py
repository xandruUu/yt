from __future__ import annotations

import os

import streamlit as st
from sqlalchemy import select

from app.ai.llm_orchestrator import list_llm_provider_statuses
from app.config.settings import get_settings
from app.core.enums import ChannelStatus
from app.db import models
from app.db.database import new_session
from app.db.repositories import add_and_commit
from app.i18n.es import LANGUAGE_LABELS_ES, STATUS_LABELS, label_for
from app.services.external_tool_service import list_external_tool_statuses


def render() -> None:
    st.title("Configuración")
    settings = get_settings()
    st.subheader("Rutas locales")
    st.code(
        "\n".join(
            [
                f"APP_ENV={settings.app_env}",
                f"APP_UI_LANGUAGE={settings.app_ui_language}",
                f"CONTENT_LANGUAGE={settings.content_language}",
                f"TARGET_MARKET={settings.target_market}",
                f"DATABASE_URL={settings.database_url}",
                f"OUTPUTS_DIR={settings.outputs_dir}",
                f"ASSETS_DIR={settings.assets_dir}",
                f"EXPORTS_DIR={settings.exports_dir}",
                f"MAX_UPLOAD_MB={settings.max_upload_mb}",
                f"DEFAULT_VIDEO_WIDTH={settings.default_video_width}",
                f"DEFAULT_VIDEO_HEIGHT={settings.default_video_height}",
                f"DEFAULT_FPS={settings.default_fps}",
                f"TARGET_DURATION_SECONDS={settings.target_duration_seconds}",
                f"MAX_VIDEO_DURATION_SECONDS={settings.max_video_duration_seconds}",
                f"DEFAULT_LLM_PROVIDER={settings.default_llm_provider}",
                f"ENABLE_AUTO_LLM={settings.enable_auto_llm}",
                f"ENABLE_OPENAI_LLM={settings.enable_openai_llm}",
                f"ENABLE_OLLAMA_LLM={settings.enable_ollama}",
                f"OLLAMA_MODEL={settings.ollama_model}",
                f"OLLAMA_NUM_CTX={settings.ollama_num_ctx}",
                f"OLLAMA_TIMEOUT_SECONDS={settings.ollama_timeout_seconds}",
                f"ENABLE_YOUTUBE_PROVIDER={settings.enable_youtube_provider}",
                f"ENABLE_RSS_PROVIDER={settings.enable_rss_provider}",
                f"ENABLE_HACKERNEWS_PROVIDER={settings.enable_hackernews_provider}",
                f"DEFAULT_TTS_PROVIDER={settings.default_tts_provider}",
                f"ENABLE_OPENAI_TTS={settings.enable_openai_tts}",
                f"ENABLE_LOCAL_TTS={settings.enable_local_tts}",
                f"ENABLE_ELEVENLABS_TTS={settings.enable_elevenlabs_tts}",
                f"ENABLE_EXTERNAL_TOOLS={settings.enable_external_tools}",
                f"DEFAULT_EXTERNAL_MODE={settings.default_external_mode}",
                f"ENABLE_ELEVENLABS={settings.enable_elevenlabs}",
                f"ELEVENLABS_MODEL_ID={settings.elevenlabs_model_id}",
                f"ELEVENLABS_DEFAULT_VOICE_ID={_mask_secret(settings.elevenlabs_default_voice_id)}",
                f"ELEVENLABS_OUTPUT_FORMAT={settings.elevenlabs_output_format}",
                f"ELEVENLABS_MAX_CHARS_PER_REQUEST={settings.elevenlabs_max_text_chars}",
                f"ELEVENLABS_REQUIRE_CONFIRMATION={settings.elevenlabs_require_confirmation}",
                f"ELEVENLABS_CONFIRM_COST_ABOVE_USD={settings.elevenlabs_confirm_cost_above_usd}",
                f"ELEVENLABS_STABILITY={settings.elevenlabs_stability}",
                f"ELEVENLABS_SIMILARITY_BOOST={settings.elevenlabs_similarity_boost}",
                f"ELEVENLABS_STYLE={settings.elevenlabs_style}",
                f"ELEVENLABS_USE_SPEAKER_BOOST={settings.elevenlabs_use_speaker_boost}",
                f"ENABLE_HIGGSFIELD_AUTOMATION={settings.enable_higgsfield_automation}",
                f"HIGGSFIELD_AUTOMATION_MODE={settings.higgsfield_automation_mode}",
                f"HIGGSFIELD_CLI_BIN={settings.higgsfield_cli_bin}",
                f"HIGGSFIELD_DOWNLOAD_DIR={settings.higgsfield_download_dir}",
                f"HIGGSFIELD_MAX_SCENE_DURATION_SECONDS={settings.higgsfield_max_scene_duration_seconds}",
                f"ENABLE_HIGGSFIELD_MANUAL={settings.enable_higgsfield_manual}",
                f"ENABLE_HIGGSFIELD_MCP={settings.enable_higgsfield_mcp}",
                f"ENABLE_PICSART_MANUAL={settings.enable_picsart_manual}",
                f"ENABLE_PICSART_API={settings.enable_picsart_api}",
                f"ENABLE_OBSIDIAN_SYNC={settings.enable_obsidian_sync}",
                f"OBSIDIAN_VAULT_PATH={settings.obsidian_vault_path}",
                f"ENABLE_COST_GUARDRAILS={settings.enable_cost_guardrails}",
                f"DAILY_MAX_EXTERNAL_COST_USD={settings.daily_max_external_cost_usd}",
                f"DAILY_MAX_HIGGSFIELD_CREDITS={settings.daily_max_higgsfield_credits}",
                f"DAILY_MAX_ELEVENLABS_CHARS={settings.daily_max_elevenlabs_chars}",
                f"REQUIRE_CONFIRMATION_FOR_EXTERNAL_JOBS={settings.require_confirmation_for_external_jobs}",
                f"REQUIRE_CONFIRMATION_FOR_PAID_TOOLS={settings.require_confirmation_for_paid_tools}",
                f"MAX_ESTIMATED_COST_PER_JOB={settings.max_estimated_cost_per_job}",
                f"OPENAI_API_KEY={_mask_secret(os.getenv('OPENAI_API_KEY'))}",
                f"ELEVENLABS_API_KEY={_mask_secret(os.getenv('ELEVENLABS_API_KEY'))}",
                f"PICSART_API_KEY={_mask_secret(os.getenv('PICSART_API_KEY'))}",
                f"HIGGSFIELD_API_KEY={_mask_secret(os.getenv('HIGGSFIELD_API_KEY'))}",
            ]
        )
    )

    st.subheader("Providers IA")
    st.dataframe(
        [
            {
                "provider": status.name,
                "disponible": status.available,
                "puede_costar": status.paid,
                "detalle": status.detail,
            }
            for status in list_llm_provider_statuses()
        ],
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Herramientas externas")
    st.dataframe(list_external_tool_statuses(), use_container_width=True, hide_index=True)
    st.caption("Las claves API se muestran enmascaradas y se leen desde variables de entorno.")

    st.subheader("Canales")
    _channel_form()
    _channel_table()


def _mask_secret(value: str | None) -> str:
    if not value:
        return "no configurada"
    clean = value.strip()
    if len(clean) <= 8:
        return "***"
    return f"{clean[:4]}...{clean[-4:]}"


def _channel_form() -> None:
    with st.form("channel_form"):
        name = st.text_input("Nombre del canal")
        language = st.selectbox(
            "Idioma",
            ["en", "es", "hi_hinglish"],
            format_func=lambda value: label_for(LANGUAGE_LABELS_ES, value),
        )
        market = st.text_input("Mercado", value="global")
        youtube_handle = st.text_input("Handle de YouTube")
        description = st.text_area("Descripción")
        status = st.selectbox(
            "Estado",
            [item.value for item in ChannelStatus],
            format_func=lambda value: label_for(STATUS_LABELS, value),
        )
        if st.form_submit_button("Crear canal"):
            with new_session() as session:
                add_and_commit(
                    session,
                    models.Channel(
                        name=name,
                        language=language,
                        market=market,
                        youtube_handle=youtube_handle,
                        description=description,
                        status=status,
                    ),
                )
            st.success("Canal creado.")


def _channel_table() -> None:
    with new_session() as session:
        channels = session.scalars(select(models.Channel).order_by(models.Channel.name)).all()
        st.dataframe(
            [
                {
                    "id": channel.id,
                    "nombre": channel.name,
                    "idioma": label_for(LANGUAGE_LABELS_ES, channel.language),
                    "mercado": channel.market,
                    "handle": channel.youtube_handle,
                    "estado": label_for(STATUS_LABELS, channel.status),
                }
                for channel in channels
            ],
            use_container_width=True,
            hide_index=True,
        )
