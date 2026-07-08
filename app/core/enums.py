from __future__ import annotations

from enum import StrEnum


class ChannelStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"


class TopicCategory(StrEnum):
    AI_TOOLS = "ai_tools"
    TECH_EXPLAINED = "tech_explained"
    SCIENCE_EXPLAINED = "science_explained"
    BUSINESS_CASE = "business_case"
    INTERNET_CULTURE_EXPLAINED = "internet_culture_explained"
    ENGINEERING = "engineering"
    PSYCHOLOGY = "psychology"
    PRODUCTIVITY = "productivity"
    FINANCE_EDUCATIONAL = "finance_educational"
    HISTORY_EXPLAINED = "history_explained"
    MYSTERY_EXPLAINED = "mystery_explained"
    OTHER = "other"


class TopicStatus(StrEnum):
    IDEA = "idea"
    APPROVED_FOR_HOOKS = "approved_for_hooks"
    REJECTED = "rejected"
    ARCHIVED = "archived"


class GeneratedIdeaStatus(StrEnum):
    SUGGESTED = "suggested"
    SELECTED = "selected"
    SAVED_FOR_LATER = "saved_for_later"
    DISCARDED = "discarded"
    CONVERTED_TO_TOPIC = "converted_to_topic"
    ARCHIVED = "archived"


class GeneratedTitleStatus(StrEnum):
    SUGGESTED = "suggested"
    SELECTED = "selected"
    DISCARDED = "discarded"
    EDITED = "edited"
    ARCHIVED = "archived"


class MetadataSuggestionStatus(StrEnum):
    SUGGESTED = "suggested"
    SELECTED = "selected"
    EDITED = "edited"
    ARCHIVED = "archived"


class HookType(StrEnum):
    MYSTERY = "mystery"
    FEAR = "fear"
    MONEY = "money"
    UTILITY = "utility"
    MISTAKE = "mistake"
    SURPRISE = "surprise"
    CONTROVERSY_SAFE = "controversy_safe"
    STORY = "story"
    COMPARISON = "comparison"


class ScriptStatus(StrEnum):
    DRAFT = "draft"
    NEEDS_REVIEW = "needs_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    LOCALIZED = "localized"


class AssetType(StrEnum):
    BACKGROUND = "background"
    IMAGE = "image"
    VIDEO_CLIP = "video_clip"
    ICON = "icon"
    SFX = "sfx"
    FONT = "font"
    OTHER = "other"


class MusicMood(StrEnum):
    MYSTERIOUS = "mysterious"
    TECH = "tech"
    DRAMATIC = "dramatic"
    CALM = "calm"
    ENERGETIC = "energetic"
    EDUCATIONAL = "educational"
    CINEMATIC = "cinematic"
    NEUTRAL = "neutral"


class VoiceProvider(StrEnum):
    MANUAL_RECORDING = "manual_recording"
    LOCAL_TTS = "local_tts"
    EXTERNAL_TTS = "external_tts"
    PLACEHOLDER = "placeholder"


class VoiceoverJobStatus(StrEnum):
    PENDING = "pending"
    GENERATING = "generating"
    GENERATED = "generated"
    IMPORTED_MANUAL = "imported_manual"
    PLACEHOLDER = "placeholder"
    FAILED = "failed"
    APPROVED = "approved"
    REJECTED = "rejected"
    ARCHIVED = "archived"


class SubtitleTrackStatus(StrEnum):
    GENERATED = "generated"
    EDITED = "edited"
    APPROVED = "approved"
    REJECTED = "rejected"
    ARCHIVED = "archived"


class VisualPlanStatus(StrEnum):
    GENERATED = "generated"
    EDITED = "edited"
    APPROVED = "approved"
    REJECTED = "rejected"
    ARCHIVED = "archived"


class VisualStoryboardStatus(StrEnum):
    GENERATED = "generated"
    EDITED = "edited"
    APPROVED = "approved"
    REJECTED = "rejected"
    ARCHIVED = "archived"


class StoryboardSceneStatus(StrEnum):
    GENERATED = "generated"
    EDITED = "edited"
    APPROVED = "approved"
    NEEDS_ASSET = "needs_asset"
    MAPPED = "mapped"
    REJECTED = "rejected"
    ARCHIVED = "archived"


class RenderPlanStatus(StrEnum):
    PENDING = "pending"
    READY = "ready"
    RENDERING = "rendering"
    RENDERED = "rendered"
    FAILED = "failed"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPORTED = "exported"


class ExternalToolJobStatus(StrEnum):
    DRAFT = "draft"
    READY = "ready"
    CONFIRMATION_REQUIRED = "confirmation_required"
    SUBMITTED = "submitted"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    IMPORTED = "imported"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    ARCHIVED = "archived"


class PromptPackStatus(StrEnum):
    DRAFT = "draft"
    GENERATED = "generated"
    EXPORTED = "exported"
    USED_MANUALLY = "used_manually"
    IMPORTED_RESULTS = "imported_results"
    ARCHIVED = "archived"


class ExternalAssetStatus(StrEnum):
    IMPORTED = "imported"
    NEEDS_LICENSE_REVIEW = "needs_license_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    PROCESSED = "processed"
    USED_IN_RENDER = "used_in_render"
    ARCHIVED = "archived"


class LicenseReviewStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_CHANGES = "needs_changes"
    ARCHIVED = "archived"


class CostEventStatus(StrEnum):
    ESTIMATED = "estimated"
    CONFIRMED = "confirmed"
    BILLED = "billed"
    CANCELLED = "cancelled"
    ARCHIVED = "archived"


class RenderStatus(StrEnum):
    PENDING = "pending"
    RENDERING = "rendering"
    RENDERED = "rendered"
    FAILED = "failed"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPORTED = "exported"


class VideoWorkflowStatus(StrEnum):
    IDEA = "idea"
    HOOKS_PENDING = "hooks_pending"
    HOOKS_GENERATED = "hooks_generated"
    HOOK_SELECTED = "hook_selected"
    SCRIPT_PENDING = "script_pending"
    SCRIPT_GENERATED = "script_generated"
    SCRIPT_REVIEW_PENDING = "script_review_pending"
    SCRIPT_APPROVED = "script_approved"
    ASSETS_PENDING = "assets_pending"
    RENDER_PENDING = "render_pending"
    RENDERED = "rendered"
    REVIEW_PENDING = "review_pending"
    APPROVED = "approved"
    EXPORTED = "exported"
    MANUALLY_PUBLISHED = "manually_published"
    REJECTED = "rejected"
    ARCHIVED = "archived"


class WizardStep(StrEnum):
    BASIC_DATA = "basic_data"
    RESEARCH = "research"
    IDEA_SELECTION = "idea_selection"
    HOOK_SELECTION = "hook_selection"
    TITLE_SELECTION = "title_selection"
    METADATA = "metadata"
    SCRIPT_GENERATION = "script_generation"
    CHARACTER = "character"
    STORYBOARD = "storyboard"
    PROMPT_PACK = "prompt_pack"
    LOCALIZATION = "localization"
    VOICEOVER = "voiceover"
    MUSIC_SELECTION = "music_selection"
    CLIP_IMPORT = "clip_import"
    SCENE_MAPPING = "scene_mapping"
    VISUAL_STYLE = "visual_style"
    RENDER = "render"
    REVIEW = "review"
    EXPORT = "export"
