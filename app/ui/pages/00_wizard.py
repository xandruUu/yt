from __future__ import annotations

import json
from pathlib import Path

import streamlit as st
from sqlalchemy import select

from app.config.settings import get_settings
from app.core.enums import (
    GeneratedIdeaStatus,
    RenderPlanStatus,
    SubtitleTrackStatus,
    VisualPlanStatus,
    VoiceoverJobStatus,
    WizardStep,
)
from app.core.wizard import WIZARD_STEPS, next_step, previous_step, wizard_progress
from app.db import models
from app.db.database import new_session
from app.db.repositories import set_selected_hook, set_selected_title
from app.i18n.es import (
    CATEGORY_LABELS,
    LANGUAGE_LABELS_ES,
    MARKET_LABELS,
    WIZARD_STEP_DESCRIPTIONS,
    WIZARD_STEP_LABELS,
    label_for,
)
from app.providers.base import TrendItem
from app.render.advanced_renderer import render_from_plan
from app.services.character_service import (
    character_bible_markdown,
    list_character_poses,
    list_character_variants,
    seed_nero_character_system,
)
from app.services.cost_tracking_service import estimate_cost
from app.services.hook_generation_service import generate_hooks_for_topic
from app.services.idea_generation_service import (
    convert_generated_idea_to_topic,
    generate_ideas_from_trends,
    persist_generated_ideas,
)
from app.services.metadata_generation_service import generate_metadata
from app.services.music_service import suggest_music_for_script
from app.services.render_plan_service import (
    approve_render_plan,
    create_short_render_plan,
    mark_render_plan_ready,
    validate_render_plan,
)
from app.services.scene_asset_mapping_service import storyboard_render_manifest
from app.services.script_generation_service import (
    DURATION_OPTIONS,
    SCRIPT_FORMATS,
    approve_script,
    generate_script,
)
from app.services.storyboard_prompt_pack_service import create_nero_higgsfield_prompt_pack
from app.services.storyboard_service import (
    VisualStoryboardService,
    list_storyboard_scenes,
    list_storyboards_for_script,
)
from app.services.subtitle_alignment_service import (
    approve_subtitles,
    export_srt,
    generate_subtitles_from_script,
    update_subtitle_track_from_rows,
)
from app.services.title_generation_service import generate_titles_for_hook
from app.services.trend_research_service import TrendResearchService
from app.services.visual_plan_service import (
    approve_visual_plan,
    generate_visual_plan,
    visual_plan_scenes,
)
from app.services.voiceover_generation_service import (
    approve_voiceover,
    create_voiceover_from_script,
    import_manual_voiceover,
    list_tts_provider_statuses,
)
from app.ui.components.generated_idea_cards import generated_idea_card_data

SESSION_STEP_KEY = "shorts_factory_wizard_step"
SESSION_APPROVED_KEY = "shorts_factory_wizard_approved_steps"
SESSION_DRAFT_KEY = "shorts_factory_wizard_draft"
SESSION_GENERATED_IDEAS_KEY = "wizard_generated_idea_ids"
SESSION_SELECTED_GENERATED_IDEA_KEY = "wizard_selected_generated_idea_id"
SESSION_SELECTED_TOPIC_KEY = "wizard_selected_topic_id"
SESSION_GENERATED_HOOKS_KEY = "wizard_generated_hook_ids"
SESSION_SELECTED_HOOK_KEY = "wizard_selected_hook_id"
SESSION_GENERATED_TITLES_KEY = "wizard_generated_title_ids"
SESSION_SELECTED_TITLE_KEY = "wizard_selected_title_id"
SESSION_SELECTED_METADATA_KEY = "wizard_selected_metadata_id"
SESSION_SELECTED_SCRIPT_KEY = "wizard_selected_script_id"
SESSION_SELECTED_VOICEOVER_KEY = "wizard_selected_voiceover_job_id"
SESSION_SELECTED_SUBTITLE_TRACK_KEY = "wizard_selected_subtitle_track_id"
SESSION_SELECTED_MUSIC_KEY = "wizard_selected_music_track_id"
SESSION_SELECTED_VISUAL_PLAN_KEY = "wizard_selected_visual_plan_id"
SESSION_SELECTED_RENDER_PLAN_KEY = "wizard_selected_render_plan_id"
SESSION_SELECTED_CHARACTER_KEY = "wizard_selected_character_id"
SESSION_SELECTED_STORYBOARD_KEY = "wizard_selected_storyboard_id"
SESSION_SELECTED_PROMPT_PACK_KEY = "wizard_selected_prompt_pack_id"


def render() -> None:
    _ensure_state()
    current_step = WizardStep(st.session_state[SESSION_STEP_KEY])
    current_definition = next(item for item in WIZARD_STEPS if item.step == current_step)

    st.title("Crear Short paso a paso")
    st.progress(wizard_progress(current_step), text=f"Paso {current_definition.index}/{len(WIZARD_STEPS)}")

    step_options = [definition.step.value for definition in WIZARD_STEPS]
    selected_step = st.selectbox(
        "Paso actual",
        step_options,
        index=step_options.index(current_step.value),
        format_func=lambda value: label_for(WIZARD_STEP_LABELS, WizardStep(value)),
    )
    if selected_step != current_step.value:
        st.session_state[SESSION_STEP_KEY] = selected_step
        st.rerun()

    st.subheader(label_for(WIZARD_STEP_LABELS, current_step))
    st.caption(WIZARD_STEP_DESCRIPTIONS[current_step])

    _render_step(current_step)
    st.divider()
    _render_controls(current_step)


def _ensure_state() -> None:
    st.session_state.setdefault(SESSION_STEP_KEY, WizardStep.BASIC_DATA.value)
    st.session_state.setdefault(SESSION_APPROVED_KEY, set())
    st.session_state.setdefault(SESSION_GENERATED_IDEAS_KEY, [])
    st.session_state.setdefault(SESSION_GENERATED_HOOKS_KEY, [])
    st.session_state.setdefault(SESSION_GENERATED_TITLES_KEY, [])
    st.session_state.setdefault(
        SESSION_DRAFT_KEY,
        {
            "language": "en",
            "market": "global",
            "category": "science_explained",
            "idea_count": 8,
            "duration": "30-45 segundos",
            "script_format": "Documental rápido",
            "voice_mode": "Sin voz automática",
            "visual_style": "Texto potente",
            "providers": ["manual"],
            "query": "",
            "manual_input": "",
            "channel": "Daily Brain Break",
            "character_slug": "nero",
        },
    )


def _render_step(step: WizardStep) -> None:
    if step == WizardStep.BASIC_DATA:
        _render_basic_data_step()
    elif step == WizardStep.RESEARCH:
        _render_research_step()
    elif step == WizardStep.IDEA_SELECTION:
        _render_idea_selection_step()
    elif step == WizardStep.HOOK_SELECTION:
        _render_hook_selection_step()
        return
        _render_card_grid(
            [
                ("Ganchos", "Misterio, error, utilidad, sorpresa y dinero/impacto si aplica."),
                ("Ajustes", "Más seguros, más cortos, más dramáticos o más educativos."),
            ]
        )
    elif step == WizardStep.TITLE_SELECTION:
        _render_title_selection_step()
        return
        _render_card_grid(
            [
                ("Títulos", "Cortos, curiosos, SEO, documentales y por idioma."),
                ("Control de riesgo", "Longitud, claridad, CTR estimado y clickbait."),
            ]
        )
    elif step == WizardStep.METADATA:
        _render_metadata_step()
    elif step == WizardStep.SCRIPT_GENERATION:
        _render_script_generation_step()
        return
        draft = st.session_state[SESSION_DRAFT_KEY]
        col1, col2 = st.columns(2)
        draft["script_format"] = col1.selectbox(
            "Formato",
            [
                "Documental rápido",
                "Historia con giro",
                "Explicación técnica simple",
                "Caso real",
                "Lista rápida",
                "Problema-solución",
                "Lo que nadie te explica",
                "Mini storytelling",
            ],
            index=0,
        )
        draft["duration"] = col2.selectbox(
            "Duración objetivo",
            ["20-30 segundos", "30-45 segundos", "45-60 segundos", "60-90 segundos", "90-180 segundos"],
            index=1,
        )
        st.session_state[SESSION_DRAFT_KEY] = draft
        st.info("El editor por líneas se conectará al paso de Guiones en la siguiente iteración.")
    elif step == WizardStep.LOCALIZATION:
        st.info("Las versiones EN/ES/HI se conectarán al generador de localización automática.")
    elif step == WizardStep.CHARACTER:
        _render_character_step()
    elif step == WizardStep.STORYBOARD:
        _render_storyboard_step()
    elif step == WizardStep.PROMPT_PACK:
        _render_prompt_pack_step()
    elif step == WizardStep.VOICEOVER:
        _render_voiceover_step()
        return
        draft = st.session_state[SESSION_DRAFT_KEY]
        draft["voice_mode"] = st.radio(
            "Modo de voz",
            ["Sin voz automática", "TTS local/gratuito opcional", "Proveedor externo opcional"],
        )
        st.session_state[SESSION_DRAFT_KEY] = draft
    elif step == WizardStep.MUSIC_SELECTION:
        _render_subtitles_music_step()
        return
        st.info("La selección usará solo música registrada en assets/music con licencia clara.")
    elif step == WizardStep.CLIP_IMPORT:
        st.info("Importa clips desde Herramientas externas > Clips y confirma licencia/uso comercial.")
    elif step == WizardStep.SCENE_MAPPING:
        _render_scene_mapping_step()
    elif step == WizardStep.VISUAL_STYLE:
        _render_visual_plan_step()
        return
        draft = st.session_state[SESSION_DRAFT_KEY]
        draft["visual_style"] = st.selectbox(
            "Plantilla visual",
            ["Texto potente", "Documental oscuro", "Tech/IA", "Educativo minimalista", "Misterio"],
        )
        st.session_state[SESSION_DRAFT_KEY] = draft
    elif step == WizardStep.RENDER:
        _render_render_step()
        return
        st.info("Este paso enlazará con Renderizar cuando exista guion aprobado.")
    elif step == WizardStep.REVIEW:
        st.info("La checklist final se mantiene obligatoria antes de exportar.")
    elif step == WizardStep.EXPORT:
        st.info("La exportación seguirá creando el paquete para subida manual, sin API de YouTube.")


def _render_basic_data_step() -> None:
    draft = st.session_state[SESSION_DRAFT_KEY]
    with new_session() as session:
        character = seed_nero_character_system(session)
        st.session_state[SESSION_SELECTED_CHARACTER_KEY] = character.id
    col1, col2, col3 = st.columns(3)
    draft["channel"] = col1.text_input("Canal", value=draft.get("channel", "Daily Brain Break"))
    draft["language"] = col2.selectbox(
        "Idioma objetivo",
        ["en", "es", "hi_hinglish"],
        index=["en", "es", "hi_hinglish"].index(draft.get("language", "en")),
        format_func=lambda value: label_for(LANGUAGE_LABELS_ES, value),
    )
    draft["market"] = col3.selectbox(
        "Mercado",
        ["global", "us", "spain", "latam", "india", "spain_latam"],
        index=["global", "us", "spain", "latam", "india", "spain_latam"].index(draft.get("market", "global")),
        format_func=lambda value: label_for(MARKET_LABELS, value),
    )
    st.session_state[SESSION_DRAFT_KEY] = draft
    st.success("Nero esta configurado como personaje default para Daily Brain Break.")


def _render_metadata_step() -> None:
    metadata_id = st.session_state.get(SESSION_SELECTED_METADATA_KEY)
    if metadata_id:
        with new_session() as session:
            metadata = session.get(models.MetadataSuggestion, metadata_id)
            if metadata:
                st.success(f"Metadata seleccionada #{metadata.id}")
                st.write(metadata.description)
                st.caption(metadata.hashtags_json)
                return
    st.info("Genera y elige metadata desde el paso Titulos. Este paso queda como control editorial antes del guion.")


def _render_character_step() -> None:
    with new_session() as session:
        character = seed_nero_character_system(session)
        st.session_state[SESSION_SELECTED_CHARACTER_KEY] = character.id
        poses = list_character_poses(session, character.id)
        variants = list_character_variants(session, character.id)
        st.markdown(f"**{character.name}** - {character.role}")
        st.write(character.short_description)
        st.text_area("Master prompt", value=character.master_prompt, height=180, disabled=True)
        st.text_area("Negative prompt", value=character.negative_prompt, height=160, disabled=True)
        with st.expander("Character Bible"):
            st.markdown(character_bible_markdown(character, poses, variants))
        st.dataframe(
            [{"pose": pose.name, "emotion": pose.emotion, "camera": pose.camera_angle} for pose in poses],
            use_container_width=True,
            hide_index=True,
        )
        st.dataframe(
            [{"variant": variant.name, "description": variant.description} for variant in variants],
            use_container_width=True,
            hide_index=True,
        )


def _render_storyboard_step() -> None:
    with new_session() as session:
        script = _load_selected_approved_script(session)
        if script is None:
            st.info("Aprueba un guion antes de generar el storyboard de Nero.")
            return
        character = seed_nero_character_system(session)
        st.caption(f"Guion aprobado: #{script.id} | Personaje: {character.name}")
        if st.button("Generar storyboard visual de Nero", type="primary"):
            storyboard = VisualStoryboardService().create_from_script(
                session,
                script_id=script.id,
                character_id=character.id,
                overwrite_existing=True,
            )
            st.session_state[SESSION_SELECTED_STORYBOARD_KEY] = storyboard.id
            st.success(f"VisualStoryboard #{storyboard.id} generado.")
            st.rerun()
        storyboards = list_storyboards_for_script(session, script.id)
        if not storyboards:
            st.info("Todavia no hay storyboards para este guion.")
            return
        selected_id = st.session_state.get(SESSION_SELECTED_STORYBOARD_KEY) or storyboards[0].id
        storyboard = session.get(models.VisualStoryboard, selected_id) or storyboards[0]
        st.session_state[SESSION_SELECTED_STORYBOARD_KEY] = storyboard.id
        st.subheader(f"Storyboard #{storyboard.id}")
        st.caption(f"Estado: {storyboard.status} | Escenas: {storyboard.total_scenes}")
        for scene in list_storyboard_scenes(session, storyboard.id):
            with st.container(border=True):
                st.markdown(f"**Escena {scene.scene_number:02}** - {scene.duration_seconds:.2f}s")
                st.write(scene.narration_line)
                st.caption(f"{scene.character_variant or 'Nero default'} | {scene.character_pose} | {scene.character_emotion}")
                st.text_area("Prompt Higgsfield", value=scene.higgsfield_prompt, height=180, key=f"wizard_scene_prompt_{scene.id}")
                if st.button("Aprobar escena", key=f"wizard_approve_scene_{scene.id}"):
                    VisualStoryboardService().approve_scene(session, scene.id)
                    st.rerun()


def _render_prompt_pack_step() -> None:
    storyboard_id = st.session_state.get(SESSION_SELECTED_STORYBOARD_KEY)
    with new_session() as session:
        if storyboard_id is None:
            script = _load_selected_approved_script(session)
            if script:
                storyboards = list_storyboards_for_script(session, script.id)
                storyboard_id = storyboards[0].id if storyboards else None
        if storyboard_id is None:
            st.info("Genera un storyboard antes de exportar prompts.")
            return
        storyboard = session.get(models.VisualStoryboard, storyboard_id)
        if storyboard is None:
            st.info("Storyboard no encontrado.")
            return
        st.caption(f"Storyboard seleccionado: #{storyboard.id}")
        if st.button("Exportar prompt pack Nero", type="primary"):
            pack = create_nero_higgsfield_prompt_pack(session, storyboard_id=storyboard.id, overwrite=True)
            st.session_state[SESSION_SELECTED_PROMPT_PACK_KEY] = pack.id
            st.success(f"PromptPack #{pack.id} exportado.")
            st.code(pack.folder_path)
        pack_id = st.session_state.get(SESSION_SELECTED_PROMPT_PACK_KEY)
        if pack_id:
            pack = session.get(models.PromptPack, pack_id)
            if pack:
                st.code(pack.folder_path)


def _render_scene_mapping_step() -> None:
    storyboard_id = st.session_state.get(SESSION_SELECTED_STORYBOARD_KEY)
    if storyboard_id is None:
        st.info("Genera un storyboard antes de mapear clips.")
        return
    with new_session() as session:
        manifest = storyboard_render_manifest(session, storyboard_id, allow_fallback=True)
        for warning in manifest["warnings"]:
            st.warning(warning)
        for error in manifest["errors"]:
            st.error(error)
        st.json(manifest, expanded=False)
        st.caption("Para asignar clips usa la pantalla Mapeo de clips.")


def _render_research_step() -> None:
    draft = st.session_state[SESSION_DRAFT_KEY]
    col1, col2, col3, col4 = st.columns(4)
    draft["language"] = col1.selectbox(
        "Idioma objetivo",
        ["en", "es", "hi_hinglish"],
        index=["en", "es", "hi_hinglish"].index(draft["language"]),
        format_func=lambda value: label_for(LANGUAGE_LABELS_ES, value),
    )
    draft["market"] = col2.selectbox(
        "Mercado",
        ["global", "us", "spain", "latam", "india", "spain_latam"],
        index=["global", "us", "spain", "latam", "india", "spain_latam"].index(draft["market"]),
        format_func=lambda value: label_for(MARKET_LABELS, value),
    )
    category_values = list(CATEGORY_LABELS)
    draft["category"] = col3.selectbox(
        "Categoría",
        category_values,
        index=category_values.index(draft["category"]),
        format_func=lambda value: label_for(CATEGORY_LABELS, value),
    )
    draft["idea_count"] = col4.number_input("Ideas a investigar", min_value=3, max_value=25, value=8)
    draft["providers"] = st.multiselect(
        "Fuentes",
        ["manual", "rss", "hackernews", "youtube"],
        default=draft.get("providers", ["manual"]),
        format_func=_provider_label,
    )
    draft["query"] = st.text_input("Query opcional", value=draft.get("query", ""))
    draft["manual_input"] = st.text_area(
        "Señales manuales",
        value=draft.get("manual_input", ""),
        height=160,
        placeholder="Pega titulares, URLs o ideas, una por línea...",
    )
    st.session_state[SESSION_DRAFT_KEY] = draft

    if st.button("Investigar ideas", type="primary"):
        result = TrendResearchService().research(
            providers=draft["providers"],
            query=draft["query"] or None,
            market=draft["market"],
            language=draft["language"],
            category=draft["category"],
            limit=int(draft["idea_count"]),
            manual_input=draft["manual_input"],
        )
        st.session_state["wizard_trend_items"] = [item.model_dump(mode="json") for item in result.items]
        st.session_state["wizard_trend_warnings"] = result.warnings
        st.success(f"Investigación completada: {len(result.items)} tendencias.")

    st.json(draft, expanded=False)
    _render_trend_results("wizard_trend_items")
    _render_generate_ideas_controls()


def _render_hook_selection_step() -> None:
    draft = st.session_state[SESSION_DRAFT_KEY]
    with new_session() as session:
        topic = _ensure_wizard_topic(session)
        if topic is None:
            st.info("Elige una idea en el paso anterior antes de generar ganchos.")
            return

        st.caption(f"Idea principal: #{topic.id} {topic.title}")
        col1, col2, col3 = st.columns(3)
        language = col1.selectbox(
            "Idioma",
            ["en", "es", "hi_hinglish"],
            index=["en", "es", "hi_hinglish"].index(draft["language"]),
            format_func=lambda value: label_for(LANGUAGE_LABELS_ES, value),
            key="wizard_hook_language",
        )
        market = col2.text_input("Mercado", value=draft["market"], key="wizard_hook_market")
        provider_name = col3.selectbox(
            "Provider IA",
            ["manual", "ollama", "openai"],
            index=0,
            format_func=lambda value: {"manual": "Manual/gratis", "ollama": "Ollama local", "openai": "OpenAI opcional"}.get(value, value),
            key="wizard_hook_provider",
        )
        style = st.segmented_control(
            "Modo",
            options=["balanced", "safer", "shorter", "documentary", "aggressive"],
            default="balanced",
            format_func=lambda value: {
                "balanced": "Equilibrado",
                "safer": "Mas seguros",
                "shorter": "Mas cortos",
                "documentary": "Mas documentales",
                "aggressive": "Mas agresivos",
            }.get(value, value),
            key="wizard_hook_style",
        )
        if st.button("Generar 25 hooks automaticamente", type="primary", key="wizard_generate_hooks"):
            result = generate_hooks_for_topic(
                session,
                topic,
                language=language,
                market=market,
                provider_name=provider_name,
                style=style or "balanced",
                save=True,
            )
            st.session_state[SESSION_GENERATED_HOOKS_KEY] = result.saved_hook_ids
            for warning in result.warnings:
                st.warning(warning)
            with st.expander("Prompt manual opcional"):
                st.text_area("Prompt", result.prompt, height=260, key="wizard_hook_prompt_preview")
            st.success(f"Se generaron {len(result.saved_hook_ids)} hooks. Elige uno para continuar.")

        hooks = _load_hooks_for_topic(session, topic.id)
        if not hooks:
            st.info("Todavia no hay hooks generados para esta idea.")
            return

        selected_hook_id = st.session_state.get(SESSION_SELECTED_HOOK_KEY)
        if selected_hook_id:
            st.success(f"Gancho elegido: Hook #{selected_hook_id}.")

        st.subheader("Hooks candidatos")
        for hook in hooks:
            _render_hook_card(session, hook, key_prefix="wizard")


def _ensure_wizard_topic(session) -> models.Topic | None:
    topic_id = st.session_state.get(SESSION_SELECTED_TOPIC_KEY)
    if topic_id:
        topic = session.get(models.Topic, topic_id)
        if topic:
            return topic

    idea_id = st.session_state.get(SESSION_SELECTED_GENERATED_IDEA_KEY)
    if not idea_id:
        return None
    idea = session.get(models.GeneratedIdea, idea_id)
    if idea is None:
        return None
    topic = convert_generated_idea_to_topic(session, idea)
    st.session_state[SESSION_SELECTED_TOPIC_KEY] = topic.id
    return topic


def _load_hooks_for_topic(session, topic_id: int) -> list[models.Hook]:
    hook_ids = list(st.session_state.get(SESSION_GENERATED_HOOKS_KEY, []))
    statement = select(models.Hook).where(models.Hook.topic_id == topic_id)
    if hook_ids:
        statement = statement.where(models.Hook.id.in_(hook_ids))
    statement = statement.order_by(models.Hook.created_at.desc())
    return list(session.scalars(statement).all())


def _render_hook_card(session, hook: models.Hook, key_prefix: str) -> None:
    note_data = _hook_note_data(hook.notes)
    total_score = note_data.get("total_score", "-")
    with st.container(border=True):
        st.markdown(f"**{hook.text}**")
        st.caption(f"Tipo: {hook.hook_type} | Score total: {total_score} | Elegido: {hook.selected}")
        cols = st.columns(4)
        cols[0].metric("Claridad", hook.clarity_score)
        cols[1].metric("Curiosidad", hook.curiosity_score)
        cols[2].metric("Emocion", hook.emotion_score)
        cols[3].metric("Riesgo", hook.risk_score)
        if note_data:
            with st.expander("Por que funciona"):
                st.write(note_data.get("why_it_works", "Sin detalle."))
                st.write(f"Visual primer segundo: {note_data.get('first_second_visual', 'No definido')}")
        if st.button("Elegir gancho", key=f"{key_prefix}_select_hook_{hook.id}"):
            set_selected_hook(session, hook)
            st.session_state[SESSION_SELECTED_HOOK_KEY] = hook.id
            st.session_state[SESSION_STEP_KEY] = WizardStep.TITLE_SELECTION.value
            st.success("Gancho elegido.")
            st.rerun()


def _hook_note_data(notes: str | None) -> dict[str, object]:
    if not notes:
        return {}
    try:
        value = json.loads(notes)
    except json.JSONDecodeError:
        return {"why_it_works": notes}
    return value if isinstance(value, dict) else {}


def _render_title_selection_step() -> None:
    draft = st.session_state[SESSION_DRAFT_KEY]
    with new_session() as session:
        topic = _ensure_wizard_topic(session)
        hook = _load_selected_hook(session)
        if topic is None or hook is None:
            st.info("Elige un gancho en el paso anterior antes de generar titulos.")
            return

        st.caption(f"Idea: #{topic.id} {topic.title}")
        st.caption(f"Gancho: {hook.text}")
        col1, col2, col3 = st.columns(3)
        language = col1.selectbox(
            "Idioma",
            ["en", "es", "hi_hinglish"],
            index=["en", "es", "hi_hinglish"].index(draft["language"]),
            format_func=lambda value: label_for(LANGUAGE_LABELS_ES, value),
            key="wizard_title_language",
        )
        market = col2.text_input("Mercado", value=draft["market"], key="wizard_title_market")
        provider_name = col3.selectbox(
            "Provider IA",
            ["manual", "ollama", "openai"],
            index=0,
            format_func=lambda value: {"manual": "Manual/gratis", "ollama": "Ollama local", "openai": "OpenAI opcional"}.get(value, value),
            key="wizard_title_provider",
        )
        mode = st.segmented_control(
            "Modo",
            options=["balanced", "shorter", "more_seo", "more_curiosity", "more_documentary", "safer", "more_direct"],
            default="balanced",
            format_func=lambda value: {
                "balanced": "Equilibrado",
                "shorter": "Mas cortos",
                "more_seo": "Mas SEO",
                "more_curiosity": "Mas curiosos",
                "more_documentary": "Mas documentales",
                "safer": "Mas seguros",
                "more_direct": "Mas directos",
            }.get(value, value),
            key="wizard_title_mode",
        )
        if st.button("Generar titulos automaticamente", type="primary", key="wizard_generate_titles"):
            result = generate_titles_for_hook(
                session,
                generated_idea_id=st.session_state.get(SESSION_SELECTED_GENERATED_IDEA_KEY),
                topic_id=topic.id,
                hook_id=hook.id,
                language=language,
                market=market,
                provider_name=provider_name,
                mode=mode or "balanced",
                save=True,
            )
            st.session_state[SESSION_GENERATED_TITLES_KEY] = result.saved_title_ids
            for warning in result.warnings:
                st.warning(warning)
            with st.expander("Prompt manual opcional"):
                st.text_area("Prompt", result.prompt, height=260, key="wizard_title_prompt_preview")
            st.success(f"Se generaron {len(result.saved_title_ids)} titulos. Elige uno para continuar.")

        titles = _load_titles_for_hook(session, hook.id)
        if not titles:
            st.info("Todavia no hay titulos generados para este gancho.")
            return
        selected_title_id = st.session_state.get(SESSION_SELECTED_TITLE_KEY)
        if selected_title_id:
            st.success(f"Titulo elegido: GeneratedTitle #{selected_title_id}.")
        st.subheader("Titulos candidatos")
        for title in titles:
            _render_title_card(session, title, topic, hook, language, market)


def _load_selected_hook(session) -> models.Hook | None:
    hook_id = st.session_state.get(SESSION_SELECTED_HOOK_KEY)
    if hook_id:
        hook = session.get(models.Hook, hook_id)
        if hook:
            return hook
    topic_id = st.session_state.get(SESSION_SELECTED_TOPIC_KEY)
    if not topic_id:
        return None
    return session.scalar(
        select(models.Hook)
        .where(models.Hook.topic_id == topic_id, models.Hook.selected.is_(True))
        .order_by(models.Hook.created_at.desc())
    )


def _load_titles_for_hook(session, hook_id: int) -> list[models.GeneratedTitle]:
    title_ids = list(st.session_state.get(SESSION_GENERATED_TITLES_KEY, []))
    statement = select(models.GeneratedTitle).where(models.GeneratedTitle.hook_id == hook_id)
    if title_ids:
        statement = statement.where(models.GeneratedTitle.id.in_(title_ids))
    statement = statement.order_by(models.GeneratedTitle.total_score.desc(), models.GeneratedTitle.created_at.desc())
    return list(session.scalars(statement).all())


def _render_title_card(
    session,
    title: models.GeneratedTitle,
    topic: models.Topic,
    hook: models.Hook,
    language: str,
    market: str,
) -> None:
    edit_key = f"wizard_editing_title_{title.id}"
    with st.container(border=True):
        st.markdown(f"**{title.title}**")
        st.caption(f"Tipo: {title.title_type} | Longitud: {title.length_chars} | Score: {title.total_score} | Elegido: {title.selected}")
        cols = st.columns(5)
        cols[0].metric("Claridad", title.clarity_score)
        cols[1].metric("Curiosidad", title.curiosity_score)
        cols[2].metric("SEO", title.seo_score)
        cols[3].metric("CTR", title.ctr_estimate_score)
        cols[4].metric("Clickbait", title.clickbait_risk)
        if title.why_it_works:
            st.caption(title.why_it_works)
        actions = st.columns(3)
        if actions[0].button("Elegir titulo", key=f"wizard_select_title_{title.id}"):
            set_selected_title(session, title)
            metadata = generate_metadata(
                session,
                generated_idea_id=st.session_state.get(SESSION_SELECTED_GENERATED_IDEA_KEY),
                topic_id=topic.id,
                hook_id=hook.id,
                title_id=title.id,
                script_id=None,
                language=language,
                market=market,
                provider_name="manual",
            ).metadata
            st.session_state[SESSION_SELECTED_TITLE_KEY] = title.id
            st.session_state[SESSION_SELECTED_METADATA_KEY] = metadata.id
            st.session_state[SESSION_STEP_KEY] = WizardStep.SCRIPT_GENERATION.value
            st.success("Titulo elegido y metadata generada.")
            st.rerun()
        if actions[1].button("Editar", key=f"wizard_edit_title_{title.id}"):
            st.session_state[edit_key] = not st.session_state.get(edit_key, False)
            st.rerun()
        if actions[2].button("Descartar", key=f"wizard_discard_title_{title.id}"):
            title.status = "discarded"
            title.selected = False
            session.commit()
            st.rerun()
        if st.session_state.get(edit_key, False):
            with st.form(f"wizard_title_form_{title.id}"):
                new_title = st.text_input("Titulo", value=title.title)
                submitted = st.form_submit_button("Guardar titulo")
                if submitted:
                    if not new_title.strip():
                        st.error("El titulo no puede estar vacio.")
                        return
                    title.title = new_title.strip()
                    title.length_chars = len(title.title)
                    title.status = "edited"
                    session.commit()
                    st.success("Titulo actualizado.")
                    st.rerun()


def _render_script_generation_step() -> None:
    draft = st.session_state[SESSION_DRAFT_KEY]
    with new_session() as session:
        topic = _ensure_wizard_topic(session)
        hook = _load_selected_hook(session)
        title = _load_selected_title(session)
        if topic is None or hook is None or title is None:
            st.info("Elige un titulo antes de generar el guion.")
            return
        st.caption(f"Idea: #{topic.id} {topic.title}")
        st.caption(f"Hook: {hook.text}")
        st.caption(f"Titulo: {title.title}")
        _render_metadata_summary(session)

        col1, col2, col3, col4 = st.columns(4)
        language = col1.selectbox(
            "Idioma",
            ["en", "es", "hi_hinglish"],
            index=["en", "es", "hi_hinglish"].index(draft["language"]),
            format_func=lambda value: label_for(LANGUAGE_LABELS_ES, value),
            key="wizard_script_language",
        )
        format_type = col2.selectbox(
            "Formato",
            list(SCRIPT_FORMATS),
            format_func=lambda value: SCRIPT_FORMATS[value],
            key="wizard_script_format",
        )
        duration_label = col3.selectbox(
            "Duracion",
            list(DURATION_OPTIONS),
            index=1,
            key="wizard_script_duration",
        )
        provider_name = col4.selectbox(
            "Provider IA",
            ["manual", "ollama", "openai"],
            index=0,
            key="wizard_script_provider",
        )
        tone = st.text_input("Tono", value="documental rapido, claro y con ritmo", key="wizard_script_tone")
        if st.button("Generar guion automatico", type="primary", key="wizard_generate_script"):
            result = generate_script(
                session,
                generated_idea_id=st.session_state.get(SESSION_SELECTED_GENERATED_IDEA_KEY),
                topic_id=topic.id,
                hook_id=hook.id,
                title_id=title.id,
                language=language,
                market=draft["market"],
                format_type=format_type,
                target_duration_seconds=DURATION_OPTIONS[duration_label],
                tone=tone,
                provider_name=provider_name,
            )
            st.session_state[SESSION_SELECTED_SCRIPT_KEY] = result.script.id
            for warning in result.warnings:
                st.warning(warning)
            st.success(f"Guion #{result.script.id} generado con score de calidad {result.quality_report.score}.")

        script = _load_selected_or_latest_script(session, topic.id, hook.id)
        if script is None:
            st.info("Todavia no hay guion generado para este titulo.")
            return
        _render_script_editor(session, script)


def _load_selected_title(session) -> models.GeneratedTitle | None:
    title_id = st.session_state.get(SESSION_SELECTED_TITLE_KEY)
    if title_id:
        title = session.get(models.GeneratedTitle, title_id)
        if title:
            return title
    hook = _load_selected_hook(session)
    if hook is None:
        return None
    return session.scalar(
        select(models.GeneratedTitle)
        .where(models.GeneratedTitle.hook_id == hook.id, models.GeneratedTitle.selected.is_(True))
        .order_by(models.GeneratedTitle.created_at.desc())
    )


def _render_metadata_summary(session) -> None:
    metadata_id = st.session_state.get(SESSION_SELECTED_METADATA_KEY)
    metadata = session.get(models.MetadataSuggestion, metadata_id) if metadata_id else None
    if not metadata:
        return
    with st.expander("Metadata sugerida"):
        st.write(metadata.description)
        st.write(metadata.hashtags_json)
        if metadata.pinned_comment:
            st.write(f"Comentario fijado: {metadata.pinned_comment}")


def _load_selected_or_latest_script(session, topic_id: int, hook_id: int) -> models.Script | None:
    script_id = st.session_state.get(SESSION_SELECTED_SCRIPT_KEY)
    if script_id:
        script = session.get(models.Script, script_id)
        if script:
            return script
    return session.scalar(
        select(models.Script)
        .where(models.Script.topic_id == topic_id, models.Script.hook_id == hook_id)
        .order_by(models.Script.created_at.desc())
    )


def _render_script_editor(session, script: models.Script) -> None:
    st.subheader(f"Guion #{script.id}")
    notes = _hook_note_data(script.fact_check_notes)
    if notes:
        st.metric("Score de calidad", notes.get("quality_score", "-"))
        for issue in notes.get("blocking_issues", []):
            st.error(issue)
        for warning in notes.get("quality_warnings", []):
            st.warning(warning)
        for warning in notes.get("fact_warnings", []):
            if isinstance(warning, dict):
                st.warning(f"{warning.get('claim_type')}: {warning.get('text')} - {warning.get('suggestion')}")

    rows = [
        {
            "id": line.id,
            "Orden": line.line_order,
            "Texto": line.text,
            "Subtitulo": line.subtitle_text or line.text,
            "Duracion": line.duration_seconds,
            "Visual": line.visual_suggestion or "",
            "Fuente necesaria": line.needs_source,
            "Riesgo": line.risk_note or "",
        }
        for line in script.lines
    ]
    edited = st.data_editor(rows, num_rows="dynamic", use_container_width=True, key=f"script_editor_{script.id}")
    actions = st.columns(3)
    if actions[0].button("Guardar cambios de lineas", key=f"save_script_lines_{script.id}"):
        _save_script_lines_from_editor(session, script, edited)
        st.success("Lineas actualizadas.")
        st.rerun()
    if actions[1].button("Aprobar guion", type="primary", key=f"approve_script_{script.id}"):
        try:
            approve_script(session, script.id)
        except ValueError as exc:
            st.error(str(exc))
            return
        st.session_state[SESSION_SELECTED_SCRIPT_KEY] = script.id
        st.success("Guion aprobado. Ya puedes continuar a voz.")
        st.rerun()
    if actions[2].button("Usar este guion", key=f"use_script_{script.id}"):
        st.session_state[SESSION_SELECTED_SCRIPT_KEY] = script.id
        st.success("Guion seleccionado.")


def _save_script_lines_from_editor(session, script: models.Script, rows: list[dict[str, object]]) -> None:
    existing = {line.id: line for line in script.lines}
    kept_ids: set[int] = set()
    normalized_rows = [row for row in rows if str(row.get("Texto") or "").strip()]
    for index, row in enumerate(normalized_rows, start=1):
        line_id = row.get("id")
        line = existing.get(line_id) if isinstance(line_id, int) else None
        if line is None:
            line = models.ScriptLine(script_id=script.id, line_order=index, text="")
            session.add(line)
            session.flush()
        kept_ids.add(line.id)
        line.line_order = int(row.get("Orden") or index)
        line.text = str(row.get("Texto") or "").strip()
        line.subtitle_text = str(row.get("Subtitulo") or line.text)
        line.duration_seconds = float(row.get("Duracion") or 2.5)
        line.visual_suggestion = str(row.get("Visual") or "")
        line.needs_source = bool(row.get("Fuente necesaria", False))
        line.risk_note = str(row.get("Riesgo") or "") or None
    for line in list(script.lines):
        if line.id not in kept_ids:
            session.delete(line)
    script.script_text = "\n".join(str(row.get("Texto") or "").strip() for row in normalized_rows)
    script.estimated_duration_seconds = sum(float(row.get("Duracion") or 2.5) for row in normalized_rows)
    session.commit()


def _render_voiceover_step() -> None:
    with new_session() as session:
        script = _load_selected_approved_script(session)
        if script is None:
            st.info("Aprueba un guion antes de crear voz.")
            return

        st.caption(f"Guion aprobado: #{script.id} {script.topic.title} [{script.language}]")
        with st.expander("Estado de proveedores TTS"):
            st.dataframe(list_tts_provider_statuses(script.language), use_container_width=True, hide_index=True)

        mode = st.radio(
            "Modo de voz",
            ["placeholder", "manual_recording", "local_tts", "openai_tts", "elevenlabs_tts"],
            format_func=_voice_provider_label,
            horizontal=True,
            key="wizard_voice_mode",
        )
        if mode == "placeholder":
            if st.button("Continuar sin voz", type="primary", key="wizard_create_placeholder_voice"):
                job = create_voiceover_from_script(session, script_id=script.id, provider_name="placeholder")
                st.session_state[SESSION_SELECTED_VOICEOVER_KEY] = job.id
                st.success(f"VoiceoverJob #{job.id} creado como placeholder.")
                st.rerun()
        elif mode == "manual_recording":
            file_path = st.text_input("Ruta del audio de voz local", key="wizard_manual_voice_path")
            duration = st.number_input(
                "Duracion estimada en segundos",
                min_value=1.0,
                value=float(script.estimated_duration_seconds or 30),
                step=0.5,
                key="wizard_manual_voice_duration",
            )
            if st.button("Importar voz manual", type="primary", key="wizard_import_manual_voice"):
                try:
                    job = import_manual_voiceover(
                        session,
                        script_id=script.id,
                        file_path=file_path,
                        duration_seconds=float(duration),
                        overwrite=True,
                    )
                except Exception as exc:  # noqa: BLE001 - Streamlit debe mostrar el error al usuario.
                    st.error(str(exc))
                    return
                st.session_state[SESSION_SELECTED_VOICEOVER_KEY] = job.id
                st.success(f"VoiceoverJob #{job.id} importado.")
                st.rerun()
        elif mode == "elevenlabs_tts":
            settings = get_settings()
            script_text = script.script_text or "\n".join(line.text for line in script.lines)
            cost = estimate_cost("elevenlabs", "tts", {"text": script_text})
            col1, col2, col3 = st.columns(3)
            voice_id = col1.text_input("Voice ID", value=settings.elevenlabs_default_voice_id, key="wizard_eleven_voice_id")
            model_id = col2.text_input("Modelo", value=settings.elevenlabs_model_id, key="wizard_eleven_model_id")
            with_timestamps = col3.checkbox("Intentar timing", value=True, key="wizard_eleven_timing")
            st.metric("Caracteres", len(script_text))
            if cost["estimated_cost"] is None:
                st.warning("Puede generar coste. No hay tarifa configurada; revisa tu plan de ElevenLabs.")
            else:
                st.warning(f"Coste estimado: {cost['estimated_cost']:.4f} {cost['currency']}.")
            st.caption("Comprueba licencia comercial del plan antes de monetizar.")
            confirmed = st.checkbox(
                "Confirmo que quiero ejecutar una operacion potencialmente de pago.",
                key="wizard_eleven_paid_confirmed",
            )
            if st.button("Generar voz con ElevenLabs", type="primary", key="wizard_generate_elevenlabs"):
                job = create_voiceover_from_script(
                    session,
                    script_id=script.id,
                    provider_name=mode,
                    language=script.language,
                    voice_id=voice_id or None,
                    allow_paid=confirmed,
                    model_id=model_id or None,
                    with_timestamps=with_timestamps,
                )
                st.session_state[SESSION_SELECTED_VOICEOVER_KEY] = job.id
                if job.status == VoiceoverJobStatus.FAILED.value:
                    st.error(job.error_message)
                else:
                    st.success(f"VoiceoverJob #{job.id} generado.")
                st.rerun()
        else:
            st.warning("Proveedor opcional. Si no esta configurado, se guardara como fallo informativo.")
            if st.button("Intentar generar voz TTS", type="primary", key=f"wizard_generate_tts_{mode}"):
                job = create_voiceover_from_script(session, script_id=script.id, provider_name=mode)
                st.session_state[SESSION_SELECTED_VOICEOVER_KEY] = job.id
                if job.status == VoiceoverJobStatus.FAILED.value:
                    st.error(job.error_message)
                else:
                    st.success(f"VoiceoverJob #{job.id} generado.")
                st.rerun()

        jobs = _load_voiceover_jobs(session, script.id)
        if not jobs:
            st.info("Todavia no hay voiceovers para este guion.")
            return

        st.subheader("Voces creadas")
        for job in jobs:
            _render_voiceover_job_card(session, job)


def _render_voiceover_job_card(session, job: models.VoiceoverJob) -> None:
    selected = st.session_state.get(SESSION_SELECTED_VOICEOVER_KEY) == job.id
    with st.container(border=True):
        st.markdown(f"**VoiceoverJob #{job.id}**")
        st.caption(
            f"Proveedor: {job.provider} | Estado: {job.status} | "
            f"Duracion: {job.duration_seconds or '-'} | Seleccionado: {selected}"
        )
        if job.output_audio_path:
            st.write(job.output_audio_path)
            if Path(job.output_audio_path).exists():
                st.audio(job.output_audio_path)
        if job.error_message:
            st.warning(job.error_message)
        actions = st.columns(3)
        if actions[0].button("Usar voz", key=f"wizard_use_voice_{job.id}"):
            st.session_state[SESSION_SELECTED_VOICEOVER_KEY] = job.id
            st.rerun()
        if actions[1].button("Aprobar voz", key=f"wizard_approve_voice_{job.id}"):
            try:
                approve_voiceover(session, job.id)
            except ValueError as exc:
                st.error(str(exc))
                return
            st.session_state[SESSION_SELECTED_VOICEOVER_KEY] = job.id
            st.success("Voz aprobada.")
            st.rerun()
        if actions[2].button("Rechazar voz", key=f"wizard_reject_voice_{job.id}"):
            job.status = VoiceoverJobStatus.REJECTED.value
            session.commit()
            st.rerun()


def _render_subtitles_music_step() -> None:
    with new_session() as session:
        script = _load_selected_approved_script(session)
        if script is None:
            st.info("Aprueba un guion antes de generar subtitulos.")
            return
        voiceover = _load_selected_voiceover(session)
        if voiceover:
            st.caption(f"Voz seleccionada: #{voiceover.id} {voiceover.provider} [{voiceover.status}]")
        else:
            st.caption("No hay voz seleccionada; los subtitulos usaran la duracion estimada del guion.")

        if st.button("Generar subtitulos desde guion", type="primary", key="wizard_generate_subtitles"):
            track = generate_subtitles_from_script(
                session,
                script_id=script.id,
                voiceover_job_id=voiceover.id if voiceover else None,
                overwrite=True,
            )
            st.session_state[SESSION_SELECTED_SUBTITLE_TRACK_KEY] = track.id
            st.success(f"SubtitleTrack #{track.id} generado.")
            st.rerun()

        tracks = _load_subtitle_tracks(session, script.id)
        if tracks:
            st.subheader("Subtitulos")
            for track in tracks:
                _render_subtitle_track_card(session, track)
        else:
            st.info("Todavia no hay subtitulos para este guion.")

        st.subheader("Musica segura opcional")
        music_tracks = suggest_music_for_script(session, script_id=script.id)
        if not music_tracks:
            st.info("No hay musica segura registrada. Puedes continuar sin musica.")
        else:
            options = {"Sin musica": None}
            options.update({f"#{track.id} {track.title} [{track.mood}, energia {track.energy}]": track.id for track in music_tracks})
            selected_label = st.selectbox("Seleccion de musica", list(options), key="wizard_music_selectbox")
            if st.button("Guardar musica seleccionada", key="wizard_save_music_selection"):
                st.session_state[SESSION_SELECTED_MUSIC_KEY] = options[selected_label]
                st.success("Seleccion de musica guardada.")


def _render_subtitle_track_card(session, track: models.SubtitleTrack) -> None:
    selected = st.session_state.get(SESSION_SELECTED_SUBTITLE_TRACK_KEY) == track.id
    with st.container(border=True):
        st.markdown(f"**SubtitleTrack #{track.id}**")
        st.caption(f"Estado: {track.status} | Seleccionado: {selected} | SRT: {track.srt_path or '-'}")
        srt_content = export_srt(session, track.id)
        st.text_area("SRT", value=srt_content, height=180, key=f"wizard_srt_preview_{track.id}")
        rows = _subtitle_rows(track)
        edited = st.data_editor(rows, use_container_width=True, num_rows="dynamic", key=f"wizard_subtitle_editor_{track.id}")
        actions = st.columns(3)
        if actions[0].button("Usar subtitulos", key=f"wizard_use_subtitles_{track.id}"):
            st.session_state[SESSION_SELECTED_SUBTITLE_TRACK_KEY] = track.id
            st.rerun()
        if actions[1].button("Guardar edicion", key=f"wizard_save_subtitles_{track.id}"):
            update_subtitle_track_from_rows(
                session,
                subtitle_track_id=track.id,
                rows=_editor_rows(edited),
                overwrite=True,
            )
            st.session_state[SESSION_SELECTED_SUBTITLE_TRACK_KEY] = track.id
            st.success("Subtitulos actualizados.")
            st.rerun()
        if actions[2].button("Aprobar subtitulos", key=f"wizard_approve_subtitles_{track.id}"):
            approve_subtitles(session, track.id)
            st.session_state[SESSION_SELECTED_SUBTITLE_TRACK_KEY] = track.id
            st.success("Subtitulos aprobados.")
            st.rerun()


def _render_visual_plan_step() -> None:
    with new_session() as session:
        script = _load_selected_approved_script(session)
        if script is None:
            st.info("Aprueba un guion antes de crear el plan visual.")
            return
        template = st.selectbox(
            "Plantilla sugerida",
            ["clean_text_focus", "tech_dark", "documentary_alert", "minimal_educational"],
            key="wizard_visual_template",
        )
        if st.button("Generar plan visual", type="primary", key="wizard_generate_visual_plan"):
            plan = generate_visual_plan(session, script_id=script.id, template_name=template)
            st.session_state[SESSION_SELECTED_VISUAL_PLAN_KEY] = plan.id
            st.success(f"VisualPlan #{plan.id} generado.")
            st.rerun()

        plans = _load_visual_plans(session, script.id)
        if not plans:
            st.info("Todavia no hay plan visual para este guion.")
            return
        for plan in plans:
            _render_visual_plan_card(session, plan)


def _render_visual_plan_card(session, plan: models.VisualPlan) -> None:
    selected = st.session_state.get(SESSION_SELECTED_VISUAL_PLAN_KEY) == plan.id
    with st.container(border=True):
        st.markdown(f"**VisualPlan #{plan.id}**")
        st.caption(f"Plantilla: {plan.template_name} | Estado: {plan.status} | Seleccionado: {selected}")
        scenes = visual_plan_scenes(plan)
        st.dataframe(scenes, use_container_width=True, hide_index=True)
        actions = st.columns(2)
        if actions[0].button("Usar plan visual", key=f"wizard_use_visual_{plan.id}"):
            st.session_state[SESSION_SELECTED_VISUAL_PLAN_KEY] = plan.id
            st.rerun()
        if actions[1].button("Aprobar plan visual", key=f"wizard_approve_visual_{plan.id}"):
            approve_visual_plan(session, plan.id)
            st.session_state[SESSION_SELECTED_VISUAL_PLAN_KEY] = plan.id
            st.success("Plan visual aprobado.")
            st.rerun()


def _render_render_step() -> None:
    with new_session() as session:
        script = _load_selected_approved_script(session)
        subtitle_track = _load_selected_subtitle_track(session)
        visual_plan = _load_selected_visual_plan(session)
        voiceover = _load_selected_voiceover(session)
        music_id = st.session_state.get(SESSION_SELECTED_MUSIC_KEY)
        if script is None:
            st.info("Aprueba un guion antes de renderizar.")
            return
        if subtitle_track is None or visual_plan is None:
            st.info("Aprueba subtitulos y plan visual antes de renderizar.")
            return

        st.caption(f"Guion #{script.id} | Subtitulos #{subtitle_track.id} | Visual #{visual_plan.id}")
        st.caption(f"Voz: #{voiceover.id} {voiceover.status}" if voiceover else "Voz: sin voz")
        st.caption(f"Musica: #{music_id}" if music_id else "Musica: sin musica")

        if st.button("Crear plan de render", type="primary", key="wizard_create_render_plan"):
            plan = create_short_render_plan(
                session,
                script_id=script.id,
                voiceover_job_id=voiceover.id if voiceover else None,
                subtitle_track_id=subtitle_track.id,
                visual_plan_id=visual_plan.id,
                music_track_id=music_id,
            )
            st.session_state[SESSION_SELECTED_RENDER_PLAN_KEY] = plan.id
            st.success(f"RenderPlan #{plan.id} creado.")
            st.rerun()

        plans = _load_render_plans(session, script.id)
        if not plans:
            st.info("Todavia no hay plan de render.")
            return
        for plan in plans:
            _render_render_plan_card(session, plan)


def _render_render_plan_card(session, plan: models.RenderPlan) -> None:
    selected = st.session_state.get(SESSION_SELECTED_RENDER_PLAN_KEY) == plan.id
    with st.container(border=True):
        st.markdown(f"**RenderPlan #{plan.id}**")
        st.caption(f"Estado: {plan.status} | Seleccionado: {selected} | Output: {plan.output_path or '-'}")
        report = validate_render_plan(session, plan.id)
        for error in report.errors:
            st.error(error)
        for warning in report.warnings:
            st.warning(warning)
        actions = st.columns(4)
        if actions[0].button("Usar plan", key=f"wizard_use_render_plan_{plan.id}"):
            st.session_state[SESSION_SELECTED_RENDER_PLAN_KEY] = plan.id
            st.rerun()
        if actions[1].button("Validar", key=f"wizard_validate_render_plan_{plan.id}"):
            updated = mark_render_plan_ready(session, plan.id)
            st.session_state[SESSION_SELECTED_RENDER_PLAN_KEY] = updated.id
            st.success("Plan listo." if updated.status == RenderPlanStatus.READY.value else updated.error_message)
            st.rerun()
        if actions[2].button("Renderizar", key=f"wizard_render_plan_{plan.id}", disabled=not report.ok):
            result = render_from_plan(session, render_plan_id=plan.id, overwrite=True)
            if result.ok and result.output_path:
                st.success("Render generado.")
                st.video(result.output_path)
            else:
                st.error(result.error_message)
            st.session_state[SESSION_SELECTED_RENDER_PLAN_KEY] = plan.id
            st.rerun()
        if actions[3].button("Aprobar render", key=f"wizard_approve_render_plan_{plan.id}"):
            try:
                approve_render_plan(session, plan.id)
            except ValueError as exc:
                st.error(str(exc))
                return
            st.session_state[SESSION_SELECTED_RENDER_PLAN_KEY] = plan.id
            st.success("Render aprobado para revision final.")
            st.rerun()


def _load_selected_approved_script(session) -> models.Script | None:
    script_id = st.session_state.get(SESSION_SELECTED_SCRIPT_KEY)
    if script_id:
        script = session.get(models.Script, script_id)
        if script and script.status == "approved":
            return script
    return session.scalar(
        select(models.Script).where(models.Script.status == "approved").order_by(models.Script.created_at.desc())
    )


def _load_voiceover_jobs(session, script_id: int) -> list[models.VoiceoverJob]:
    return list(
        session.scalars(
            select(models.VoiceoverJob)
            .where(models.VoiceoverJob.script_id == script_id)
            .order_by(models.VoiceoverJob.created_at.desc())
        ).all()
    )


def _load_selected_voiceover(session) -> models.VoiceoverJob | None:
    job_id = st.session_state.get(SESSION_SELECTED_VOICEOVER_KEY)
    return session.get(models.VoiceoverJob, job_id) if job_id else None


def _load_subtitle_tracks(session, script_id: int) -> list[models.SubtitleTrack]:
    return list(
        session.scalars(
            select(models.SubtitleTrack)
            .where(models.SubtitleTrack.script_id == script_id)
            .order_by(models.SubtitleTrack.created_at.desc())
        ).all()
    )


def _load_selected_subtitle_track(session) -> models.SubtitleTrack | None:
    track_id = st.session_state.get(SESSION_SELECTED_SUBTITLE_TRACK_KEY)
    return session.get(models.SubtitleTrack, track_id) if track_id else None


def _load_visual_plans(session, script_id: int) -> list[models.VisualPlan]:
    return list(
        session.scalars(
            select(models.VisualPlan)
            .where(models.VisualPlan.script_id == script_id)
            .order_by(models.VisualPlan.created_at.desc())
        ).all()
    )


def _load_selected_visual_plan(session) -> models.VisualPlan | None:
    plan_id = st.session_state.get(SESSION_SELECTED_VISUAL_PLAN_KEY)
    return session.get(models.VisualPlan, plan_id) if plan_id else None


def _load_render_plans(session, script_id: int) -> list[models.RenderPlan]:
    return list(
        session.scalars(
            select(models.RenderPlan)
            .where(models.RenderPlan.script_id == script_id)
            .order_by(models.RenderPlan.created_at.desc())
        ).all()
    )


def _subtitle_rows(track: models.SubtitleTrack) -> list[dict[str, object]]:
    payload = json.loads(track.subtitles_json or "[]")
    return [
        {
            "start_seconds": item["start_seconds"],
            "end_seconds": item["end_seconds"],
            "text": item["text"],
        }
        for item in payload
        if isinstance(item, dict)
    ]


def _voice_provider_label(provider: str) -> str:
    return {
        "placeholder": "Sin voz",
        "manual_recording": "Voz manual",
        "local_tts": "TTS local",
        "openai_tts": "OpenAI TTS",
        "elevenlabs_tts": "ElevenLabs",
    }.get(provider, provider)


def _editor_rows(value) -> list[dict[str, object]]:
    if hasattr(value, "to_dict"):
        return value.to_dict("records")
    return list(value)


def _render_idea_selection_step_legacy() -> None:
    trend_items = [TrendItem(**item) for item in st.session_state.get("wizard_trend_items", [])]
    warnings = st.session_state.get("wizard_trend_warnings", [])
    for warning in warnings:
        st.warning(warning)
    if not trend_items:
        st.info("Investiga tendencias en el paso anterior antes de elegir una idea.")
        return

    st.subheader("Tendencias listas para convertir en ideas")
    for index, item in enumerate(trend_items, start=1):
        with st.container(border=True):
            st.markdown(f"**{index}. {item.title}**")
            st.caption(f"Fuente: {item.source} | Categoría: {label_for(CATEGORY_LABELS, item.category)}")
            if item.summary:
                st.write(item.summary)
            cols = st.columns(3)
            cols[0].metric("Señales", len(item.popularity_signals))
            cols[1].metric("Riesgo proveedor", "Aviso" if item.popularity_signals.get("provider_error") else "OK")
            cols[2].metric("URL", "Sí" if item.source_url else "No")
            if st.button("Usar como base de idea", key=f"use_trend_{index}"):
                st.session_state["wizard_selected_trend"] = item.model_dump(mode="json")
                st.success("Tendencia seleccionada. La generación de ideas originales llega en la siguiente fase.")


def _render_idea_selection_step() -> None:
    warnings = st.session_state.get("wizard_trend_warnings", [])
    for warning in warnings:
        st.warning(warning)

    with new_session() as session:
        ideas = _load_wizard_generated_ideas(session)
        if not ideas:
            st.info("Investiga tendencias y genera ideas originales en el paso anterior.")
            _render_generate_ideas_controls()
            return

        selected_idea_id = st.session_state.get(SESSION_SELECTED_GENERATED_IDEA_KEY)
        selected_topic_id = st.session_state.get(SESSION_SELECTED_TOPIC_KEY)
        if selected_topic_id:
            st.success(f"Idea principal lista para ganchos: Topic #{selected_topic_id}.")
        elif selected_idea_id:
            st.success(f"Idea elegida: GeneratedIdea #{selected_idea_id}.")

        st.subheader("Ideas originales generadas")
        for idea in ideas:
            _render_generated_idea_card(session, idea, key_prefix="wizard", advance_on_select=True)


def _render_generate_ideas_controls() -> None:
    trend_items = _wizard_trend_items()
    if not trend_items:
        return

    draft = st.session_state[SESSION_DRAFT_KEY]
    st.subheader("Generar ideas originales")
    title_options = [item.title for item in trend_items]
    selected_titles = st.multiselect(
        "Tendencias base",
        title_options,
        default=title_options[: min(3, len(title_options))],
        key="wizard_selected_trend_titles",
    )
    selected_items = [item for item in trend_items if item.title in selected_titles]
    ideas_per_trend = st.slider(
        "Ideas por tendencia",
        min_value=1,
        max_value=5,
        value=3,
        key="wizard_ideas_per_trend",
    )
    if st.button("Generar ideas desde tendencias", type="primary", key="wizard_generate_ideas"):
        if not selected_items:
            st.error("Selecciona al menos una tendencia antes de generar ideas.")
            return
        ideas = generate_ideas_from_trends(
            selected_items,
            target_language=draft["language"],
            target_market=draft["market"],
            category=draft["category"],
            ideas_per_trend=int(ideas_per_trend),
        )
        if not ideas:
            st.warning("No se generaron ideas. Revisa que las tendencias no sean errores de proveedor.")
            return
        with new_session() as session:
            saved = persist_generated_ideas(session, ideas)
            saved_ids = [idea.id for idea in saved]
        existing_ids = list(st.session_state.get(SESSION_GENERATED_IDEAS_KEY, []))
        for idea_id in saved_ids:
            if idea_id not in existing_ids:
                existing_ids.append(idea_id)
        st.session_state[SESSION_GENERATED_IDEAS_KEY] = existing_ids
        st.success(f"Se generaron {len(saved_ids)} ideas originales. Ve al paso 2 para elegir una.")


def _wizard_trend_items() -> list[TrendItem]:
    return [TrendItem(**item) for item in st.session_state.get("wizard_trend_items", [])]


def _load_wizard_generated_ideas(session) -> list[models.GeneratedIdea]:
    idea_ids = list(st.session_state.get(SESSION_GENERATED_IDEAS_KEY, []))
    selected_id = st.session_state.get(SESSION_SELECTED_GENERATED_IDEA_KEY)
    if selected_id and selected_id not in idea_ids:
        idea_ids.append(selected_id)
    if not idea_ids:
        return []
    statement = (
        select(models.GeneratedIdea)
        .where(models.GeneratedIdea.id.in_(idea_ids))
        .order_by(models.GeneratedIdea.total_score.desc(), models.GeneratedIdea.created_at.desc())
    )
    return list(session.scalars(statement).all())


def _render_generated_idea_card(
    session,
    idea: models.GeneratedIdea,
    key_prefix: str,
    advance_on_select: bool = False,
) -> None:
    data = generated_idea_card_data(idea)
    edit_key = f"{key_prefix}_editing_{idea.id}"
    with st.container(border=True):
        st.markdown(f"**{data['titulo']}**")
        st.caption(
            f"{data['estado']} | {data['categoria']} | {data['idioma']} | "
            f"{data['mercado']} | Score {data['score']} ({data['score_badge']})"
        )
        st.write(idea.summary)
        cols = st.columns(5)
        cols[0].metric("Viralidad", idea.viral_score)
        cols[1].metric("RPM", idea.rpm_score)
        cols[2].metric("Evergreen", idea.evergreen_score)
        cols[3].metric("Riesgo copyright", idea.copyright_risk)
        cols[4].metric("Riesgo monetización", idea.monetization_risk)
        with st.expander("Detalles"):
            st.write(f"Ángulo: {idea.angle}")
            st.write(f"Por qué puede funcionar: {idea.why_it_can_work}")
            st.write(f"Público objetivo: {idea.target_audience or 'No definido'}")
            st.write(f"Duración sugerida: {idea.suggested_duration}")
            st.write(f"Formato: {idea.suggested_format}")
            st.write(f"Hook sugerido: {idea.suggested_hook_type}")
            st.write(f"Visual sugerido: {idea.suggested_visual}")
            st.write(f"Fuentes: {idea.sources_json or '[]'}")
        actions = st.columns(5)
        if actions[0].button("Elegir idea", key=f"{key_prefix}_select_{idea.id}"):
            if idea.status == GeneratedIdeaStatus.DISCARDED.value:
                st.error("No puedes elegir una idea descartada.")
                return
            idea.status = GeneratedIdeaStatus.SELECTED.value
            session.commit()
            st.session_state[SESSION_SELECTED_GENERATED_IDEA_KEY] = idea.id
            if advance_on_select:
                st.session_state[SESSION_STEP_KEY] = WizardStep.HOOK_SELECTION.value
            st.success("Idea elegida.")
            st.rerun()
        if actions[1].button("Guardar para después", key=f"{key_prefix}_save_{idea.id}"):
            idea.status = GeneratedIdeaStatus.SAVED_FOR_LATER.value
            session.commit()
            st.rerun()
        if actions[2].button("Descartar", key=f"{key_prefix}_discard_{idea.id}"):
            idea.status = GeneratedIdeaStatus.DISCARDED.value
            session.commit()
            st.rerun()
        if actions[3].button("Convertir en idea principal", key=f"{key_prefix}_topic_{idea.id}"):
            topic = convert_generated_idea_to_topic(session, idea)
            st.session_state[SESSION_SELECTED_GENERATED_IDEA_KEY] = idea.id
            st.session_state[SESSION_SELECTED_TOPIC_KEY] = topic.id
            if advance_on_select:
                st.session_state[SESSION_STEP_KEY] = WizardStep.HOOK_SELECTION.value
            st.success(f"Convertida en idea principal #{topic.id}.")
            st.rerun()
        if actions[4].button("Editar", key=f"{key_prefix}_edit_{idea.id}"):
            st.session_state[edit_key] = not st.session_state.get(edit_key, False)
            st.rerun()
        if st.session_state.get(edit_key, False):
            _render_generated_idea_edit_form(session, idea, key_prefix)


def _render_generated_idea_edit_form(session, idea: models.GeneratedIdea, key_prefix: str) -> None:
    with st.form(f"{key_prefix}_edit_form_{idea.id}"):
        title = st.text_input("Título", value=idea.title)
        angle = st.text_area("Ángulo", value=idea.angle)
        summary = st.text_area("Resumen", value=idea.summary)
        why_it_can_work = st.text_area("Por qué puede funcionar", value=idea.why_it_can_work)
        submitted = st.form_submit_button("Guardar cambios")
        if submitted:
            if not title.strip():
                st.error("La idea necesita un título.")
                return
            idea.title = title.strip()
            idea.angle = angle.strip()
            idea.summary = summary.strip()
            idea.why_it_can_work = why_it_can_work.strip()
            session.commit()
            st.success("Idea actualizada.")
            st.rerun()


def _render_trend_results(session_key: str) -> None:
    trend_items = [TrendItem(**item) for item in st.session_state.get(session_key, [])]
    if not trend_items:
        return
    st.subheader("Tendencias detectadas")
    st.dataframe(
        [
            {
                "título": item.title,
                "fuente": item.source,
                "url": item.source_url,
                "señales": item.popularity_signals,
            }
            for item in trend_items
        ],
        use_container_width=True,
        hide_index=True,
    )


def _render_card_grid(items: list[tuple[str, str]]) -> None:
    columns = st.columns(len(items))
    for column, (title, body) in zip(columns, items, strict=False):
        with column:
            st.markdown(f"**{title}**")
            st.caption(body)


def _render_controls(current_step: WizardStep) -> None:
    approved_steps: set[str] = st.session_state[SESSION_APPROVED_KEY]
    col1, col2, col3, col4, col5 = st.columns(5)
    previous_value = previous_step(current_step)
    next_value = next_step(current_step)
    can_advance = _can_advance(current_step)

    if col1.button("Atrás", disabled=previous_value is None):
        st.session_state[SESSION_STEP_KEY] = previous_value.value
        st.rerun()
    if col2.button("Guardar borrador"):
        st.success("Borrador guardado en esta sesión.")
    if col3.button("Regenerar sugerencias"):
        st.info("La regeneración automática se conectará al proveedor LLM opcional.")
    if col4.button("Aprobar paso", type="primary"):
        approved_steps.add(current_step.value)
        st.session_state[SESSION_APPROVED_KEY] = approved_steps
        st.success("Paso aprobado.")
    if col5.button("Siguiente", disabled=next_value is None or not can_advance):
        st.session_state[SESSION_STEP_KEY] = next_value.value
        st.rerun()

    approved_count = len(approved_steps)
    st.caption(f"Pasos aprobados en esta sesion: {approved_count}/{len(WIZARD_STEPS)}")


def _can_advance(current_step: WizardStep) -> bool:
    if current_step == WizardStep.IDEA_SELECTION:
        return bool(
            st.session_state.get(SESSION_SELECTED_GENERATED_IDEA_KEY)
            or st.session_state.get(SESSION_SELECTED_TOPIC_KEY)
        )
    if current_step == WizardStep.HOOK_SELECTION:
        return bool(st.session_state.get(SESSION_SELECTED_HOOK_KEY))
    if current_step == WizardStep.TITLE_SELECTION:
        return bool(st.session_state.get(SESSION_SELECTED_TITLE_KEY))
    if current_step == WizardStep.SCRIPT_GENERATION:
        script_id = st.session_state.get(SESSION_SELECTED_SCRIPT_KEY)
        if not script_id:
            return False
        with new_session() as session:
            script = session.get(models.Script, script_id)
            return bool(script and script.status == "approved")
    if current_step == WizardStep.CHARACTER:
        return bool(st.session_state.get(SESSION_SELECTED_CHARACTER_KEY))
    if current_step == WizardStep.STORYBOARD:
        return bool(st.session_state.get(SESSION_SELECTED_STORYBOARD_KEY))
    if current_step == WizardStep.VOICEOVER:
        job_id = st.session_state.get(SESSION_SELECTED_VOICEOVER_KEY)
        if not job_id:
            return False
        with new_session() as session:
            job = session.get(models.VoiceoverJob, job_id)
            return bool(
                job
                and job.status
                in {
                    VoiceoverJobStatus.APPROVED.value,
                    VoiceoverJobStatus.PLACEHOLDER.value,
                }
            )
    if current_step == WizardStep.MUSIC_SELECTION:
        track_id = st.session_state.get(SESSION_SELECTED_SUBTITLE_TRACK_KEY)
        if not track_id:
            return False
        with new_session() as session:
            track = session.get(models.SubtitleTrack, track_id)
            return bool(track and track.status == SubtitleTrackStatus.APPROVED.value)
    if current_step == WizardStep.VISUAL_STYLE:
        plan_id = st.session_state.get(SESSION_SELECTED_VISUAL_PLAN_KEY)
        if not plan_id:
            return False
        with new_session() as session:
            plan = session.get(models.VisualPlan, plan_id)
            return bool(plan and plan.status == VisualPlanStatus.APPROVED.value)
    if current_step == WizardStep.RENDER:
        plan_id = st.session_state.get(SESSION_SELECTED_RENDER_PLAN_KEY)
        if not plan_id:
            return False
        with new_session() as session:
            plan = session.get(models.RenderPlan, plan_id)
            return bool(plan and plan.status == RenderPlanStatus.APPROVED.value)
    return True


def _provider_label(provider: str) -> str:
    return {
        "manual": "Manual",
        "rss": "RSS",
        "hackernews": "Hacker News",
        "youtube": "YouTube Data API",
    }.get(provider, provider)
