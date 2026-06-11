from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class LLMMessage:
    role: str  # "system" | "user" | "assistant"
    content: str


@dataclass
class LLMResponse:
    content: str
    model: str
    tokens_used: int | None = None
    finish_reason: str | None = None


class BaseLLMProvider(ABC):
    """Abstract interface for LLM providers."""

    @abstractmethod
    async def complete(
        self,
        messages: list[LLMMessage],
        max_tokens: int = 4096,
        temperature: float = 0.1,
        **kwargs: Any,
    ) -> LLMResponse: ...

    @abstractmethod
    async def generate_code(
        self,
        prompt: str,
        language: str = "typescript",
        context: str | None = None,
        max_tokens: int = 4096,
    ) -> str: ...

    async def chat(self, user_message: str, system_prompt: str | None = None) -> str:
        messages: list[LLMMessage] = []
        if system_prompt:
            messages.append(LLMMessage(role="system", content=system_prompt))
        messages.append(LLMMessage(role="user", content=user_message))
        response = await self.complete(messages)
        return response.content
