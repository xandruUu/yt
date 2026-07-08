from __future__ import annotations

from app.tts.base import TTSProvider, VoiceOption, VoiceoverResult
from app.tts.elevenlabs_tts_provider import ElevenLabsTTSProvider
from app.tts.local_tts_provider import LocalTTSProvider
from app.tts.manual_voice_provider import ManualVoiceProvider
from app.tts.openai_tts_provider import OpenAITTSProvider
from app.tts.placeholder_voice_provider import PlaceholderVoiceProvider

__all__ = [
    "ElevenLabsTTSProvider",
    "LocalTTSProvider",
    "ManualVoiceProvider",
    "OpenAITTSProvider",
    "PlaceholderVoiceProvider",
    "TTSProvider",
    "VoiceOption",
    "VoiceoverResult",
]
