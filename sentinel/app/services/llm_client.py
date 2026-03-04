"""LLM client abstraction — ALL LLM calls go through this module.

Handles local/cloud routing, model selection from config,
JSON parsing with markdown-fence stripping, and timeouts.
Never call Ollama directly from pipeline nodes.
"""
import json
import re
from enum import Enum

import httpx

from app.config import settings


class InferenceTarget(Enum):
    LOCAL = "local"
    CLOUD = "cloud"


# Task → inference target routing table (TC-1: no hardcoded model names)
TASK_ROUTING: dict[str, InferenceTarget] = {
    "preprocess":          InferenceTarget.LOCAL,
    "classify":            InferenceTarget.LOCAL,
    "classify_escalation": InferenceTarget.CLOUD,
    "segment":             InferenceTarget.CLOUD,
    "report":              InferenceTarget.CLOUD,
    "synthesize":          InferenceTarget.CLOUD,
    "title":               InferenceTarget.CLOUD,
    "educate":             InferenceTarget.CLOUD,
    "chat":                InferenceTarget.LOCAL,
    "embed":               InferenceTarget.LOCAL,   # ALWAYS local
}

# Per-task timeouts in seconds
TASK_TIMEOUTS: dict[str, float] = {
    "classify":            30.0,
    "classify_escalation": 30.0,
    "preprocess":          60.0,
    "segment":             120.0,
    "report":              120.0,
    "synthesize":          120.0,
    "title":               60.0,
    "educate":             120.0,
    "chat":                30.0,
    "embed":               10.0,
}
_DEFAULT_TIMEOUT = 60.0

# Regex to strip ```json ... ``` or ``` ... ``` fences from LLM output
_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


def parse_llm_json(text: str) -> dict:
    """Parse JSON from LLM output, stripping markdown code fences if present.

    Ollama often wraps JSON in ```json ... ``` blocks. This strips the fences
    before parsing.

    Raises:
        ValueError: if the text cannot be parsed as JSON after stripping.
    """
    stripped = text.strip()

    # Try to extract content from code fences first
    match = _FENCE_RE.search(stripped)
    if match:
        stripped = match.group(1).strip()

    try:
        return json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"LLM output is not valid JSON after fence stripping: {exc}\n"
            f"Raw output: {text!r}"
        ) from exc


class LLMClient:
    """Unified LLM client routing calls to local Ollama or Ollama Cloud.

    Usage:
        client = LLMClient()
        response = await client.complete("classify", prompt)
        parsed = parse_llm_json(response)
    """

    async def complete(self, task: str, prompt: str, **kwargs) -> str:
        """Generate a completion for the given task and prompt.

        Routes to local or cloud Ollama based on the task type.
        Model name comes from settings — never hardcoded here.

        Args:
            task: Task name (e.g. "classify", "report"). Controls routing + model.
            prompt: The full prompt string.
            **kwargs: Extra Ollama params (temperature, num_predict, etc.)

        Returns:
            Raw LLM response string (may contain JSON, markdown, etc.)
        """
        target = TASK_ROUTING.get(task, InferenceTarget.CLOUD)
        model = settings.get_model_for_task(task)
        timeout = TASK_TIMEOUTS.get(task, _DEFAULT_TIMEOUT)

        if target == InferenceTarget.LOCAL:
            return await self._call_local(model, prompt, timeout, **kwargs)
        return await self._call_cloud(model, prompt, timeout, **kwargs)

    async def _call_local(self, model: str, prompt: str, timeout: float, **kwargs) -> str:
        """POST to local Ollama generate endpoint."""
        payload = {"model": model, "prompt": prompt, "stream": False, **kwargs}
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{settings.OLLAMA_LOCAL_URL}/api/generate",
                json=payload,
            )
            response.raise_for_status()
            return response.json()["response"]

    async def _call_cloud(self, model: str, prompt: str, timeout: float, **kwargs) -> str:
        """POST to Ollama Cloud generate endpoint."""
        payload = {"model": model, "prompt": prompt, "stream": False, **kwargs}
        headers = {"Authorization": f"Bearer {settings.OLLAMA_CLOUD_API_KEY}"}
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{settings.OLLAMA_CLOUD_URL}/api/generate",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            return response.json()["response"]
