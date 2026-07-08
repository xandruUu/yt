# Picsart

La primera integracion es manual/handoff y la API queda preparada como opcional.

ShortsFactory genera:

- `README_PICSART.md`
- `asset_processing_plan.md`
- `clip_processing_plan.csv`
- `scene_asset_map.json`
- `resize_crop_instructions.md`
- `background_instructions.md`

Operaciones previstas para API futura:

- trim
- crop
- fit
- resize
- remove_background
- change_background
- adjust
- effects
- concat
- extract_thumbnail

Sin `PICSART_API_KEY`, usa el modo manual: procesa fuera, descarga resultados e importa assets en ShortsFactory.
