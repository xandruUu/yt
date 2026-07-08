# Configuracion De APIs Opcionales

ShortsFactory funciona sin API keys. El modo manual permite pegar senales, copiar prompts y pegar respuestas de ChatGPT/Codex.

## YouTube Data API

Uso previsto en esta fase:

- Investigar temas.
- Analizar titulos y metadatos publicos.
- No subir videos.
- No publicar.

Variable:

```env
YOUTUBE_DATA_API_KEY=
```

Si falta la clave, la app muestra un aviso y recomienda modo manual, RSS o Hacker News.

## Reddit API

Uso previsto:

- Detectar debates y preguntas.
- No copiar posts literalmente.
- No scrapear HTML.

Variables:

```env
REDDIT_CLIENT_ID=
REDDIT_CLIENT_SECRET=
REDDIT_USER_AGENT=ShortsFactoryLocal/1.0
```

## OpenAI Opcional

Uso previsto:

- Generar hooks, titulos, guiones y metadatos automaticamente.
- Solo se usa si `ENABLE_OPENAI_LLM=true`.
- Puede generar coste, por eso esta desactivado por defecto.

Variables:

```env
DEFAULT_LLM_PROVIDER=manual
OPENAI_API_KEY=
OPENAI_TEXT_MODEL=gpt-4.1-mini
ENABLE_OPENAI_LLM=false
ENABLE_AUTO_LLM=false
```

## Ollama Opcional

Uso previsto:

- Generacion local sin proveedor de pago.
- Solo se usa si `ENABLE_OLLAMA=true` y Ollama esta corriendo.

Variables:

```env
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1
ENABLE_OLLAMA=false
```

## ElevenLabs Opcional

Uso previsto:

- Generar voiceovers naturales desde guiones aprobados.
- Intentar timing/alignment si la API lo devuelve.
- Registrar coste estimado y evento de auditoria.

Variables:

```env
ENABLE_ELEVENLABS=true
ENABLE_ELEVENLABS_TTS=true
ELEVENLABS_API_KEY=
ELEVENLABS_DEFAULT_VOICE_ID=
ELEVENLABS_MODEL_ID=eleven_multilingual_v2
ELEVENLABS_OUTPUT_FORMAT=mp3_44100_128
```

La UI exige confirmacion antes de ejecutar una operacion potencialmente de pago.

## Higgsfield Opcional

Uso previsto:

- Generar prompt packs manuales para clips por escena.
- MCP queda desactivado por defecto.

Variables:

```env
ENABLE_HIGGSFIELD_MANUAL=true
ENABLE_HIGGSFIELD_MCP=false
HIGGSFIELD_MCP_URL=https://mcp.higgsfield.ai/mcp
```

## Picsart Opcional

Uso previsto:

- Generar planes manuales de crop/fit/procesado.
- API queda preparada pero desactivada por defecto.

Variables:

```env
ENABLE_PICSART_MANUAL=true
ENABLE_PICSART_API=false
PICSART_API_KEY=
```
