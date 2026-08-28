import asyncio
import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


def _build_extraction_prompt(skill_name: str, task: str, required_params: list[dict]) -> str:
    param_lines = "\n".join(f"- {p['name']}: {p['description']}" for p in required_params)
    return (
        f"Task: {task}\n\n"
        f"Extract the following parameters for skill '{skill_name}':\n"
        f"{param_lines}\n\n"
        'Return only a JSON object like: {"param_name": "value"}'
    )


def _extract_json(text: str) -> dict[str, Any] | None:
    
    if not text:
        return None

    cleaned = text.strip()

    
    try:
        result = json.loads(cleaned)
        if isinstance(result, dict):
            return result
    except json.JSONDecodeError:
        pass

    
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL)
    if match:
        try:
            result = json.loads(match.group(1))
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            pass

    
    match = re.search(r"\{[^{}]*\}", cleaned, re.DOTALL)
    if match:
        try:
            result = json.loads(match.group(0))
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            pass

    return None


def _score(params: dict[str, Any] | None, required_params: list[dict]) -> int:
    
    if not params:
        return -1

    required_names = {p["name"] for p in required_params}
    score = sum(1 for name in required_names if params.get(name) and str(params[name]).strip())
    
    score += sum(1 for v in params.values() if v and str(v).strip())
    return score


async def _call_model(token: str, model: str, prompt: str, system_prompt: str) -> dict[str, Any] | None:
    """Tenta HF; caller decide qual token/model."""
    try:
        from app.llm.huggingface import HuggingFaceProvider
        llm = HuggingFaceProvider(token=token, model=model, max_tokens=512, temperature=0.1)
        response = await llm.chat(prompt, system_prompt=system_prompt)
        return _extract_json(response)
    except Exception as exc:
        logger.debug("dual_extractor: HF model %s failed — %s", model, exc)
        return None


async def _call_grok(prompt: str, system_prompt: str) -> dict[str, Any] | None:
    """Tenta extração via Grok (forçado quando GROCK_API_TOKEN presente)."""
    try:
        from app.llm.grok import GrokProvider
        import os
        # Só tenta se Grok estiver configurado
        token = os.getenv("GROCK_API_TOKEN") or os.getenv("GROK_API_TOKEN") or os.getenv("XAI_API_KEY")
        if not token:
            return None
        model = os.getenv("GROK_MODEL") or os.getenv("GROCK_MODEL") or "grok-3"
        llm = GrokProvider(token=token, model=model, max_tokens=512, temperature=0.1)
        response = await llm.chat(prompt, system_prompt=system_prompt)
        return _extract_json(response)
    except Exception as exc:
        logger.debug("dual_extractor: Grok model failed — %s", exc)
        return None


async def extract_params_dual(
    skill_name: str,
    task: str,
    required_params: list[dict],
    system_prompt: str,
    token: str,
    model_1: str,
    model_2: str,
) -> dict[str, Any] | None:
    """
    Extração forçada Grok-first.

    1. Tenta Grok (se GROCK_API_TOKEN presente) — forçado como primário.
    2. Tenta model_1 e model_2 em paralelo (HF).
    3. Retorna o melhor escore dentre todos.
    Falls back to None if todos falharem.
    """
    if not required_params:
        return {}

    prompt = _build_extraction_prompt(skill_name, task, required_params)

    # Grok tem prioridade — chama junto
    grok_task = _call_grok(prompt, system_prompt)
    hf_task1 = _call_model(token, model_1, prompt, system_prompt)
    hf_task2 = _call_model(token, model_2, prompt, system_prompt)

    grok_result, result1, result2 = await asyncio.gather(grok_task, hf_task1, hf_task2)

    # Se Grok retornou algo válido, prefira Grok se escore >= HF
    best = None
    best_score = -1
    candidates = [
        (grok_result, "grok"),
        (result1, model_1),
        (result2, model_2),
    ]
    for res, label in candidates:
        score = _score(res, required_params)
        logger.debug("dual_extractor: %s score=%d res=%s", label, score, res)
        if score > best_score:
            best_score = score
            best = res

    # Se Grok empatar com HF, prefira Grok (forçado)
    grok_score = _score(grok_result, required_params)
    if grok_result and grok_score == best_score and grok_score >= 0:
        return grok_result

    return best


async def extract_params_grok(
    skill_name: str,
    task: str,
    required_params: list[dict],
    system_prompt: str,
) -> dict[str, Any] | None:
    """Extração direta só com Grok (usada quando HuggingFace não está disponível)."""
    if not required_params:
        return {}
    prompt = _build_extraction_prompt(skill_name, task, required_params)
    result = await _call_grok(prompt, system_prompt)
    return result
