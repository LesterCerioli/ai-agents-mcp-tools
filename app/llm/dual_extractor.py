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
    
    try:
        from app.llm.huggingface import HuggingFaceProvider
        llm = HuggingFaceProvider(token=token, model=model, max_tokens=512, temperature=0.1)
        response = await llm.chat(prompt, system_prompt=system_prompt)
        return _extract_json(response)
    except Exception as exc:
        logger.debug("dual_extractor: model %s failed — %s", model, exc)
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
    Call model_1 and model_2 in parallel with the same param-extraction prompt.
    Return whichever response covers more required parameters.
    Falls back to None if both fail.
    """
    if not required_params:
        return {}

    prompt = _build_extraction_prompt(skill_name, task, required_params)

    result1, result2 = await asyncio.gather(
        _call_model(token, model_1, prompt, system_prompt),
        _call_model(token, model_2, prompt, system_prompt),
    )

    score1 = _score(result1, required_params)
    score2 = _score(result2, required_params)

    logger.debug(
        "dual_extractor: model1=%s score=%d | model2=%s score=%d",
        model_1, score1, model_2, score2,
    )

    return result1 if score1 >= score2 else result2
