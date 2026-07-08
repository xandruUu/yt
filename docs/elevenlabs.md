# ElevenLabs

ElevenLabs esta integrado como proveedor API opcional.

Variables:

```env
ENABLE_ELEVENLABS=true
ENABLE_ELEVENLABS_TTS=true
ELEVENLABS_API_KEY=
ELEVENLABS_DEFAULT_VOICE_ID=
ELEVENLABS_MODEL_ID=eleven_multilingual_v2
ELEVENLABS_OUTPUT_FORMAT=mp3_44100_128
```

Flujo:

1. Aprueba un guion.
2. En `Voz` o `Herramientas externas > ElevenLabs`, introduce voice/model.
3. Revisa caracteres y coste estimado.
4. Confirma la operacion potencialmente de pago.
5. Genera audio.
6. Previsualiza y aprueba el `VoiceoverJob`.

La integracion intenta `/with-timestamps` para alignment y, si no funciona, cae a TTS normal. La API key se lee de `.env` y no se guarda en DB.
