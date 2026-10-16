"""Bounded, offline-aware model requests with a built-in story fallback."""

import asyncio
import hashlib
import logging
import time
import httpx
from config import (
    LM_STUDIO_URL,
    LM_STUDIO_MODEL,
    LM_STUDIO_API_KEY,
    LM_STUDIO_USE_CHAT,
    HF_API_KEY,
    HF_MODEL,
    DEFAULT_MODEL,
    CACHE_TTL,
    HTTP_TIMEOUT,
    MAX_CONCURRENT_LLM,
    OFFLINE_MODE,
    LLM_MAX_TOKENS,
    LLM_TEMPERATURE,
    LLM_TOP_P,
)
from constants import FALLBACK_AI_TEXT

logger = logging.getLogger(__name__)
_cache: dict[str, tuple[str, float]] = {}
_semaphore = asyncio.Semaphore(max(1, MAX_CONCURRENT_LLM))


def is_llm_busy():
    return _semaphore.locked()


class LLMManager:
    def __init__(self, default_model=None):
        self.default_model = default_model or DEFAULT_MODEL

    async def generate(self, prompt, model=None, max_tokens=None):
        provider = (model or self.default_model).lower()
        if provider not in {"local", "hf", "fallback"}:
            raise ValueError("Choose local, hf, or fallback")
        max_tokens = max_tokens or LLM_MAX_TOKENS
        key = hashlib.sha256(f"{provider}|{max_tokens}|{prompt}".encode()).hexdigest()
        now = time.monotonic()
        cached = _cache.get(key)
        if cached and now - cached[1] < CACHE_TTL:
            return cached[0]
        generated = False
        async with _semaphore:
            try:
                if provider == "local" and LM_STUDIO_URL:
                    result = await self._local(prompt, max_tokens)
                    generated = True
                elif provider == "hf" and not OFFLINE_MODE and HF_API_KEY:
                    result = await self._hosted(prompt, max_tokens)
                    generated = True
                else:
                    result = self._fallback(prompt)
            except (
                httpx.HTTPError,
                ValueError,
                KeyError,
                TypeError,
                IndexError,
            ) as exc:
                logger.warning(
                    "%s model unavailable (%s); using built-in demo",
                    provider,
                    type(exc).__name__,
                )
                result = self._fallback(prompt)
        # Expire entries and cap memory. Cache successful provider responses only.
        for old_key, (_, timestamp) in list(_cache.items()):
            if now - timestamp >= CACHE_TTL:
                _cache.pop(old_key, None)
        if len(_cache) >= 128:
            _cache.pop(next(iter(_cache)))
        # A temporary provider failure must not hide its recovery for the cache TTL.
        if generated or provider == "fallback":
            _cache[key] = (result, now)
        return result

    @staticmethod
    def _text(data):
        if not isinstance(data, dict):
            raise ValueError("Invalid model response")
        choices = data.get("choices") or []
        first = choices[0] if choices else {}
        result = (first.get("message") or {}).get("content") or first.get("text")
        result = result or data.get("generated_text") or data.get("text")
        if not isinstance(result, str) or not result.strip():
            raise ValueError("Model returned empty text")
        return result.strip()

    async def _local(self, prompt, max_tokens):
        base = LM_STUDIO_URL.rstrip("/")
        if base.endswith("/v1"):
            base = base[:-3]
        headers = (
            {"Authorization": f"Bearer {LM_STUDIO_API_KEY}"}
            if LM_STUDIO_API_KEY
            else {}
        )
        timeout = httpx.Timeout(HTTP_TIMEOUT, connect=min(5, HTTP_TIMEOUT))
        async with httpx.AsyncClient(timeout=timeout, headers=headers) as client:
            model_id = LM_STUDIO_MODEL.strip()
            if not model_id:
                response = await client.get(f"{base}/v1/models")
                response.raise_for_status()
                models = response.json().get("data", [])
                model_id = next(
                    (
                        row["id"]
                        for row in models
                        if row.get("id") and "embed" not in row["id"].lower()
                    ),
                    "",
                )
                if not model_id:
                    raise ValueError("Load a text-generation model in LM Studio")
            endpoints = (
                ["chat/completions", "completions"]
                if LM_STUDIO_USE_CHAT
                else ["completions"]
            )
            for index, endpoint in enumerate(endpoints):
                payload = {
                    "model": model_id,
                    "max_tokens": max_tokens,
                    "temperature": LLM_TEMPERATURE,
                    "top_p": LLM_TOP_P,
                    "stream": False,
                }
                if endpoint == "chat/completions":
                    payload["messages"] = [{"role": "user", "content": prompt}]
                else:
                    payload["prompt"] = prompt
                response = await client.post(f"{base}/v1/{endpoint}", json=payload)
                # Compatibility fallback only for unsupported endpoints, never a second long timeout.
                if response.status_code in {404, 405} and index + 1 < len(endpoints):
                    continue
                response.raise_for_status()
                return self._text(response.json())
        raise ValueError("No compatible completion endpoint")

    async def _hosted(self, prompt, max_tokens):
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(HTTP_TIMEOUT, connect=min(5, HTTP_TIMEOUT))
        ) as client:
            response = await client.post(
                "https://router.huggingface.co/v1/chat/completions",
                headers={"Authorization": f"Bearer {HF_API_KEY}"},
                json={
                    "model": HF_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": max_tokens,
                    "temperature": LLM_TEMPERATURE,
                    "top_p": LLM_TOP_P,
                },
            )
            response.raise_for_status()
            return self._text(response.json())

    def _fallback(self, prompt: str) -> str:
        """Generate intelligent fallback responses based on prompt context"""
        logger.info("🔄 Using intelligent fallback generator")

        # Extract context from prompt
        prompt_lower = prompt.lower()
        if prompt.startswith("Please provide a brief summary") and "Scene:" in prompt:
            scene = prompt.split("Scene:", 1)[1].rsplit("Summary:", 1)[0].strip()
            import re

            sentences = re.split(r"(?<=[.!?])\s+", scene)
            return " ".join(sentences[:2])[:700]

        if "start" in prompt_lower or "begin" in prompt_lower:
            narration = "Narration: Your adventure begins in a mysterious place full of possibilities. The air is thick with anticipation as you stand at the threshold of your journey."
            choices = "\nChoices:\n1) Explore the immediate area\n2) Look for signs or clues\n3) Take a moment to plan your approach"
            clues = "\nClues: Something interesting awaits discovery in this place."
        elif "explore" in prompt_lower or "investigate" in prompt_lower:
            narration = "Narration: You carefully examine your surroundings, noticing details that others might miss. Your investigation reveals new possibilities."
            choices = "\nChoices:\n1) Continue exploring deeper\n2) Examine a specific object\n3) Take a different approach"
            clues = (
                "\nClues: Your careful observation has revealed something important."
            )
        elif "fight" in prompt_lower or "battle" in prompt_lower:
            narration = "Narration: The tension rises as you prepare for what lies ahead. Your courage and determination will be tested."
            choices = "\nChoices:\n1) Face the challenge head-on\n2) Look for a strategic advantage\n3) Try to find an alternative solution"
            clues = "\nClues: Your bravery has opened new possibilities."
        else:
            # Use centralized fallback for default case
            return FALLBACK_AI_TEXT

        return narration + choices + clues
