from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def now_utc() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=now_utc,
        onupdate=now_utc,
    )


class Channel(TimestampMixin, Base):
    __tablename__ = "channels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    language: Mapped[str] = mapped_column(String(32), nullable=False)
    market: Mapped[str] = mapped_column(String(80), nullable=False, default="global")
    description: Mapped[str | None] = mapped_column(Text)
    youtube_handle: Mapped[str | None] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")

    renders: Mapped[list[Render]] = relationship(back_populates="channel")


class Topic(TimestampMixin, Base):
    __tablename__ = "topics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    category: Mapped[str] = mapped_column(String(80), nullable=False, default="other")
    source: Mapped[str | None] = mapped_column(String(200))
    source_url: Mapped[str | None] = mapped_column(Text)
    language_origin: Mapped[str] = mapped_column(String(32), nullable=False, default="en")
    target_markets: Mapped[str] = mapped_column(Text, nullable=False, default="global")
    trend_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    rpm_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    visual_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    evergreen_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    competition_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    copyright_risk: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    monetization_risk: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    status: Mapped[str] = mapped_column(String(48), nullable=False, default="idea")
    notes: Mapped[str | None] = mapped_column(Text)

    hooks: Mapped[list[Hook]] = relationship(back_populates="topic", cascade="all, delete-orphan")
    scripts: Mapped[list[Script]] = relationship(back_populates="topic", cascade="all, delete-orphan")


class GeneratedIdea(TimestampMixin, Base):
    __tablename__ = "generated_ideas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    trend_item_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    angle: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    why_it_can_work: Mapped[str] = mapped_column(Text, nullable=False)
    target_language: Mapped[str] = mapped_column(String(32), nullable=False)
    target_market: Mapped[str] = mapped_column(String(80), nullable=False)
    category: Mapped[str] = mapped_column(String(80), nullable=False)
    suggested_duration: Mapped[str] = mapped_column(String(48), nullable=False, default="30-45s")
    suggested_format: Mapped[str] = mapped_column(String(80), nullable=False, default="documental_rapido")
    suggested_hook_type: Mapped[str] = mapped_column(String(64), nullable=False, default="mystery")
    suggested_visual: Mapped[str | None] = mapped_column(Text)
    target_audience: Mapped[str | None] = mapped_column(Text)
    viral_score: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    rpm_score: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    visual_score: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    narrative_clarity_score: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    evergreen_score: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    novelty_score: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    production_ease_score: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    copyright_risk: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    monetization_risk: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    total_score: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    sources_json: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(48), nullable=False, default="suggested")
    converted_topic_id: Mapped[int | None] = mapped_column(ForeignKey("topics.id"), nullable=True)

    converted_topic: Mapped[Topic | None] = relationship()


class GeneratedTitle(TimestampMixin, Base):
    __tablename__ = "generated_titles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    generated_idea_id: Mapped[int | None] = mapped_column(ForeignKey("generated_ideas.id"), nullable=True)
    topic_id: Mapped[int | None] = mapped_column(ForeignKey("topics.id"), nullable=True)
    hook_id: Mapped[int] = mapped_column(ForeignKey("hooks.id"), nullable=False, index=True)
    language: Mapped[str] = mapped_column(String(32), nullable=False, default="es")
    market: Mapped[str] = mapped_column(String(80), nullable=False, default="global")
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    title_type: Mapped[str] = mapped_column(String(64), nullable=False, default="curiosity")
    clarity_score: Mapped[int] = mapped_column(Integer, nullable=False, default=7)
    curiosity_score: Mapped[int] = mapped_column(Integer, nullable=False, default=7)
    seo_score: Mapped[int] = mapped_column(Integer, nullable=False, default=6)
    ctr_estimate_score: Mapped[int] = mapped_column(Integer, nullable=False, default=7)
    clickbait_risk: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    total_score: Mapped[int] = mapped_column(Integer, nullable=False, default=70)
    length_chars: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    why_it_works: Mapped[str | None] = mapped_column(Text)
    selected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(48), nullable=False, default="suggested")


class MetadataSuggestion(TimestampMixin, Base):
    __tablename__ = "metadata_suggestions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    generated_idea_id: Mapped[int | None] = mapped_column(ForeignKey("generated_ideas.id"), nullable=True)
    topic_id: Mapped[int | None] = mapped_column(ForeignKey("topics.id"), nullable=True)
    hook_id: Mapped[int | None] = mapped_column(ForeignKey("hooks.id"), nullable=True)
    title_id: Mapped[int | None] = mapped_column(ForeignKey("generated_titles.id"), nullable=True)
    script_id: Mapped[int | None] = mapped_column(ForeignKey("scripts.id"), nullable=True)
    language: Mapped[str] = mapped_column(String(32), nullable=False, default="es")
    market: Mapped[str] = mapped_column(String(80), nullable=False, default="global")
    description: Mapped[str] = mapped_column(Text, nullable=False)
    hashtags_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    pinned_comment: Mapped[str | None] = mapped_column(Text)
    upload_notes: Mapped[str | None] = mapped_column(Text)
    synthetic_media_note: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    made_for_kids_recommendation: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(48), nullable=False, default="suggested")


class Hook(Base):
    __tablename__ = "hooks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id"), nullable=False, index=True)
    language: Mapped[str] = mapped_column(String(32), nullable=False, default="en")
    text: Mapped[str] = mapped_column(Text, nullable=False)
    hook_type: Mapped[str] = mapped_column(String(64), nullable=False, default="mystery")
    clarity_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    curiosity_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    emotion_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    risk_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    selected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    topic: Mapped[Topic] = relationship(back_populates="hooks")
    scripts: Mapped[list[Script]] = relationship(back_populates="hook")


class Script(TimestampMixin, Base):
    __tablename__ = "scripts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id"), nullable=False, index=True)
    hook_id: Mapped[int | None] = mapped_column(ForeignKey("hooks.id"), index=True)
    language: Mapped[str] = mapped_column(String(32), nullable=False, default="en")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    script_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    estimated_duration_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=38.0)
    tone: Mapped[str] = mapped_column(String(120), nullable=False, default="fast_clear_documentary")
    status: Mapped[str] = mapped_column(String(48), nullable=False, default="draft")
    needs_fact_check: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    fact_check_notes: Mapped[str | None] = mapped_column(Text)
    title_suggestion: Mapped[str | None] = mapped_column(String(180))
    description_suggestion: Mapped[str | None] = mapped_column(Text)
    hashtags: Mapped[str | None] = mapped_column(Text)
    needs_native_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    topic: Mapped[Topic] = relationship(back_populates="scripts")
    hook: Mapped[Hook | None] = relationship(back_populates="scripts")
    lines: Mapped[list[ScriptLine]] = relationship(
        back_populates="script",
        cascade="all, delete-orphan",
        order_by="ScriptLine.line_order",
    )
    voiceovers: Mapped[list[Voiceover]] = relationship(back_populates="script")
    renders: Mapped[list[Render]] = relationship(back_populates="script")


class ScriptLine(Base):
    __tablename__ = "script_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    script_id: Mapped[int] = mapped_column(ForeignKey("scripts.id"), nullable=False, index=True)
    line_order: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    visual_suggestion: Mapped[str | None] = mapped_column(Text)
    duration_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=2.5)
    subtitle_text: Mapped[str | None] = mapped_column(Text)
    needs_source: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source_url: Mapped[str | None] = mapped_column(Text)
    risk_note: Mapped[str | None] = mapped_column(Text)

    script: Mapped[Script] = relationship(back_populates="lines")


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    asset_type: Mapped[str] = mapped_column(String(64), nullable=False, default="other")
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(200), nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text)
    license_type: Mapped[str] = mapped_column(String(120), nullable=False)
    attribution_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    attribution_text: Mapped[str | None] = mapped_column(Text)
    safe_for_commercial_use: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class MusicTrack(Base):
    __tablename__ = "music_tracks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    artist: Mapped[str | None] = mapped_column(String(180))
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(200), nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text)
    license_type: Mapped[str] = mapped_column(String(120), nullable=False)
    mood: Mapped[str] = mapped_column(String(64), nullable=False, default="neutral")
    energy: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    bpm: Mapped[int | None] = mapped_column(Integer)
    duration_seconds: Mapped[float | None] = mapped_column(Float)
    attribution_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    attribution_text: Mapped[str | None] = mapped_column(Text)
    safe_for_monetization: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class Voiceover(Base):
    __tablename__ = "voiceovers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    script_id: Mapped[int] = mapped_column(ForeignKey("scripts.id"), nullable=False, index=True)
    language: Mapped[str] = mapped_column(String(32), nullable=False)
    voice_provider: Mapped[str] = mapped_column(String(64), nullable=False, default="placeholder")
    voice_name: Mapped[str | None] = mapped_column(String(160))
    file_path: Mapped[str | None] = mapped_column(Text)
    duration_seconds: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(48), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    script: Mapped[Script] = relationship(back_populates="voiceovers")


class VoiceoverJob(TimestampMixin, Base):
    __tablename__ = "voiceover_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    video_project_id: Mapped[int | None] = mapped_column(ForeignKey("video_projects.id"), nullable=True, index=True)
    wizard_session_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    script_id: Mapped[int | None] = mapped_column(ForeignKey("scripts.id"), nullable=True, index=True)
    script_draft_id: Mapped[int | None] = mapped_column(ForeignKey("script_drafts.id"), nullable=True, index=True)
    language: Mapped[str] = mapped_column(String(32), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False, default="placeholder")
    voice_name: Mapped[str | None] = mapped_column(String(160))
    voice_id: Mapped[str | None] = mapped_column(String(160))
    model_id: Mapped[str | None] = mapped_column(String(160))
    text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    text_hash: Mapped[str | None] = mapped_column(String(128))
    input_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    output_path: Mapped[str | None] = mapped_column(Text)
    output_audio_path: Mapped[str | None] = mapped_column(Text)
    duration_seconds: Mapped[float | None] = mapped_column(Float)
    character_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(48), nullable=False, default="pending")
    error_message: Mapped[str | None] = mapped_column(Text)
    external_request_id: Mapped[str | None] = mapped_column(String(240))
    cost_event_id: Mapped[int | None] = mapped_column(ForeignKey("cost_events.id"), nullable=True)
    cost_estimate: Mapped[float | None] = mapped_column(Float)
    metadata_json: Mapped[str | None] = mapped_column(Text)


class SubtitleTrack(TimestampMixin, Base):
    __tablename__ = "subtitle_tracks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    video_project_id: Mapped[int | None] = mapped_column(ForeignKey("video_projects.id"), nullable=True, index=True)
    script_id: Mapped[int | None] = mapped_column(ForeignKey("scripts.id"), nullable=True, index=True)
    script_draft_id: Mapped[int | None] = mapped_column(ForeignKey("script_drafts.id"), nullable=True, index=True)
    voiceover_job_id: Mapped[int | None] = mapped_column(ForeignKey("voiceover_jobs.id"), nullable=True)
    language: Mapped[str] = mapped_column(String(32), nullable=False)
    srt_path: Mapped[str | None] = mapped_column(Text)
    ass_path: Mapped[str | None] = mapped_column(Text)
    subtitles_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    status: Mapped[str] = mapped_column(String(48), nullable=False, default="generated")


class VisualPlan(TimestampMixin, Base):
    __tablename__ = "visual_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    script_id: Mapped[int] = mapped_column(ForeignKey("scripts.id"), nullable=False, index=True)
    wizard_session_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    template_name: Mapped[str] = mapped_column(String(80), nullable=False, default="texto_potente")
    global_style: Mapped[str] = mapped_column(Text, nullable=False, default="")
    background_style: Mapped[str] = mapped_column(String(120), nullable=False, default="clean")
    caption_style: Mapped[str] = mapped_column(String(120), nullable=False, default="large_high_contrast")
    scenes_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    status: Mapped[str] = mapped_column(String(48), nullable=False, default="generated")


class CharacterFamily(TimestampMixin, Base):
    __tablename__ = "character_families"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    slug: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)
    canonical_description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    base_visual_style: Mapped[str] = mapped_column(Text, nullable=False, default="")
    base_personality: Mapped[str] = mapped_column(Text, nullable=False, default="")
    global_must_preserve_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    global_must_avoid_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    obsidian_note_path: Mapped[str | None] = mapped_column(Text)


class CharacterProfile(TimestampMixin, Base):
    __tablename__ = "character_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    family_id: Mapped[int | None] = mapped_column(ForeignKey("character_families.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)
    role: Mapped[str] = mapped_column(String(240), nullable=False, default="")
    short_description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    canonical_description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    master_prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    negative_prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    visual_style: Mapped[str] = mapped_column(Text, nullable=False, default="")
    personality: Mapped[str] = mapped_column(Text, nullable=False, default="")
    speaking_style: Mapped[str] = mapped_column(Text, nullable=False, default="")
    default_outfit: Mapped[str] = mapped_column(Text, nullable=False, default="")
    required_traits_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    forbidden_traits_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    color_palette_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    proportions_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    reference_image_paths_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    main_image_path: Mapped[str | None] = mapped_column(Text)
    main_thumbnail_path: Mapped[str | None] = mapped_column(Text)
    must_preserve_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    must_avoid_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    prompt_fragment: Mapped[str] = mapped_column(Text, nullable=False, default="")
    negative_prompt_fragment: Mapped[str] = mapped_column(Text, nullable=False, default="")
    obsidian_note_path: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(48), nullable=False, default="active")
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class CharacterPose(TimestampMixin, Base):
    __tablename__ = "character_poses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    character_id: Mapped[int] = mapped_column(ForeignKey("character_profiles.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    camera_angle: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    body_orientation: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    emotion: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    prompt_fragment: Mapped[str] = mapped_column(Text, nullable=False, default="")
    negative_prompt_fragment: Mapped[str] = mapped_column(Text, nullable=False, default="")
    reference_image_path: Mapped[str | None] = mapped_column(Text)


class CharacterVariant(TimestampMixin, Base):
    __tablename__ = "character_variants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    character_id: Mapped[int] = mapped_column(ForeignKey("character_profiles.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    allowed_changes_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    must_preserve_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    outfit_description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    use_cases_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    prompt_fragment: Mapped[str] = mapped_column(Text, nullable=False, default="")
    negative_prompt_fragment: Mapped[str] = mapped_column(Text, nullable=False, default="")


class CharacterCell(TimestampMixin, Base):
    __tablename__ = "character_cells"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    character_profile_id: Mapped[int] = mapped_column(
        ForeignKey("character_profiles.id"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    slug: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    cell_type: Mapped[str] = mapped_column(String(64), nullable=False, default="other")
    image_path: Mapped[str | None] = mapped_column(Text)
    thumbnail_path: Mapped[str | None] = mapped_column(Text)
    prompt_notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    mime_type: Mapped[str | None] = mapped_column(String(120))
    sha256: Mapped[str | None] = mapped_column(String(128))


class VisualStoryboard(TimestampMixin, Base):
    __tablename__ = "visual_storyboards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    script_id: Mapped[int] = mapped_column(ForeignKey("scripts.id"), nullable=False, index=True)
    character_id: Mapped[int] = mapped_column(ForeignKey("character_profiles.id"), nullable=False, index=True)
    visual_style: Mapped[str] = mapped_column(Text, nullable=False, default="")
    total_scenes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    aspect_ratio: Mapped[str] = mapped_column(String(32), nullable=False, default="9:16")
    target_duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=38)
    global_prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    global_negative_prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(48), nullable=False, default="generated")


class StoryboardScene(TimestampMixin, Base):
    __tablename__ = "storyboard_scenes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    storyboard_id: Mapped[int] = mapped_column(ForeignKey("visual_storyboards.id"), nullable=False, index=True)
    scene_number: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=2.5)
    narration_line: Mapped[str] = mapped_column(Text, nullable=False, default="")
    on_screen_action: Mapped[str] = mapped_column(Text, nullable=False, default="")
    character_pose: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    character_emotion: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    character_variant: Mapped[str | None] = mapped_column(String(160))
    camera_shot: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    camera_motion: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    background: Mapped[str] = mapped_column(Text, nullable=False, default="")
    props_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    visual_effects_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    transition_in: Mapped[str | None] = mapped_column(String(120))
    transition_out: Mapped[str | None] = mapped_column(String(120))
    higgsfield_prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    picsart_processing_notes: Mapped[str | None] = mapped_column(Text)
    negative_prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    required_assets_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    external_asset_id: Mapped[int | None] = mapped_column(ForeignKey("external_assets.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(48), nullable=False, default="generated")


class SceneAssetMapping(TimestampMixin, Base):
    __tablename__ = "scene_asset_mappings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scene_id: Mapped[int] = mapped_column(ForeignKey("storyboard_scenes.id"), nullable=False, index=True)
    external_asset_id: Mapped[int] = mapped_column(ForeignKey("external_assets.id"), nullable=False, index=True)
    usage_type: Mapped[str] = mapped_column(String(80), nullable=False, default="foreground_clip")
    start_time: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    duration: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    fit_mode: Mapped[str] = mapped_column(String(80), nullable=False, default="cover")
    crop_anchor: Mapped[str] = mapped_column(String(80), nullable=False, default="center")
    apply_ken_burns: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notes: Mapped[str | None] = mapped_column(Text)


class RenderPlan(TimestampMixin, Base):
    __tablename__ = "render_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    wizard_session_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    script_id: Mapped[int] = mapped_column(ForeignKey("scripts.id"), nullable=False, index=True)
    voiceover_job_id: Mapped[int | None] = mapped_column(ForeignKey("voiceover_jobs.id"), nullable=True)
    subtitle_track_id: Mapped[int | None] = mapped_column(ForeignKey("subtitle_tracks.id"), nullable=True)
    visual_plan_id: Mapped[int | None] = mapped_column(ForeignKey("visual_plans.id"), nullable=True)
    music_track_id: Mapped[int | None] = mapped_column(ForeignKey("music_tracks.id"), nullable=True)
    output_path: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(48), nullable=False, default="pending")
    error_message: Mapped[str | None] = mapped_column(Text)


class ExternalToolJob(TimestampMixin, Base):
    __tablename__ = "external_tool_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    wizard_session_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    script_id: Mapped[int | None] = mapped_column(ForeignKey("scripts.id"), nullable=True, index=True)
    visual_plan_id: Mapped[int | None] = mapped_column(ForeignKey("visual_plans.id"), nullable=True)
    provider_name: Mapped[str] = mapped_column(String(120), nullable=False)
    provider_type: Mapped[str] = mapped_column(String(64), nullable=False)
    job_type: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(48), nullable=False, default="draft")
    request_json: Mapped[str | None] = mapped_column(Text)
    response_json: Mapped[str | None] = mapped_column(Text)
    output_path: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    estimated_cost: Mapped[float | None] = mapped_column(Float)
    actual_cost: Mapped[float | None] = mapped_column(Float)


class PromptPack(TimestampMixin, Base):
    __tablename__ = "prompt_packs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    wizard_session_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    script_id: Mapped[int] = mapped_column(ForeignKey("scripts.id"), nullable=False, index=True)
    visual_plan_id: Mapped[int | None] = mapped_column(ForeignKey("visual_plans.id"), nullable=True)
    provider_name: Mapped[str] = mapped_column(String(120), nullable=False)
    pack_type: Mapped[str] = mapped_column(String(80), nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    folder_path: Mapped[str] = mapped_column(Text, nullable=False)
    master_prompt_path: Mapped[str | None] = mapped_column(Text)
    scene_prompts_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    negative_prompt: Mapped[str | None] = mapped_column(Text)
    style_reference: Mapped[str | None] = mapped_column(Text)
    instructions_path: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(48), nullable=False, default="generated")


class ExternalAsset(TimestampMixin, Base):
    __tablename__ = "external_assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    wizard_session_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    script_id: Mapped[int | None] = mapped_column(ForeignKey("scripts.id"), nullable=True, index=True)
    visual_plan_id: Mapped[int | None] = mapped_column(ForeignKey("visual_plans.id"), nullable=True)
    scene_order: Mapped[int | None] = mapped_column(Integer)
    provider_name: Mapped[str | None] = mapped_column(String(120))
    asset_type: Mapped[str] = mapped_column(String(64), nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str | None] = mapped_column(String(200))
    source_url: Mapped[str | None] = mapped_column(Text)
    license_type: Mapped[str | None] = mapped_column(String(120))
    license_notes: Mapped[str | None] = mapped_column(Text)
    commercial_use_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    duration_seconds: Mapped[float | None] = mapped_column(Float)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    fps: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(48), nullable=False, default="needs_license_review")


class ResearchRun(TimestampMixin, Base):
    __tablename__ = "research_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    idea_count_requested: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    lookback_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    target_market: Mapped[str] = mapped_column(String(80), nullable=False, default="global")
    content_language: Mapped[str] = mapped_column(String(32), nullable=False, default="en")
    status: Mapped[str] = mapped_column(String(48), nullable=False, default="created")
    error_message: Mapped[str | None] = mapped_column(Text)
    provider_summary_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")


class ProviderFetchLog(TimestampMixin, Base):
    __tablename__ = "provider_fetch_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    research_run_id: Mapped[int] = mapped_column(ForeignKey("research_runs.id"), nullable=False, index=True)
    provider_name: Mapped[str] = mapped_column(String(120), nullable=False)
    request_payload_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    response_summary_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    raw_response_path: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(48), nullable=False, default="created")
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TrendItem(TimestampMixin, Base):
    __tablename__ = "trend_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    research_run_id: Mapped[int] = mapped_column(ForeignKey("research_runs.id"), nullable=False, index=True)
    provider_name: Mapped[str] = mapped_column(String(120), nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(240))
    url: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    author_or_channel: Mapped[str | None] = mapped_column(String(240))
    views: Mapped[int | None] = mapped_column(Integer)
    likes: Mapped[int | None] = mapped_column(Integer)
    comments: Mapped[int | None] = mapped_column(Integer)
    shares: Mapped[int | None] = mapped_column(Integer)
    duration_seconds: Mapped[float | None] = mapped_column(Float)
    language: Mapped[str | None] = mapped_column(String(32))
    region: Mapped[str | None] = mapped_column(String(80))
    raw_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    viral_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    velocity_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    engagement_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    novelty_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    visual_potential_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    shorts_suitability_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    risk_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    source_reliability_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)


class IdeaCandidate(TimestampMixin, Base):
    __tablename__ = "idea_candidates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    research_run_id: Mapped[int] = mapped_column(ForeignKey("research_runs.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    short_description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    viral_angle: Mapped[str] = mapped_column(Text, nullable=False, default="")
    why_now: Mapped[str] = mapped_column(Text, nullable=False, default="")
    visual_potential: Mapped[str] = mapped_column(Text, nullable=False, default="")
    estimated_duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    source_item_ids_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    risk_level: Mapped[str] = mapped_column(String(32), nullable=False, default="low")
    risk_notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(48), nullable=False, default="suggested")


class CreationInboxItem(TimestampMixin, Base):
    __tablename__ = "creation_inbox_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    idea_candidate_id: Mapped[int] = mapped_column(ForeignKey("idea_candidates.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(48), nullable=False, default="pending")
    notes: Mapped[str | None] = mapped_column(Text)


class DeepResearchRun(TimestampMixin, Base):
    __tablename__ = "deep_research_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    idea_candidate_id: Mapped[int] = mapped_column(ForeignKey("idea_candidates.id"), nullable=False, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(48), nullable=False, default="created")
    error_message: Mapped[str | None] = mapped_column(Text)


class DeepIdeaCandidate(TimestampMixin, Base):
    __tablename__ = "deep_idea_candidates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    deep_research_run_id: Mapped[int] = mapped_column(
        ForeignKey("deep_research_runs.id"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    detailed_description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    specific_angle: Mapped[str] = mapped_column(Text, nullable=False, default="")
    why_it_can_go_viral: Mapped[str] = mapped_column(Text, nullable=False, default="")
    possible_hook: Mapped[str] = mapped_column(Text, nullable=False, default="")
    facts_to_verify_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    visual_opportunities_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    risk_level: Mapped[str] = mapped_column(String(32), nullable=False, default="low")
    risk_notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(48), nullable=False, default="suggested")


class MetadataRecipeDraft(TimestampMixin, Base):
    __tablename__ = "metadata_recipe_drafts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    deep_idea_candidate_id: Mapped[int] = mapped_column(
        ForeignKey("deep_idea_candidates.id"),
        nullable=False,
        index=True,
    )
    titles_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    hooks_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    descriptions_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    hashtag_sets_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    selected_title: Mapped[str | None] = mapped_column(Text)
    selected_hook: Mapped[str | None] = mapped_column(Text)
    selected_description: Mapped[str | None] = mapped_column(Text)
    selected_hashtags_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    status: Mapped[str] = mapped_column(String(48), nullable=False, default="draft")


class VideoProject(TimestampMixin, Base):
    __tablename__ = "video_projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    deep_idea_candidate_id: Mapped[int | None] = mapped_column(
        ForeignKey("deep_idea_candidates.id"),
        nullable=True,
        index=True,
    )
    metadata_recipe_id: Mapped[int | None] = mapped_column(
        ForeignKey("metadata_recipe_drafts.id"),
        nullable=True,
        index=True,
    )
    character_profile_id: Mapped[int | None] = mapped_column(
        ForeignKey("character_profiles.id"),
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    hashtags_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    hook: Mapped[str] = mapped_column(Text, nullable=False, default="")
    content_language: Mapped[str] = mapped_column(String(32), nullable=False, default="en")
    ui_language: Mapped[str] = mapped_column(String(32), nullable=False, default="es")
    target_market: Mapped[str] = mapped_column(String(80), nullable=False, default="global")
    target_duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    max_duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=90)
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="metadata_selected")


class ScriptDraft(TimestampMixin, Base):
    __tablename__ = "script_drafts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    video_project_id: Mapped[int] = mapped_column(ForeignKey("video_projects.id"), nullable=False, index=True)
    language: Mapped[str] = mapped_column(String(32), nullable=False, default="en")
    voiceover_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    estimated_duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    estimated_words: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    beats_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    fact_check_notes_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    risk_notes_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    status: Mapped[str] = mapped_column(String(48), nullable=False, default="script_draft")


class SceneSlot(TimestampMixin, Base):
    __tablename__ = "scene_slots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    video_project_id: Mapped[int] = mapped_column(ForeignKey("video_projects.id"), nullable=False, index=True)
    slot_number: Mapped[int] = mapped_column(Integer, nullable=False)
    slot_type: Mapped[str] = mapped_column(String(80), nullable=False, default="scene")
    target_start_second: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    target_end_second: Mapped[float] = mapped_column(Float, nullable=False, default=8.0)
    voiceover_segment: Mapped[str] = mapped_column(Text, nullable=False, default="")


class SceneCandidate(TimestampMixin, Base):
    __tablename__ = "scene_candidates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scene_slot_id: Mapped[int] = mapped_column(ForeignKey("scene_slots.id"), nullable=False, index=True)
    option_code: Mapped[str] = mapped_column(String(24), nullable=False)
    duration_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=8.0)
    visual_description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    character_action: Mapped[str] = mapped_column(Text, nullable=False, default="")
    camera_movement: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    setting: Mapped[str] = mapped_column(Text, nullable=False, default="")
    continuity_in: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    continuity_out: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    compatible_next_states_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    required_character_cell_ids_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(48), nullable=False, default="suggested")


class SelectedScene(TimestampMixin, Base):
    __tablename__ = "selected_scenes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    video_project_id: Mapped[int] = mapped_column(ForeignKey("video_projects.id"), nullable=False, index=True)
    scene_slot_id: Mapped[int] = mapped_column(ForeignKey("scene_slots.id"), nullable=False, index=True)
    scene_candidate_id: Mapped[int] = mapped_column(
        ForeignKey("scene_candidates.id"),
        nullable=False,
        index=True,
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(48), nullable=False, default="selected")


class HiggsfieldPromptPack(TimestampMixin, Base):
    __tablename__ = "higgsfield_prompt_packs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    video_project_id: Mapped[int] = mapped_column(ForeignKey("video_projects.id"), nullable=False, index=True)
    selected_scene_id: Mapped[int] = mapped_column(ForeignKey("selected_scenes.id"), nullable=False, index=True)
    prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    negative_prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    reference_images_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    camera_movement: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    style_notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    consistency_notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    aspect_ratio: Mapped[str] = mapped_column(String(32), nullable=False, default="9:16")
    duration_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=8.0)
    status: Mapped[str] = mapped_column(String(48), nullable=False, default="generated")


class HiggsfieldJob(TimestampMixin, Base):
    __tablename__ = "higgsfield_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    video_project_id: Mapped[int] = mapped_column(ForeignKey("video_projects.id"), nullable=False, index=True)
    selected_scene_id: Mapped[int] = mapped_column(ForeignKey("selected_scenes.id"), nullable=False, index=True)
    prompt_pack_id: Mapped[int] = mapped_column(
        ForeignKey("higgsfield_prompt_packs.id"),
        nullable=False,
        index=True,
    )
    automation_mode: Mapped[str] = mapped_column(String(48), nullable=False, default="manual")
    external_job_id: Mapped[str | None] = mapped_column(String(240))
    submitted_payload_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    raw_output_path: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(48), nullable=False, default="created")
    error_message: Mapped[str | None] = mapped_column(Text)
    estimated_credits: Mapped[float | None] = mapped_column(Float)
    actual_credits: Mapped[float | None] = mapped_column(Float)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class GeneratedClip(TimestampMixin, Base):
    __tablename__ = "generated_clips"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    video_project_id: Mapped[int] = mapped_column(ForeignKey("video_projects.id"), nullable=False, index=True)
    selected_scene_id: Mapped[int] = mapped_column(ForeignKey("selected_scenes.id"), nullable=False, index=True)
    higgsfield_job_id: Mapped[int | None] = mapped_column(ForeignKey("higgsfield_jobs.id"), nullable=True)
    source: Mapped[str] = mapped_column(String(80), nullable=False, default="manual")
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    thumbnail_path: Mapped[str | None] = mapped_column(Text)
    duration_seconds: Mapped[float | None] = mapped_column(Float)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    fps: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(48), nullable=False, default="registered")


class RenderJob(TimestampMixin, Base):
    __tablename__ = "render_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    video_project_id: Mapped[int] = mapped_column(ForeignKey("video_projects.id"), nullable=False, index=True)
    output_path: Mapped[str | None] = mapped_column(Text)
    width: Mapped[int] = mapped_column(Integer, nullable=False, default=1080)
    height: Mapped[int] = mapped_column(Integer, nullable=False, default=1920)
    fps: Mapped[float] = mapped_column(Float, nullable=False, default=30.0)
    duration_seconds: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(48), nullable=False, default="pending")
    error_message: Mapped[str | None] = mapped_column(Text)


class ObsidianSyncLog(TimestampMixin, Base):
    __tablename__ = "obsidian_sync_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    note_path: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(48), nullable=False, default="created")
    error_message: Mapped[str | None] = mapped_column(Text)


class CostEvent(Base):
    __tablename__ = "cost_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider_name: Mapped[str] = mapped_column(String(120), nullable=False)
    operation: Mapped[str] = mapped_column(String(120), nullable=False)
    model: Mapped[str | None] = mapped_column(String(160))
    estimated_cost: Mapped[float | None] = mapped_column(Float)
    actual_cost: Mapped[float | None] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(12), nullable=False, default="USD")
    units_type: Mapped[str | None] = mapped_column(String(64))
    input_units: Mapped[float | None] = mapped_column(Float)
    output_units: Mapped[float | None] = mapped_column(Float)
    metadata_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class Render(Base):
    __tablename__ = "renders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    script_id: Mapped[int] = mapped_column(ForeignKey("scripts.id"), nullable=False, index=True)
    channel_id: Mapped[int | None] = mapped_column(ForeignKey("channels.id"), index=True)
    language: Mapped[str] = mapped_column(String(32), nullable=False)
    template_name: Mapped[str] = mapped_column(String(80), nullable=False, default="clean_text_focus")
    video_path: Mapped[str | None] = mapped_column(Text)
    thumbnail_path: Mapped[str | None] = mapped_column(Text)
    duration_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=38.0)
    resolution: Mapped[str] = mapped_column(String(32), nullable=False, default="1080x1920")
    status: Mapped[str] = mapped_column(String(48), nullable=False, default="pending")
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    script: Mapped[Script] = relationship(back_populates="renders")
    channel: Mapped[Channel | None] = relationship(back_populates="renders")
    checklist: Mapped[ReviewChecklist | None] = relationship(
        back_populates="render",
        cascade="all, delete-orphan",
    )
    export_package: Mapped[ExportPackage | None] = relationship(
        back_populates="render",
        cascade="all, delete-orphan",
    )


class ReviewChecklist(Base):
    __tablename__ = "review_checklists"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    render_id: Mapped[int] = mapped_column(ForeignKey("renders.id"), nullable=False, unique=True)
    hook_strong: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    script_fact_checked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    language_natural: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    music_license_ok: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    assets_license_ok: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    no_reused_content_risk: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    no_sensitive_content: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    subtitles_readable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    audio_clear: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    video_not_too_repetitive: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    metadata_not_misleading: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    made_for_kids_false_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    synthetic_media_reviewed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    review_notes: Mapped[str | None] = mapped_column(Text)
    approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    render: Mapped[Render] = relationship(back_populates="checklist")


class ExportPackage(Base):
    __tablename__ = "export_packages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    render_id: Mapped[int] = mapped_column(ForeignKey("renders.id"), nullable=False, unique=True)
    export_folder: Mapped[str] = mapped_column(Text, nullable=False)
    video_file: Mapped[str] = mapped_column(Text, nullable=False)
    title_file: Mapped[str] = mapped_column(Text, nullable=False)
    description_file: Mapped[str] = mapped_column(Text, nullable=False)
    hashtags_file: Mapped[str] = mapped_column(Text, nullable=False)
    script_file: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_file: Mapped[str] = mapped_column(Text, nullable=False)
    checklist_file: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    manual_youtube_url: Mapped[str | None] = mapped_column(Text)

    render: Mapped[Render] = relationship(back_populates="export_package")
