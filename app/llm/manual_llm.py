from __future__ import annotations

from app.llm.base import LLMProviderStatus


class ManualLLMProvider:
    name = "manual"

    def is_available(self) -> bool:
        return True

    def status(self) -> LLMProviderStatus:
        return LLMProviderStatus(
            name=self.name,
            available=True,
            detail="Modo manual gratuito: prepara prompts para copiar/pegar.",
            paid=False,
        )

    def generate_text(self, system_prompt: str, user_prompt: str) -> str:
        return self.build_prompt(system_prompt, user_prompt)

    def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        schema_name: str | None = None,
    ) -> dict[str, object]:
        return {
            "provider": self.name,
            "schema_name": schema_name,
            "prompt": self.build_prompt(system_prompt, user_prompt),
        }

    def build_prompt(self, system_prompt: str, user_prompt: str) -> str:
        return "\n\n".join(
            [
                "# Sistema",
                system_prompt.strip(),
                "# Usuario",
                user_prompt.strip(),
            ]
        )
