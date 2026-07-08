# Generar ideas originales desde tendencias

Eres un estratega experto en YouTube Shorts, retención y monetización.

A partir de estas tendencias, genera ideas originales para Shorts.

Tendencias:
{{trend_items}}

Idioma objetivo:
{{target_language}}

Mercado objetivo:
{{target_market}}

Categoría:
{{category}}

Reglas:
- No copies títulos existentes.
- No copies el texto de las fuentes.
- Transforma cada tendencia en ángulos originales.
- Cada idea debe poder explicarse en 30-45 segundos.
- Prioriza ideas con gancho fuerte en el primer segundo.
- Prioriza temas visuales y fáciles de explicar.
- Prioriza temas con potencial de RPM alto si el nicho lo permite.
- Evita temas con alto riesgo de copyright.
- Evita depender de clips de terceros.
- Evita claims falsos o imposibles de verificar.
- Evita contenido sensible innecesario.
- Devuelve JSON válido.

Formato de salida:
[
  {
    "titulo": "...",
    "angulo": "...",
    "resumen": "...",
    "por_que_puede_funcionar": "...",
    "publico_objetivo": "...",
    "duracion_sugerida": "30-45s",
    "formato_sugerido": "documental rapido",
    "tipo_hook_sugerido": "misterio",
    "visual_sugerido": "...",
    "potencial_viral": 8,
    "potencial_rpm": 7,
    "facilidad_visual": 8,
    "claridad_narrativa": 8,
    "evergreen": 6,
    "novedad": 7,
    "facilidad_produccion": 8,
    "riesgo_copyright": 2,
    "riesgo_monetizacion": 2
  }
]
