# Roadmap

## Phase 1: Local MVP

Topics, hooks, scripts, subtitles, music and asset registries, basic render, review checklist, export package, README, and tests.

## Phase 2: Optional AI automation

Optional LLM provider configuration, generation buttons, cost tracking, and manual fallback.

## Completed iteration B: Trends to scored ideas

- Trend candidates can become persisted `GeneratedIdea` records.
- Ideas receive heuristic scores and risk checks.
- The trend research page and guided wizard can show actionable idea cards.
- Ideas can be selected, saved for later, discarded, edited, or converted into `Topic` records.

## Iteration C: Creative automation

Connect the selected idea/topic to hook generation, title generation, and script generation so the wizard can move from `Elegir gancho` to `Generar guion` with fewer manual steps.

## Completed iteration C1/C2: LLM providers and hooks

- Added common LLM provider contracts.
- Added manual, OpenAI optional, and Ollama optional providers.
- Added provider status in settings.
- Added automatic supervised hook generation with no-key heuristic fallback.
- Connected hook generation and hook selection in the wizard.

## Iteration C3/C4 scope: Titles, metadata, and script

Generate title candidates from the selected hook, choose a title, generate metadata, then create an editable script by lines.

## Completed iteration C3/C4: Titles, metadata, and script

- Added generated title persistence and selection.
- Added metadata suggestions with safe hashtags.
- Added automatic script generation by lines.
- Added basic fact-check warnings and quality reports.
- Connected the wizard from selected hook to approved script.

## Next iteration D: Voice, subtitles, visual plan, render

Generate/import voiceover, create approximate subtitles, build a visual plan and render a supervised draft video.

## Completed iteration E foundation: External tools

- Added external tool provider base and registry.
- Added optional ElevenLabs API provider with paid confirmation, cost audit and timing fallback.
- Added prompt packs for Higgsfield and Picsart manual handoff.
- Added imported external asset library with license/commercial-use gates.
- Added `Herramientas externas` UI and cost tracking.

Remaining E work:

- Render external clips directly per scene.
- Picsart API execution.
- Higgsfield MCP execution if stable.

## Phase 3: Voiceover

Manual recording, audio import, local TTS, optional premium TTS, and subtitle/audio sync.

## Phase 4: Visual polish

More templates, licensed B-roll, animation, graphs, SFX, waveforms, and channel-specific styles.

## Phase 5: Analytics

Manual metrics, dashboards by language/category/hook/duration, and retention learning loops.

## Phase 6: YouTube API

Optional private upload only, OAuth, logs, audit state, and supervised actions.
