# ShortsFactory canonical pipeline

Este documento declara el flujo principal de la app y separa los modulos legacy que se conservan para compatibilidad y depuracion.

## Flujo canonico

El camino oficial para crear un short es:

```text
Inicio
  -> Investigacion
  -> Creacion
  -> Ideas
  -> Produccion
  -> Personajes
  -> Mapeo de clips
  -> Renderizar
  -> Revision
  -> Exportaciones
```

Modelos principales:

```text
ResearchRun
ProviderFetchLog
TrendItem
IdeaCandidate
CreationInboxItem
DeepResearchRun
DeepIdeaCandidate
MetadataRecipeDraft
VideoProject
ScriptDraft
VoiceoverJob
SceneSlot
SceneCandidate
SelectedScene
HiggsfieldPromptPack
HiggsfieldJob
GeneratedClip
RenderJob
```

Responsabilidades:

- Investigacion genera tendencias e ideas candidatas.
- Creacion profundiza una idea y produce angulos/subideas.
- Ideas selecciona titulo, descripcion, hashtags, hook y crea el VideoProject.
- Produccion selecciona personaje, guion, voz, escenas, prompt packs y jobs Higgsfield pendientes.
- Mapeo de clips asocia clips reales a escenas.
- Renderizar monta preview/render y avisa si faltan clips reales.
- Revision valida calidad y riesgos.
- Exportaciones prepara el paquete final de publicacion.

## Modulos legacy

Estos modulos no se borran todavia. Por defecto quedan ocultos detras de:

```env
SHOW_LEGACY_MODULES=false
```

Si se activa `SHOW_LEGACY_MODULES=true`, aparecen bajo `Legacy / Avanzado`:

```text
Crear Short paso a paso
Ideas antiguas
Ganchos
Guiones
Localizacion
Storyboard Nero
Voces
Herramientas externas
Musica y recursos
```

Modelos legacy principales:

```text
Topic
GeneratedIdea
Hook
Script
ScriptLine
Voiceover
VisualPlan
PromptPack
ExternalToolJob
ExternalAsset
Render
```

Estos modulos siguen siendo utiles para datos antiguos, pruebas manuales y funciones aun no migradas, pero no deben presentarse como el flujo principal.

## Estado actual de Higgsfield

La app prepara `HiggsfieldPromptPack` y `HiggsfieldJob`, pero no envia aun generaciones reales al CLI/MCP.

Estado actual:

```text
SelectedScene
  -> HiggsfieldPromptPack
  -> HiggsfieldJob pending_confirmation/manual_required
```

Reglas actuales:

- No se ejecuta una generacion pagada automaticamente.
- El texto de la UI indica que solo se prepara el payload/job.
- Para la misma `selected_scene_id` y `prompt_pack_id`, se reutiliza un job activo existente.
- Solo se crea otro intento si el usuario marca explicitamente `Crear nuevo intento aunque ya exista uno`.

Estado futuro:

```text
Confirmacion humana
  -> higgsfield generate create ...
  -> external_job_id
  -> polling
  -> GeneratedClip
```

## Estado actual de Render

`Renderizar` conserva compatibilidad con el flujo legacy basado en `Script` y `ScriptLine`.

Mientras no existan `GeneratedClip` mapeados para todas las `SelectedScene` del proyecto canonico, la pantalla debe avisar que el render puede usar visuales fallback/placeholder y que no es el render final de produccion.

Render canonico deseado:

```text
VideoProject
  -> ScriptDraft aprobado
  -> VoiceoverJob aprobado
  -> SelectedScene[]
  -> GeneratedClip[] mapeados
  -> SubtitleTrack
  -> MusicResource opcional
  -> RenderJob
```

## Plan de migracion

1. Mantener legacy oculto por defecto.
2. Usar el flujo canonico para nuevos proyectos.
3. Migrar funciones utiles de legacy a Produccion/Ideas/Exportaciones.
4. Implementar submit real Higgsfield con confirmacion humana, coste visible y deduplicacion.
5. Implementar render canonico con clips reales, voz, subtitulos y musica.
6. Borrar legacy solo cuando no queden imports, datos o funciones necesarias.

## Reglas de seguridad

- No commitear `.env`, `.venv`, outputs ni medios generados pesados.
- No mostrar API keys en UI ni logs.
- No hacer migraciones destructivas sin backup.
- No enviar jobs pagados sin confirmacion humana.
