# ShortsFactory

ShortsFactory es una herramienta local y revisada por humanos para producir YouTube Shorts. La V1 evoluciona hacia un asistente guiado en español: investiga o prepara ideas, propone ganchos, ayuda a crear guiones, organiza música/recursos con licencia, renderiza, exige checklist y exporta paquetes listos para subida manual.

La app no sube vídeos a YouTube, no publica automáticamente, no descarga clips de redes sociales y no requiere APIs de pago para funcionar.

## Alcance V1

- Dashboard local en Streamlit.
- Interfaz principal en español.
- Pantalla `Crear Short paso a paso` con 12 fases.
- Base de datos SQLite con SQLAlchemy.
- Investigacion de tendencias con conversion a ideas originales puntuadas.
- Generacion automatica supervisada de hooks desde una idea elegida.
- Generacion automatica supervisada de titulos, metadata y guion por lineas.
- Voz supervisada con `VoiceoverJob`: placeholder sin voz, importacion manual y proveedores TTS opcionales.
- Subtitulos SRT generados desde el guion, editables y aprobables antes de renderizar.
- Plan visual por escenas y `RenderPlan` validado antes de FFmpeg.
- Herramientas externas: ElevenLabs opcional, prompt packs Higgsfield/Picsart, importacion de clips externos y costes auditables.
- Flujo de ideas, ganchos, guiones, localización, voces, música/recursos, render, revisión y exportación.
- Modo manual gratuito mediante prompts copiables.
- Render vertical básico 1080x1920 con FFmpeg cuando esté instalado.
- Checklist humana obligatoria antes de exportar.

## Instalación

```bash
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
```

On macOS/Linux:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## FFmpeg

FFmpeg solo es obligatorio para renderizar vídeo.

Windows:

1. Download FFmpeg from https://ffmpeg.org/download.html.
2. Add the `bin` folder to `PATH`.
3. Check:

```bash
ffmpeg -version
```

## Ejecutar

```bash
.\.venv\Scripts\streamlit.exe run app/main.py
```

La app inicializa `data/shorts_factory.db` automáticamente al arrancar.

Abre:

```text
http://localhost:8501
```

## Modo guiado

La entrada principal es `Crear Short paso a paso`.

Fases:

1. Investigar.
2. Elegir idea.
3. Elegir gancho.
4. Elegir título.
5. Generar guion.
6. Localizar.
7. Voz.
8. Subtitulos y musica.
9. Estilo visual.
10. Renderizar.
11. Revisar.
12. Exportar.

La Iteración 1 deja lista la estructura del wizard, navegación española y pantallas base. Las siguientes iteraciones conectan proveedores de tendencias, scoring automático, generación de ideas, hooks, títulos y guiones.

## Investigacion de tendencias

La pantalla `Investigador de tendencias` y el paso 1 del wizard ya pueden usar:

- Manual: pega titulares, URLs, temas o texto libre.
- RSS: lee feeds configurados en `config/rss_sources.json`.
- Hacker News: usa la API publica para top stories.
- YouTube Data API: proveedor opcional; avisa si no hay `YOUTUBE_DATA_API_KEY`.

Los resultados se normalizan como tendencias, se deduplican y pueden convertirse en ideas originales puntuadas.

## Como pasar de tendencias a ideas

El flujo nuevo convierte senales de tendencia en `GeneratedIdea` persistentes sin depender de LLM ni APIs de pago:

1. Abre `Crear Short paso a paso`.
2. En `Investigar`, elige idioma, mercado, categoria, fuentes y pega senales manuales si quieres.
3. Pulsa `Investigar ideas`.
4. Selecciona una o varias tendencias y pulsa `Generar ideas desde tendencias`.
5. Ve al paso `Elegir idea`.
6. Revisa las cards con score total, viralidad, RPM, evergreen, riesgos, angulo, resumen, visual sugerido y fuentes.
7. Usa `Elegir idea`, `Guardar para despues`, `Descartar`, `Editar` o `Convertir en idea principal`.
8. Al convertir, se crea un `Topic` real con estado `approved_for_hooks` para continuar con ganchos.

Tambien puedes hacer el mismo flujo desde `Investigador de tendencias`, que muestra las ideas generadas y permite convertirlas en ideas principales.

## Como pasar de idea a hooks

La Iteracion C1/C2 anade providers LLM y generacion supervisada de hooks:

1. En `Crear Short paso a paso`, elige o convierte una idea en el paso `Elegir idea`.
2. En `Elegir gancho`, pulsa `Generar 25 hooks automaticamente`.
3. El modo `Manual/gratis` funciona sin API keys y usa plantillas heuristicas.
4. `Ollama local` y `OpenAI opcional` quedan disponibles solo si los activas en `.env`.
5. Revisa las cards de hooks con claridad, curiosidad, emocion, riesgo y score total.
6. Pulsa `Elegir gancho` para pasar al paso de titulos.

Tambien puedes generar hooks desde la pantalla `Ganchos`. La app no aprueba ni publica nada automaticamente: solo genera sugerencias y espera tu seleccion.

## De hook elegido a guion aprobado

La Iteracion C3/C4 completa la parte creativa principal:

1. En `Elegir gancho`, elige un hook.
2. En `Elegir titulo`, pulsa `Generar titulos automaticamente`.
3. Revisa claridad, curiosidad, SEO, CTR, riesgo clickbait y longitud.
4. Pulsa `Elegir titulo`; la app genera metadata sugerida.
5. En `Generar guion`, elige formato, duracion, tono e idioma.
6. Pulsa `Generar guion automatico`.
7. Edita la tabla de lineas si hace falta.
8. Revisa warnings de claims y calidad.
9. Pulsa `Aprobar guion` para desbloquear el paso de voz.

El fallback sin API genera titulos, metadata y guion por lineas de forma heuristica. OpenAI/Ollama siguen siendo opcionales y desactivados por defecto.

## De guion aprobado a render

La Iteracion D conecta el tramo final de produccion dentro de `Crear Short paso a paso`:

1. En `Voz`, elige `Sin voz` para crear un placeholder o importa una grabacion local `.mp3`, `.wav`, `.m4a`, `.aac` u `.ogg`.
2. Aprueba la voz si es manual. El placeholder puede usarse para avanzar sin narracion.
3. En `Subtitulos y musica`, pulsa `Generar subtitulos desde guion`, revisa/edita la tabla y aprueba el SRT.
4. Elige musica segura si ya la registraste en `Musica y recursos`; si no, puedes continuar sin musica.
5. En `Estilo visual`, genera un plan visual por escenas y apruebalo.
6. En `Renderizar`, crea el `RenderPlan`, valida requisitos y renderiza con FFmpeg.
7. El render generado pasa a `Revision`; la checklist humana sigue siendo obligatoria antes de exportar.

Lo que ya hace:

- Crea registros `VoiceoverJob`, `SubtitleTrack`, `VisualPlan` y `RenderPlan`.
- Permite continuar sin voz usando audio silencioso.
- Genera SRT desde las lineas del guion y lo guarda en `outputs/subtitles`.
- Valida que guion, subtitulos, plan visual, musica y FFmpeg esten listos antes de renderizar.
- Mezcla voz/musica locales cuando existen archivos de audio y FFmpeg esta disponible.
- Exporta tambien `subtitles.srt`, `voiceover.txt`, `visual_plan.json` y `render_plan.json`.

Lo que no hace todavia:

- No graba voz desde microfono dentro del navegador.
- No llama a OpenAI TTS, ElevenLabs ni motores locales por defecto; ElevenLabs ya esta preparado como API opcional y requiere key + confirmacion de coste.
- No descarga musica, imagenes, clips ni recursos externos.
- No genera visuales complejos por escena; el render actual usa plantilla/fondo, subtitulos y audio local.
- No sube ni publica en YouTube.

## Herramientas externas

La Iteracion E anade una pantalla `Herramientas externas`:

- `Estado`: muestra providers, modo, disponibilidad, key requerida y coste posible.
- `ElevenLabs`: genera voiceover real si configuras API key y confirmas coste.
- `Higgsfield`: crea prompt packs manuales por escena para generar clips fuera.
- `Picsart`: crea planes manuales de procesado/crop/fit para clips y deja API preparada.
- `Paquetes`: lista prompt packs y permite marcarlos como usados manualmente.
- `Clips`: importa assets externos, valida extension/tamano y exige licencia/uso comercial.
- `Costes`: registra eventos estimados/reales de operaciones externas.

El modo sin API sigue funcionando. Higgsfield/Picsart empiezan como handoff manual: ShortsFactory genera prompts/instrucciones, el usuario usa la herramienta externa, descarga resultados y los importa.

Para activar ElevenLabs:

```env
ENABLE_ELEVENLABS=true
ENABLE_ELEVENLABS_TTS=true
ELEVENLABS_API_KEY=tu_key
ELEVENLABS_DEFAULT_VOICE_ID=tu_voice_id
ELEVENLABS_MODEL_ID=eleven_multilingual_v2
```

Antes de generar voz aparece confirmacion porque puede consumir creditos. La app no guarda la API key en base de datos ni la muestra en pantalla.

## Tests

```bash
.\.venv\Scripts\python.exe -m pytest
```

If dependencies are not installed yet, the pure-Python smoke option is:

```bash
python -m unittest discover tests
```

## Lint

```bash
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format .
```

## Reglas de seguridad

- Las claves van en `.env`, nunca en código.
- `.env` está ignorado por Git.
- No hay subida ni publicación automática a YouTube.
- No hay scraping de clips virales.
- No se aprueba música o recursos sin licencia registrada.
- No se exporta sin checklist aprobada.

## Flujo recomendado ahora

1. Abre `Crear Short paso a paso`.
2. Define idioma, mercado, categoría y número de ideas.
3. Investiga tendencias desde fuentes manuales, RSS o Hacker News.
4. Genera ideas originales desde las tendencias seleccionadas.
5. Elige, guarda, descarta, edita o convierte una idea en `Topic`.
6. Genera 25 hooks y elige el gancho ganador.
7. Genera titulos y elige el titulo ganador.
8. Genera metadata sugerida.
9. Genera, edita y aprueba el guion por lineas.
10. Crea voz placeholder o importa una voz manual.
11. Genera y aprueba subtitulos; elige musica segura si existe.
12. Genera plan visual, renderiza, revisa y exporta.
