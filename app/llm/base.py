from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class LLMProviderError(RuntimeError):
    """Base error for optional LLM providers."""


class LLMProviderUnavailable(LLMProviderError):
    """Raised when a provider is selected but not configured or reachable."""


@dataclass(frozen=True)
class LLMProviderStatus:
    name: str
    available: bool
    detail: str
    paid: bool = False


class LLMProvider(Protocol):
    name: str

    def is_available(self) -> bool:
        ...

    def status(self) -> LLMProviderStatus:
        ...

    def generate_text(self, system_prompt: str, user_prompt: str) -> str:
        ...

    def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        schema_name: str | None = None,
    ) -> dict[str, object] | list[object]:
        ...
