from __future__ import annotations

from app.core.enums import WizardStep

APP_NAME = "ShortsFactory"

NAVIGATION = (
    ("Investigacion", "09_trend_research"),
    ("Creacion", "16_creation"),
    ("Ideas", "17_metadata_recipe"),
    ("Produccion", "18_production"),
    ("Inicio", "home"),
    ("Crear Short paso a paso", "00_wizard"),
    ("Ideas antiguas", "01_topics"),
    ("Ganchos", "02_hooks"),
    ("Guiones", "03_scripts"),
    ("Localización", "10_localization"),
    ("Personajes", "13_characters"),
    ("Storyboard Nero", "14_storyboard"),
    ("Voces", "11_voiceover"),
    ("Herramientas externas", "12_external_tools"),
    ("Música y recursos", "04_assets_music"),
    ("Mapeo de clips", "15_scene_mapping"),
    ("Renderizar", "05_render"),
    ("Revisión", "06_review"),
    ("Exportaciones", "07_exports"),
    ("Configuración", "08_settings"),
)

COMMON = {
    "all": "Todo",
    "language": "Idioma",
    "market": "Mercado",
    "category": "Categoría",
    "status": "Estado",
    "title": "Título",
    "summary": "Resumen",
    "source": "Fuente",
    "source_url": "URL de la fuente",
    "notes": "Notas",
    "save": "Guardar",
    "edit": "Editar",
    "approve": "Aprobar",
    "reject": "Rechazar",
    "archive": "Archivar",
    "pending": "Pendiente",
    "approved": "Aprobado",
    "rejected": "Rechazado",
    "exported": "Exportado",
    "manual_mode": "Modo manual gratuito",
    "automatic_mode": "Modo automático opcional",
}

LANGUAGE_LABELS_ES = {
    "en": "Inglés",
    "es": "Español",
    "hi": "Hindi",
    "hi_hinglish": "Hindi/Hinglish",
}

MARKET_LABELS = {
    "global": "Global",
    "us": "Estados Unidos",
    "spain": "España",
    "latam": "LATAM",
    "india": "India",
    "spain_latam": "España/LATAM",
}

CATEGORY_LABELS = {
    "ai_tools": "IA",
    "tech_explained": "Tecnología",
    "science_explained": "Ciencia",
    "business_case": "Negocios",
    "internet_culture_explained": "Internet/cultura viral",
    "engineering": "Ingeniería",
    "psychology": "Psicología",
    "productivity": "Productividad",
    "finance_educational": "Finanzas educativas",
    "history_explained": "Historia explicada",
    "mystery_explained": "Misterios explicados",
    "other": "Otro",
}

STATUS_LABELS = {
    "active": "Activo",
    "paused": "Pausado",
    "idea": "Idea",
    "approved_for_hooks": "Aprobada para ganchos",
    "rejected": "Rechazada",
    "archived": "Archivada",
    "draft": "Borrador",
    "needs_review": "Necesita revisión",
    "approved": "Aprobado",
    "localized": "Localizado",
    "pending": "Pendiente",
    "generating": "Generando",
    "generated": "Generado",
    "imported_manual": "Importado manualmente",
    "placeholder": "Placeholder sin voz",
    "ready": "Listo",
    "rendering": "Renderizando",
    "rendered": "Render generado",
    "failed": "Fallido",
    "exported": "Exportado",
    "confirmation_required": "Requiere confirmacion",
    "cancelled": "Cancelado",
    "suggested": "Sugerida",
    "selected": "Elegida",
    "saved_for_later": "Guardada para después",
    "discarded": "Descartada",
    "converted_to_topic": "Convertida en idea principal",
    "edited": "Editada",
    "used_in_render": "Usado en render",
    "needs_license_review": "Revisar licencia",
    "estimated": "Estimado",
    "confirmed": "Confirmado",
    "billed": "Facturado",
    "needs_changes": "Necesita cambios",
    "needs_asset": "Necesita asset",
    "mapped": "Mapeada",
    "created": "Creado",
    "running": "Ejecutando",
    "completed": "Completado",
    "sent_to_creation": "Enviada a creacion",
    "processed": "Procesada",
    "metadata_selected": "Metadata elegida",
    "character_selected": "Personaje elegido",
    "script_draft": "Guion borrador",
    "script_approved": "Guion aprobado",
    "voiceover_generated": "Voz generada",
    "voiceover_failed": "Voz fallida",
    "scenes_planned": "Escenas planificadas",
    "manual_required": "Requiere modo manual",
    "pending_confirmation": "Pendiente de confirmacion",
    "registered": "Registrado",
}

WIZARD_STEP_LABELS = {
    WizardStep.BASIC_DATA: "Datos basicos",
    WizardStep.RESEARCH: "Investigar",
    WizardStep.IDEA_SELECTION: "Elegir idea",
    WizardStep.HOOK_SELECTION: "Elegir gancho",
    WizardStep.TITLE_SELECTION: "Elegir título",
    WizardStep.METADATA: "Metadata",
    WizardStep.SCRIPT_GENERATION: "Generar guion",
    WizardStep.CHARACTER: "Personaje",
    WizardStep.STORYBOARD: "Storyboard Nero",
    WizardStep.PROMPT_PACK: "Prompts Higgsfield/Picsart",
    WizardStep.LOCALIZATION: "Localizar",
    WizardStep.VOICEOVER: "Voz",
    WizardStep.MUSIC_SELECTION: "Subtitulos y musica",
    WizardStep.CLIP_IMPORT: "Importar clips",
    WizardStep.SCENE_MAPPING: "Asociar clips",
    WizardStep.VISUAL_STYLE: "Estilo visual",
    WizardStep.RENDER: "Renderizar",
    WizardStep.REVIEW: "Revisar",
    WizardStep.EXPORT: "Exportar",
}

WIZARD_STEP_DESCRIPTIONS = {
    WizardStep.BASIC_DATA: "Define canal, personaje y parametros base del Short.",
    WizardStep.RESEARCH: "Elige idioma, mercado y categoría para preparar la investigación.",
    WizardStep.IDEA_SELECTION: "Compara ideas sugeridas y decide cuál merece convertirse en vídeo.",
    WizardStep.HOOK_SELECTION: "Elige el gancho más fuerte para el primer segundo.",
    WizardStep.TITLE_SELECTION: "Selecciona un título claro, corto y sin clickbait falso.",
    WizardStep.SCRIPT_GENERATION: "Genera, pega o edita el guion por líneas.",
    WizardStep.LOCALIZATION: "Prepara versiones adaptadas por idioma sin traducción literal.",
    WizardStep.VOICEOVER: "Decide si usarás voz manual, placeholder o TTS opcional.",
    WizardStep.MUSIC_SELECTION: "Genera subtitulos SRT y elige musica segura de la biblioteca local.",
    WizardStep.VISUAL_STYLE: "Selecciona plantilla, ritmo visual y estilo de subtítulos.",
    WizardStep.RENDER: "Genera un vídeo vertical 1080x1920 para revisión.",
    WizardStep.REVIEW: "Completa la checklist humana obligatoria.",
    WizardStep.EXPORT: "Crea el paquete final para subir manualmente a YouTube Studio.",
}

WIZARD_STEP_DESCRIPTIONS.update(
    {
        WizardStep.METADATA: "Prepara descripcion, hashtags, comentario fijado y notas de disclosure.",
        WizardStep.CHARACTER: "Confirma que Nero sera el personaje protagonista y revisa su Character Bible.",
        WizardStep.STORYBOARD: "Genera escenas visuales con acciones, poses, variantes y prompts de Nero.",
        WizardStep.PROMPT_PACK: "Exporta el paquete de prompts para Higgsfield/Picsart.",
        WizardStep.CLIP_IMPORT: "Importa clips generados fuera y confirma licencia/uso comercial.",
        WizardStep.SCENE_MAPPING: "Asocia cada clip importado a su escena del storyboard.",
    }
)

REVIEW_LABELS = {
    "hook_strong": "El gancho engancha en el primer segundo.",
    "script_fact_checked": "El guion no inventa datos y los datos importantes están revisados.",
    "language_natural": "El idioma suena natural.",
    "music_license_ok": "La música tiene licencia registrada.",
    "assets_license_ok": "Los recursos tienen licencia registrada.",
    "no_reused_content_risk": "No hay clips robados ni riesgo claro de contenido reutilizado.",
    "no_sensitive_content": "No hay contenido sensible peligroso.",
    "subtitles_readable": "Los subtítulos se leen bien.",
    "audio_clear": "El audio se escucha bien.",
    "video_not_too_repetitive": "El vídeo no parece contenido repetitivo generado en masa.",
    "metadata_not_misleading": "El título y la descripción no son engañosos.",
    "made_for_kids_false_confirmed": "Se confirma que no es contenido para niños.",
    "synthetic_media_reviewed": "Se revisó si hay contenido sintético o IA.",
}


def label_for(mapping: dict[str, str], value: object) -> str:
    return mapping.get(str(value), str(value))
