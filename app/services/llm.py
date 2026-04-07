"""
Провайдеры LLM: Ollama (бесплатно локально), OpenAI-совместимый API (Groq и др.).
"""

from abc import ABC, abstractmethod

import httpx

from app.config import settings


class LLMProvider(ABC):
    @abstractmethod
    async def complete(self, system: str, user: str) -> str:
        pass


class OllamaProvider(LLMProvider):
    async def complete(self, system: str, user: str) -> str:
        url = f"{settings.ollama_base_url.rstrip('/')}/api/chat"
        payload = {
            "model": settings.ollama_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
        }
        async with httpx.AsyncClient(timeout=120.0) as client:
            r = await client.post(url, json=payload)
            r.raise_for_status()
            data = r.json()
        msg = data.get("message") or {}
        return (msg.get("content") or "").strip()


class OpenAICompatibleProvider(LLMProvider):
    async def complete(self, system: str, user: str) -> str:
        if not settings.openai_compat_base_url or not settings.openai_compat_model:
            raise ValueError("OPENAI_COMPAT_BASE_URL и OPENAI_COMPAT_MODEL обязательны")
        url = f"{settings.openai_compat_base_url.rstrip('/')}/chat/completions"
        headers = {"Content-Type": "application/json"}
        if settings.openai_compat_api_key:
            headers["Authorization"] = f"Bearer {settings.openai_compat_api_key}"
        payload = {
            "model": settings.openai_compat_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        async with httpx.AsyncClient(timeout=120.0) as client:
            r = await client.post(url, json=payload, headers=headers)
            r.raise_for_status()
            data = r.json()
        choices = data.get("choices") or []
        if not choices:
            return ""
        return (choices[0].get("message") or {}).get("content", "").strip()


def get_llm() -> LLMProvider:
    p = settings.llm_provider.lower()
    if p == "ollama":
        return OllamaProvider()
    if p in ("openai_compatible", "groq", "openrouter"):
        return OpenAICompatibleProvider()
    raise ValueError(f"Неизвестный LLM_PROVIDER: {settings.llm_provider}")
