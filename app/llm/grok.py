"""
Grok (xAI) LLM Provider — forçado como LLM principal do sistema.

Lê GROCK_API_TOKEN do ambiente (sem nunca expor o valor em logs, respostas ou
erros). Implementa BaseLLMProvider via API OpenAI-compatível da xAI:

  POST https://api.x.ai/v1/chat/completions
  Header: Authorization: Bearer <GROCK_API_TOKEN>
  Body: { model, messages, max_tokens, temperature, stream:false }

Suporta:
  - complete() para chat/prompt genérico
  - generate_code() para geração de código produção-ready
  - plus helpers de avaliação de projetos existentes

O token é resolvido APENAS via variável de ambiente GROCK_API_TOKEN (aceita
aliases GROK_API_TOKEN / XAI_API_KEY por compatibilidade, mas o nome canónico
é GROCK_API_TOKEN). O valor nunca é logado nem retornado.
"""
from __future__ import annotations

import logging
import os
from typing import Any

import httpx

from .base import BaseLLMProvider, LLMMessage, LLMResponse

logger = logging.getLogger(__name__)

# Modelos Grok válidos (xAI). Valores são referenciais; podem ser sobrescritos
# via env GROK_MODEL / GROK_MODEL_GO / GROK_MODEL_CODE.
GROK_RECOMMENDED_MODELS: dict[str, str] = {
    "default": "grok-3",
    "fast": "grok-3-fast",
    "mini": "grok-3-mini",
    "code": "grok-code-fast-1",
    "code-large": "grok-4",
    "reasoning": "grok-3",
}

# Mensagem de erro quando token ausente — nunca inclui o valor.
_MISSING_TOKEN_MSG = (
    "GROCK_API_TOKEN não configurado. Defina a variável de ambiente "
    "GROCK_API_TOKEN com seu token xAI (https://console.x.ai/)."
)

def _resolve_grok_token(explicit: str | None = None) -> str | None:
    """Resolve o token sem expor seu valor."""
    if explicit:
        return explicit
    for key in ("GROCK_API_TOKEN", "GROK_API_TOKEN", "XAI_API_KEY", "XAI_TOKEN"):
        val = os.getenv(key)
        if val:
            return val
    return None

def _mask_token(token: str) -> str:
    """Retorna versão mascarada para logs (últimos 4 chars visíveis)."""
    if not token or len(token) <= 8:
        return "***"
    return f"{token[:3]}***{token[-4:]}"

class GrokProvider(BaseLLMProvider):
    """
    Provider Grok (xAI) — OpenAI-compatível.

    Forçado como LLM principal. Todos os agents/orchestrator devem preferir
    esta implementação; HuggingFace fica como fallback se Grok indisponível.
    """

    def __init__(
        self,
        token: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.1,
        timeout: float = 90.0,
    ):
        resolved = _resolve_grok_token(token)
        # Nunca armazena token em atributo público logável; usa _token interno.
        self._token: str | None = resolved
        self.model: str = (
            model
            or os.getenv("GROK_MODEL")
            or os.getenv("GROCK_MODEL")
            or GROK_RECOMMENDED_MODELS["default"]
        )
        self.base_url: str = (
            (base_url or os.getenv("GROK_API_BASE_URL") or os.getenv("GROCK_API_BASE_URL") or "https://api.x.ai/v1")
            .rstrip("/")
        )
        self.default_max_tokens = max_tokens
        self.default_temperature = temperature
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    @property
    def is_configured(self) -> bool:
        return bool(self._token)

    @property
    def is_available(self) -> bool:
        return self.is_configured

    def _require_token(self) -> str:
        if not self._token:
            raise RuntimeError(_MISSING_TOKEN_MSG)
        return self._token

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def complete(
        self,
        messages: list[LLMMessage],
        max_tokens: int | None = None,
        temperature: float | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        token = self._require_token()
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        body: dict[str, Any] = {
            "model": kwargs.pop("model", self.model),
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "max_tokens": max_tokens or self.default_max_tokens,
            "temperature": temperature if temperature is not None else self.default_temperature,
            "stream": False,
        }
        # xAI suporta parâmetros extras como top_p, etc.
        for k in ("top_p", "seed", "stop"):
            if k in kwargs:
                body[k] = kwargs.pop(k)

        client = self._get_client()
        try:
            resp = await client.post(url, json=body, headers=headers)
        except httpx.TimeoutException as exc:
            logger.warning("Grok API timeout model=%s err=%s", self.model, exc)
            raise RuntimeError(f"Grok API timeout após {self.timeout}s") from exc
        except httpx.RequestError as exc:
            logger.warning("Grok API request error model=%s err=%s", self.model, exc)
            raise RuntimeError(f"Grok API request failed: {exc}") from exc

        if resp.status_code == 401:
            logger.error("Grok API 401 — token inválido ou expirado")
            raise RuntimeError("Grok API 401: token inválido. Verifique GROCK_API_TOKEN.")
        if resp.status_code == 429:
            logger.warning("Grok API 429 rate-limited")
            raise RuntimeError("Grok API rate limit atingido (429). Tente novamente em instantes.")
        if resp.status_code >= 400:
            # Nunca incluir token na mensagem de erro
            body_text = resp.text[:500]
            logger.warning("Grok API erro %s body=%s", resp.status_code, body_text)
            raise RuntimeError(f"Grok API erro {resp.status_code}: {body_text}")

        data = resp.json()
        try:
            choice = data["choices"][0]
            content = choice["message"]["content"] or ""
            finish = choice.get("finish_reason")
            usage = data.get("usage", {})
            tokens_used = usage.get("total_tokens")
        except (KeyError, IndexError, TypeError) as exc:
            logger.warning("Grok API resposta inesperada: %s", data)
            raise RuntimeError(f"Grok API resposta malformada: {exc}") from exc

        return LLMResponse(
            content=content,
            model=data.get("model", self.model),
            tokens_used=tokens_used,
            finish_reason=finish,
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
            "Return ONLY the code without markdown fences or explanations. "
            "You work together with an existing skill system: respect file conventions, "
            "use TypeScript strictly (except API route.js), handle errors, and "
            "write accessible, well-typed code."
        )
        if context:
            system += f"\n\nProject context / skill expert prompt:\n{context}"

        messages = [
            LLMMessage(role="system", content=system),
            LLMMessage(role="user", content=prompt),
        ]
        response = await self.complete(messages, max_tokens=max_tokens, temperature=0.05)
        content = response.content.strip()

        # Strip markdown fences se modelo adicionar mesmo após instrução
        for fence in ["```tsx", "```typescript", "```ts", "```jsx", "```js", "```python", "```go", "```"]:
            if content.startswith(fence):
                content = content[len(fence):]
                break
        if content.endswith("```"):
            content = content[:-3]
        return content.strip()

    async def analyze_project(
        self,
        instruction: str,
        project_files: list[dict[str, Any]],
        project_type: str = "unknown",
        max_tokens: int = 4096,
    ) -> str:
        """
        Análise especializada de projeto existente usando Grok.

        Envia resumo dos arquivos + instrução e pede ao Grok um plano estruturado:
        - avaliação do estado atual (estrutura, problemas detectados)
        - requisitos extraídos da instrução
        - mapeamento de skills sugeridas para implementar melhorias/correções
        Retorna JSON string (ou texto) com o raciocínio; quem chama faz parse com fallback.
        """
        file_summaries: list[str] = []
        total_chars = 0
        limit = 120_000  # evita ultrapassar context window
        for f in project_files[:60]:
            path = f.get("path", "")
            content = f.get("content") or ""
            if f.get("truncated"):
                content = "[truncated]"
            entry = f"- {path} ({len(content)} chars)\n{content[:2500]}"
            if total_chars + len(entry) > limit:
                break
            file_summaries.append(entry)
            total_chars += len(entry)

        files_block = "\n\n".join(file_summaries) if file_summaries else "(nenhum arquivo enviado)"
        user_prompt = (
            f"Você é um arquiteto sênior que avalia projetos existentes e propõe melhorias "
            f"usando um sistema de skills (go, nextjs, design, frontend, vercel, backend, diagnostic, solid).\n\n"
            f"Tipo de projeto detectado: {project_type}\n"
            f"Instrução do usuário (requisitos): {instruction}\n\n"
            f"Arquivos do projeto (parcial):\n{files_block}\n\n"
            f"TAREFA:\n"
            f"1. Avalie a estrutura atual, identifique padrões, frameworks e possíveis débitos técnicos.\n"
            f"2. Interprete os requisitos da instrução e mapeie para skills concretas.\n"
            f"3. Sugira um plano de execução ordenado com: agent, skill, params (JSON), reason.\n"
            f"4. Se houver correções, indique arquivos a criar/modificar e porquê.\n"
            f"Retorne APENAS JSON válido com chaves: analysis, detected_stack, requirements, suggested_skills, corrections, next_steps.\n"
            f"Exemplo de suggested_skills: [{{\"agent\":\"go\",\"skill\":\"go.gorm_entity\",\"params\":{{\"resource\":\"product\",\"module_name\":\"github.com/org/app\"}},\"reason\":\"criar entidade Product\"}}]\n"
        )
        messages = [
            LLMMessage(
                role="system",
                content=(
                    "You are a senior software architect. Analyze existing codebases and "
                    "map user requirements to concrete skills. Always return valid JSON only, "
                    "no markdown, no explanation. Be precise about agent/skill names and params."
                ),
            ),
            LLMMessage(role="user", content=user_prompt),
        ]
        resp = await self.complete(messages, max_tokens=max_tokens, temperature=0.15)
        return resp.content.strip()

    def with_model(self, model_key: str) -> "GrokProvider":
        """
        Retorna nova instância com modelo diferente (mantém mesmo token/base_url).
        Aceita keys de GROK_RECOMMENDED_MODELS ou nome direto de modelo xAI.
        """
        model = GROK_RECOMMENDED_MODELS.get(model_key, model_key)
        return GrokProvider(
            token=self._token,
            model=model,
            base_url=self.base_url,
            max_tokens=self.default_max_tokens,
            temperature=self.default_temperature,
            timeout=self.timeout,
        )

    def __repr__(self) -> str:
        # Nunca expor token
        masked = _mask_token(self._token) if self._token else "NOT_SET"
        return f"<GrokProvider model={self.model} base_url={self.base_url} token={masked}>"
