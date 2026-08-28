"""
Factory de LLM — força Grok como provider principal, HuggingFace como fallback.

Respeita GROCK_API_TOKEN (sem expor valor) e mantém compatibilidade com
HUGGINGFACE_TOKEN quando Grok não está disponível.

Regras de prioridade (forçado):
  1. Se GROCK_API_TOKEN presente -> GrokProvider é primário (llm e go_llm)
  2. Se GROCK_API_TOKEN ausente/false -> HuggingFaceProvider (legado)
  3. Em improve/ask/diagnose: Grok tenta primeiro; se falhar, cai para HF ou template.

Nunca loga o valor do token; usa mascaramento para diagnóstico.
"""
from __future__ import annotations

import logging
import os

from .base import BaseLLMProvider
from .grok import GrokProvider, _mask_token
from .huggingface import HuggingFaceProvider

logger = logging.getLogger(__name__)


def _has_grok_token() -> bool:
    for key in ("GROCK_API_TOKEN", "GROK_API_TOKEN", "XAI_API_KEY", "XAI_TOKEN"):
        if os.getenv(key):
            return True
    return False


def create_llm_providers() -> tuple[BaseLLMProvider | None, BaseLLMProvider | None, str]:
    """
    Cria (llm, go_llm, provider_label) forçando Grok quando disponível.

    Returns:
        llm: provider principal para NextJS/Design/Frontend/Vercel/Backend/Diagnostic
        go_llm: provider específico para Go (pode usar modelo diferente)
        label: string descritiva para logs (sem expor token)
    """
    grok_token_present = _has_grok_token()

    if grok_token_present:
        # Grok é obrigatório quando token existe — força seu uso
        grok_model = os.getenv("GROK_MODEL") or os.getenv("GROCK_MODEL") or "grok-3"
        grok_go_model = os.getenv("GROK_MODEL_GO") or os.getenv("GROK_MODEL") or os.getenv("GROCK_MODEL") or "grok-3"
        grok_base = os.getenv("GROK_API_BASE_URL") or os.getenv("GROCK_API_BASE_URL") or "https://api.x.ai/v1"

        # Não expõe token, só mascarado para log
        token_preview = _mask_token(os.getenv("GROCK_API_TOKEN") or os.getenv("GROK_API_TOKEN") or os.getenv("XAI_API_KEY") or "")
        logger.info("LLM provider: Grok (xAI) model=%s base=%s token=%s [FORÇADO]", grok_model, grok_base, token_preview)

        llm = GrokProvider(model=grok_model, base_url=grok_base)
        go_llm = GrokProvider(model=grok_go_model, base_url=grok_base)

        # Valida que token foi resolvido; se não, fallback para HF com warning
        if not llm.is_configured:
            logger.warning("GROCK_API_TOKEN detectado mas não resolvido — fallback para HuggingFace")
        else:
            return llm, go_llm, f"grok:{grok_model}"

    # Fallback: HuggingFace (legado) — mantido para dev sem Grok token
    hf_token = os.getenv("HUGGINGFACE_TOKEN")
    hf_model = os.getenv("LLM_MODEL_1")
    hf_go_model = os.getenv("LLM_MODEL_GO")

    if hf_token:
        logger.info("LLM provider: HuggingFace model=%s (Grok não configurado — usando fallback)", hf_model or "default")
        llm = HuggingFaceProvider(token=hf_token, model=hf_model)
        go_llm = HuggingFaceProvider(token=hf_token, model=hf_go_model) if hf_go_model else llm
        return llm, go_llm, f"huggingface:{hf_model or 'default'}"

    logger.warning("Nenhum LLM token configurado (GROCK_API_TOKEN / HUGGINGFACE_TOKEN ausentes) — modo template-only")
    return None, None, "none:template-only"


def get_primary_llm(llm: BaseLLMProvider | None, go_llm: BaseLLMProvider | None) -> BaseLLMProvider | None:
    """Retorna o LLM primário (preferencialmente Grok)."""
    return llm or go_llm


def is_grok_provider(provider: BaseLLMProvider | None) -> bool:
    return isinstance(provider, GrokProvider)
