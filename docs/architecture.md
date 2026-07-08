# Architecture

ShortsFactory is intentionally local-first. The first version uses Streamlit, SQLite, SQLAlchemy, and small Python services so the workflow can run on one machine without cloud accounts or paid APIs.

## Decisions

- The repository root is the application root. The spec names `ShortsFactory/`, but this workspace already represents that project.
- The database is local SQLite at `data/shorts_factory.db`.
- SQLAlchemy models define persistence, while service modules keep business logic away from Streamlit pages.
- AI generation is manual copy/paste in the MVP. Prompt templates live in `app/prompts`.
- The V1 product shell is Spanish-first and uses `app/i18n/es.py` for shared UI labels.
- The guided production flow is modeled by `WizardStep` and `app/core/wizard.py`.
- FFmpeg is called with argument lists, not shell strings, to avoid command injection.
- Export is blocked by service logic unless a review checklist is approved.
- Topic scoring normalizes the weighted formula to 0-100 by dividing by the maximum positive score, then clamps to 0-100.
- File paths are validated through `app/utils/safe_paths.py` to reduce traversal and overwrite risks.

## V1 automation direction

The new product direction is a guided assistant rather than a generic database. Iteration 1 adds Spanish navigation, a 12-step wizard, and entry pages for trend research, localization, and voiceover. Providers for RSS, Hacker News, YouTube Data API, Reddit, Google Trends, Ollama, and optional LLM APIs should be added behind service abstractions in later iterations.

Iteration A adds trend research providers:

- `ManualInputProvider` for pasted text/URLs/headlines.
- `RSSFeedProvider` for configured public feeds.
- `HackerNewsProvider` for the public Firebase API.
- `YouTubeSearchProvider` as an optional, key-gated provider stub.

`TrendResearchService` orchestrates providers, deduplicates by URL/title hash, sorts basic popularity signals, and returns normalized `TrendItem` objects.

Iteration B adds the scoring and idea layer:

- `GeneratedIdea` persists original short ideas before they become full topics.
- `TrendScoringService` scores trend and idea candidates from 0-100 with separate 0-10 factors for viral potential, RPM, visual ease, narrative clarity, evergreen value, novelty, production ease, copyright risk, and monetization risk.
- `IdeaGenerationService` turns normalized `TrendItem` objects into heuristic ideas without requiring an LLM.
- `generated_idea_cards` prepares reusable card data for Streamlit pages.
- `convert_generated_idea_to_topic` maps a generated idea into a `Topic` with `approved_for_hooks` status.
- The wizard stores selected generated idea/topic IDs in Streamlit session state because the project does not yet have a persistent `WizardSession` table.

Iteration C1/C2 starts supervised creative automation:

- `app/llm` defines a common `LLMProvider` interface plus `ManualLLMProvider`, `OpenAILLMProvider`, and `OllamaLLMProvider`.
- `ManualLLMProvider` is always available and prepares copy/paste prompts; it does not call external services.
- OpenAI and Ollama providers are optional and disabled by default through `.env` flags.
- `app/ai/llm_orchestrator.py` selects providers and reports availability without exposing API keys.
- `HookGenerationService` creates 25 hook candidates from a selected topic, using heuristics as the no-key fallback and optional LLM JSON when configured.
- Generated hooks reuse the existing `Hook` table. Extra candidate metadata is stored in `Hook.notes` as JSON to avoid a disruptive migration.
- The wizard stores selected hook IDs in Streamlit session state and blocks title selection until a hook is chosen.

Iteration C3/C4 completes the core creative text draft:

- `GeneratedTitle` persists title candidates linked to topic/hook.
- `MetadataSuggestion` persists description, hashtags, pinned comment and upload notes.
- `TitleGenerationService` creates title cards with clarity, curiosity, SEO, CTR, clickbait risk and total score.
- `MetadataGenerationService` creates safe upload metadata with 3-5 hashtags and `#shorts`.
- `ScriptGenerationService` creates structured `Script` and `ScriptLine` records using the existing script schema.
- `FactCheckHelperService` marks numbers, dates, money, absolutes and high-risk domains as claims needing source review.
- `ContentQualityService` scores draft scripts and blocks obvious issues such as empty scripts or generic intros.
- Script-specific C3/C4 metadata is stored in existing fields such as `fact_check_notes`, avoiding a risky SQLite column migration for now.

## Boundaries

The app does not upload, publish, scrape, bypass copyright systems, or store secrets in code. Future API integrations must keep manual review and auditability as product requirements.
