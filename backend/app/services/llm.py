"""
LLM provider abstraction.

LLM_PROVIDER=ollama      -> local Ollama server (http://localhost:11434)
LLM_PROVIDER=openrouter  -> OpenRouter-hosted models (needs OPENROUTER_API_KEY)
LLM_PROVIDER=offline     -> zero-network deterministic provider (default)

The offline provider is a REAL, separate code path — not a mock of what
an LLM "would" say. It uses extractive summarization, sentence scoring,
and template-based structured-output construction. It is intentionally
labeled everywhere it's used so nobody mistakes its output for an LLM's.
Swapping LLM_PROVIDER to "ollama" or "openrouter" changes nothing else
in the agent graph — every agent calls this module, never a provider
directly.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

import httpx

from app.config import get_settings


@dataclass
class LLMResponse:
    text: str
    provider: str
    model: str


class LLMProviderError(RuntimeError):
    pass


def _extract_json(text: str) -> dict:
    """Best-effort extraction of a JSON object from an LLM response."""
    text = text.strip()
    text = re.sub(r"^```json\s*|^```\s*|```$", "", text, flags=re.MULTILINE).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise


async def _call_ollama(system: str, user: str) -> str:
    settings = get_settings()
    async with httpx.AsyncClient(timeout=settings.request_timeout_seconds * 4) as client:
        resp = await client.post(
            f"{settings.ollama_base_url}/api/chat",
            json={
                "model": settings.llm_model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "stream": False,
                "keep_alive": "10m",
                "options": {"temperature": 0.1},
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return data["message"]["content"]


async def _call_openrouter(system: str, user: str) -> str:
    settings = get_settings()
    if not settings.openrouter_api_key:
        raise LLMProviderError("OPENROUTER_API_KEY is not set")
    async with httpx.AsyncClient(timeout=settings.request_timeout_seconds * 4) as client:
        resp = await client.post(
            f"{settings.openrouter_base_url}/chat/completions",
            headers={"Authorization": f"Bearer {settings.openrouter_api_key}"},
            json={
                "model": settings.llm_model,
                "temperature": 0.1,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]


def _offline_complete(system: str, user: str) -> str:
    """
    Deterministic, extractive, zero-network completion. Used for both
    plain-text and (when the caller asks for JSON) structured output,
    via simple template construction from the input rather than free
    generation. This keeps the *pipeline* genuinely executable without
    any paid/network service; it does not claim LLM-quality prose.
    """
    from app.services.offline_reasoner import offline_reasoner

    return offline_reasoner(system=system, user=user)


async def complete(system: str, user: str, *, expect_json: bool = False):
    """Route to the configured provider. Returns str, or dict if expect_json."""
    settings = get_settings()
    provider = settings.llm_provider

    if provider == "ollama":
        text = await _call_ollama(system, user)
    elif provider == "openrouter":
        text = await _call_openrouter(system, user)
    elif provider == "offline":
        text = _offline_complete(system, user)
    else:
        raise LLMProviderError(f"Unknown LLM_PROVIDER: {provider}")

    if expect_json:
        try:
            return _extract_json(text)
        except Exception as exc:
            # Keep demo mode deterministic. In live mode, never silently
            # replace malformed model output with unrelated offline output.
            if provider != "offline":
                raise LLMProviderError("The configured LLM returned invalid JSON; retry this research run.") from exc
            from app.services.offline_reasoner import offline_reasoner

            fallback_text = offline_reasoner(system=system, user=user)
            return _extract_json(fallback_text)
    return text
