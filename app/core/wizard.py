from __future__ import annotations

from dataclasses import dataclass

from app.core.enums import WizardStep


@dataclass(frozen=True)
class WizardStepDefinition:
    step: WizardStep
    index: int
    title: str
    action_hint: str


WIZARD_STEPS: tuple[WizardStepDefinition, ...] = (
    WizardStepDefinition(WizardStep.BASIC_DATA, 1, "Datos basicos", "Elegir canal, idioma, mercado y Nero."),
    WizardStepDefinition(WizardStep.RESEARCH, 2, "Investigar", "Definir idioma, mercado y categoria."),
    WizardStepDefinition(WizardStep.IDEA_SELECTION, 3, "Elegir idea", "Escoger una idea candidata."),
    WizardStepDefinition(WizardStep.HOOK_SELECTION, 4, "Elegir gancho", "Seleccionar o editar el gancho."),
    WizardStepDefinition(WizardStep.TITLE_SELECTION, 5, "Elegir titulo", "Elegir titulo corto y seguro."),
    WizardStepDefinition(WizardStep.METADATA, 6, "Metadata", "Preparar descripcion, hashtags y notas."),
    WizardStepDefinition(WizardStep.SCRIPT_GENERATION, 7, "Generar guion", "Crear y revisar lineas."),
    WizardStepDefinition(WizardStep.CHARACTER, 8, "Personaje", "Confirmar Character Bible de Nero."),
    WizardStepDefinition(WizardStep.STORYBOARD, 9, "Storyboard Nero", "Crear escenas visuales por linea."),
    WizardStepDefinition(WizardStep.PROMPT_PACK, 10, "Prompt Pack", "Exportar prompts Higgsfield/Picsart."),
    WizardStepDefinition(WizardStep.VOICEOVER, 11, "Voz", "Elegir modo de voz."),
    WizardStepDefinition(WizardStep.MUSIC_SELECTION, 12, "Subtitulos y musica", "Crear SRT y elegir biblioteca segura."),
    WizardStepDefinition(WizardStep.CLIP_IMPORT, 13, "Importar clips", "Importar clips generados fuera."),
    WizardStepDefinition(WizardStep.SCENE_MAPPING, 14, "Asociar clips", "Mapear clips a escenas."),
    WizardStepDefinition(WizardStep.VISUAL_STYLE, 15, "Estilo visual", "Preparar plan visual tecnico."),
    WizardStepDefinition(WizardStep.RENDER, 16, "Renderizar", "Generar video vertical."),
    WizardStepDefinition(WizardStep.REVIEW, 17, "Revisar", "Completar checklist humana."),
    WizardStepDefinition(WizardStep.EXPORT, 18, "Exportar", "Crear paquete final."),
)


def wizard_step_values() -> list[str]:
    return [definition.step.value for definition in WIZARD_STEPS]


def get_step_definition(step: WizardStep | str) -> WizardStepDefinition:
    normalized = step if isinstance(step, WizardStep) else WizardStep(step)
    for definition in WIZARD_STEPS:
        if definition.step == normalized:
            return definition
    raise ValueError(f"Unknown wizard step: {step}")


def wizard_progress(step: WizardStep | str) -> float:
    definition = get_step_definition(step)
    return definition.index / len(WIZARD_STEPS)


def next_step(step: WizardStep | str) -> WizardStep | None:
    definition = get_step_definition(step)
    if definition.index >= len(WIZARD_STEPS):
        return None
    return WIZARD_STEPS[definition.index].step


def previous_step(step: WizardStep | str) -> WizardStep | None:
    definition = get_step_definition(step)
    if definition.index <= 1:
        return None
    return WIZARD_STEPS[definition.index - 2].step
