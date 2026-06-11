import os
from huggingface_hub import AsyncInferenceClient
from .base import BaseLLMProvider, LLMMessage, LLMResponse

RECOMMENDED_MODELS: dict[str, str] = {
    "code": "Qwen/Qwen2.5-Coder-7B-Instruct",
    "code-large": "Qwen/Qwen2.5-Coder-32B-Instruct",
    "general": "meta-llama/Llama-3.1-8B-Instruct",
    "general-large": "meta-llama/Llama-3.1-70B-Instruct",
    "fast": "microsoft/Phi-3.5-mini-instruct",
    "reasoning": "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B",
    "deepseek-coder": "deepseek-ai/DeepSeek-Coder-V2-Lite-Instruct",
    "codellama": "codellama/CodeLlama-13b-Instruct-hf",
    "mistral": "mistralai/Mistral-7B-Instruct-v0.3",
}


class HuggingFaceProvider(BaseLLMProvider):
    """LLM provider using Hugging Face open-source models via Inference API."""

    def __init__(
        self,
        token: str | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.1,
    ):
        self.token = token or os.getenv("HUGGINGFACE_TOKEN")
        self.model = model or os.getenv("LLM_MODEL", RECOMMENDED_MODELS["code"])
        self.default_max_tokens = max_tokens
        self.default_temperature = temperature
        self._client: AsyncInferenceClient | None = None

    @property
    def client(self) -> AsyncInferenceClient:
        if self._client is None:
            self._client = AsyncInferenceClient(token=self.token)
        return self._client

    async def complete(
        self,
        messages: list[LLMMessage],
        max_tokens: int | None = None,
        temperature: float | None = None,
        **kwargs,
    ) -> LLMResponse:
        hf_messages = [{"role": m.role, "content": m.content} for m in messages]

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=hf_messages,
            max_tokens=max_tokens or self.default_max_tokens,
            temperature=temperature if temperature is not None else self.default_temperature,
            **kwargs,
        )

        choice = response.choices[0]
        return LLMResponse(
            content=choice.message.content or "",
            model=self.model,
            tokens_used=response.usage.total_tokens if response.usage else None,
            finish_reason=choice.finish_reason,
        )

    async def generate_code(
        self,
        prompt: str,
        language: str = "typescript",
        context: str | None = None,
        max_tokens: int = 4096,
    ) -> str:
        system = (
            f"You are an expert {language} developer. "
            "Generate clean, production-ready code. "
            "Return ONLY the code without markdown fences or explanations."
        )
        if context:
            system += f"\n\nProject context:\n{context}"

        messages = [
            LLMMessage(role="system", content=system),
            LLMMessage(role="user", content=prompt),
        ]
        response = await self.complete(messages, max_tokens=max_tokens, temperature=0.05)
        content = response.content.strip()

        # Strip markdown fences if model added them anyway
        for fence in ["```tsx", "```typescript", "```ts", "```jsx", "```js", "```python", "```"]:
            if content.startswith(fence):
                content = content[len(fence):]
                break
        if content.endswith("```"):
            content = content[:-3]

        return content.strip()

    def with_model(self, model_key: str) -> "HuggingFaceProvider":
        model = RECOMMENDED_MODELS.get(model_key, model_key)
        return HuggingFaceProvider(
            token=self.token,
            model=model,
            max_tokens=self.default_max_tokens,
            temperature=self.default_temperature,
        )
