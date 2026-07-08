# Workflow

```text
Investigar
  -> Elegir idea
  -> Elegir gancho
  -> Elegir título
  -> Generar guion
  -> Localizar
  -> Voz
  -> Subtitulos y musica
  -> Elegir estilo visual
  -> Renderizar
  -> Revisar
  -> Exportar
  -> Subida manual
```

## Approval gates

- A topic should be approved before hook work.
- A script must be approved before voice, subtitles, visual planning and rendering.
- Voice must be approved, or explicitly set as placeholder/no voice.
- Subtitles must be generated/edited and approved before rendering.
- A visual plan must be approved before rendering.
- Music is optional, but selected music must be marked safe for monetization.
- A review checklist must be approved before export.
- An export package must exist before a video can be marked as manually published.

## Tendencias a ideas

Iteration B adds a concrete pre-topic stage:

```text
TrendItem
  -> GeneratedIdea scored with viral/RPM/visual/evergreen/risk heuristics
  -> selected/saved/discarded/edited in the UI
  -> converted into Topic approved_for_hooks
```

The wizard now expects an idea selection before moving from `Elegir idea` to `Elegir gancho`. This can be either a selected `GeneratedIdea` or a converted `Topic`.

## Idea a hooks

Iteration C1/C2 adds the first supervised creative automation step:

```text
Topic approved_for_hooks
  -> generate 25 Hook candidates
  -> review hook cards
  -> select one Hook
  -> continue to title generation
```

The default path uses heuristic generation and costs nothing. Optional LLM providers can be enabled, but a selected hook is still required before the wizard advances to `Elegir titulo`.

## Hook a guion aprobado

Iteration C3/C4 adds:

```text
Selected Hook
  -> GeneratedTitle candidates
  -> selected GeneratedTitle
  -> MetadataSuggestion
  -> structured Script + ScriptLine records
  -> fact-check/quality warnings
  -> approved Script
  -> Voice step unlocked
```

The app can generate titles, metadata and scripts without API keys. Approval remains human-supervised: a script must be approved before the wizard can continue to `Voz`.

## Guion aprobado a render

Iteration D adds the supervised production stage:

```text
Approved Script
  -> VoiceoverJob (placeholder, manual import or optional TTS)
  -> SubtitleTrack SRT
  -> optional safe MusicTrack
  -> VisualPlan scenes
  -> optional external prompt packs / imported clips
  -> RenderPlan validation
  -> FFmpeg render
  -> review checklist
  -> export package for manual upload
```

The default path needs no paid API: choose placeholder/no voice, generate SRT from script lines, skip music if there is no safe track, approve the visual plan and render with FFmpeg. External TTS providers remain disabled unless configured.

## Herramientas externas

Iteration E adds:

```text
Approved Script / VisualPlan
  -> ElevenLabs optional TTS
  -> Higgsfield prompt pack
  -> Picsart processing pack
  -> ExternalAsset import
  -> license/commercial-use review
  -> render/export gates
```

External APIs are optional. Manual prompt packs are the default path for Higgsfield and Picsart.
