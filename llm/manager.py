# llm/manager.py
import asyncio, time, hashlib, logging
from typing import Optional
from config import LM_STUDIO_URL, LM_STUDIO_MODEL, LM_STUDIO_API_KEY, LM_STUDIO_USE_CHAT, HF_API_KEY, HF_MODEL, DEFAULT_MODEL, CACHE_TTL, HTTP_TIMEOUT, MAX_CONCURRENT_LLM, OFFLINE_MODE, LLM_MAX_TOKENS, LLM_TEMPERATURE, LLM_TOP_P
from constants import FALLBACK_AI_TEXT
import httpx

logger = logging.getLogger(__name__)

# in-memory TTL cache: key -> (text, ts)
_cache: dict[str, tuple[str, float]] = {}
_cache_lock = asyncio.Lock()
_semaphore = asyncio.Semaphore(MAX_CONCURRENT_LLM)

def _cache_key(prompt: str, model: str):
    return hashlib.sha256((model + "||" + prompt).encode()).hexdigest()

async def _get_cached(prompt: str, model: str):
    key = _cache_key(prompt, model)
    async with _cache_lock:
        it = _cache.get(key)
        if not it:
            return None
        text, ts = it
        if time.time() - ts > CACHE_TTL:
            del _cache[key]
            return None
        return text

async def _set_cache(prompt: str, model: str, text: str):
    key = _cache_key(prompt, model)
    async with _cache_lock:
        _cache[key] = (text, time.time())

def is_llm_busy() -> bool:
    """Check if LLM is currently processing a request"""
    return _semaphore._value == 0

class LLMManager:
    def __init__(self, default_model: Optional[str] = None):
        self.default_model = default_model or DEFAULT_MODEL

    async def generate(self, prompt: str, model: Optional[str] = None, max_tokens: int = None) -> str:
        model = (model or self.default_model).lower()
        if model not in ("local", "hf"):
            logger.warning("⚠️ Invalid model '%s' requested. Falling back to default model '%s'", model, self.default_model)
            model = self.default_model

        max_tokens = max_tokens or LLM_MAX_TOKENS  # Use config value (1200) if not specified
        logger.info("🤖 LLM Generate Request - Model: %s, Prompt Length: %d chars, Max Tokens: %d", model, len(prompt), max_tokens)

        cached = await _get_cached(prompt, model)
        if cached:
            logger.info("✅ LLM Cache Hit - Returning cached response (%d chars)", len(cached))
            return cached

        logger.info("⏳ LLM Cache Miss - Generating new response...")
        async with _semaphore:
            logger.info("🔒 Acquired LLM semaphore (max concurrent=%d)", MAX_CONCURRENT_LLM)

            # try local LM Studio endpoint
            if model == "local" and LM_STUDIO_URL:
                logger.info("🔌 Attempting Local LM Studio at: %s", LM_STUDIO_URL)
                try:
                    headers = {"Content-Type": "application/json"}
                    if LM_STUDIO_API_KEY:
                        headers["Authorization"] = f"Bearer {LM_STUDIO_API_KEY}"
                        logger.debug("Using API key for authentication")
                    timeout = HTTP_TIMEOUT if HTTP_TIMEOUT is not None else None
                    logger.info("⏱️  Timeout: %s seconds", timeout)
                    async with httpx.AsyncClient(timeout=timeout, headers=headers) as client:
                        base = LM_STUDIO_URL.rstrip('/')

                        endpoints = []
                        if LM_STUDIO_USE_CHAT:
                            endpoints.append("/v1/chat/completions")
                        endpoints.append("/v1/completions")

                        model_id = (LM_STUDIO_MODEL or "").strip()
                        if not model_id:
                            try:
                                models_url = f"{base}/v1/models"
                                logger.info("🔍 Auto-detecting LM Studio model from: %s", models_url)
                                mr = await client.get(models_url)
                                mr.raise_for_status()
                                data = mr.json()
                                logger.debug("Models response: %s", str(data)[:200])
                                items = data.get("data") if isinstance(data, dict) else data
                                if isinstance(items, list) and items:
                                    first = items[0] if isinstance(items[0], dict) else None
                                    if first:
                                        model_id = first.get("id") or first.get("model") or first.get("name") or "local-model"
                                        logger.info("✅ Auto-detected model: %s", model_id)
                                if not model_id:
                                    model_id = "local-model"
                                    logger.warning("⚠️  No model detected, using default: %s", model_id)
                            except Exception as e_models:
                                logger.warning("❌ Could not auto-detect LM Studio model: %s", e_models)
                                model_id = "local-model"
                        else:
                            logger.info("📝 Using configured model: %s", model_id)

                        last_error = None
                        for ep in endpoints:
                            url = f"{base}{ep}"
                            try:
                                if ep.endswith("chat/completions"):
                                    payload = {
                                        "model": model_id,
                                        "messages": [{"role": "user", "content": prompt}],
                                        "max_tokens": max_tokens,
                                        "temperature": LLM_TEMPERATURE,
                                        "stream": False
                                    }
                                    logger.info("📤 Sending Chat Completion request to: %s", url)
                                else:
                                    payload = {
                                        "model": model_id,
                                        "prompt": prompt,
                                        "max_tokens": max_tokens,
                                        "temperature": LLM_TEMPERATURE,
                                        "stream": False
                                    }
                                    logger.info("📤 Sending Completion request to: %s", url)

                                logger.info("🔧 Request params: model=%s, max_tokens=%d, temp=%.1f", model_id, max_tokens, LLM_TEMPERATURE)
                                logger.debug("Full payload: %s", str(payload)[:500])

                                r = await client.post(url, json=payload)
                                logger.info("📥 Response received: Status %d", r.status_code)
                                r.raise_for_status()
                                data = r.json()
                                logger.debug("Response data: %s", str(data)[:300])

                                text = None
                                if "choices" in data and data["choices"]:
                                    choice0 = data["choices"][0]
                                    if isinstance(choice0, dict):
                                        if "message" in choice0 and isinstance(choice0["message"], dict):
                                            text = choice0["message"].get("content")
                                        text = text or choice0.get("text")
                                text = text or data.get("text") or data.get("generated_text") or data.get("output")
                                if not text and isinstance(data, list) and data and isinstance(data[0], dict):
                                    text = data[0].get("generated_text")

                                if text and str(text).strip():
                                    text = str(text)
                                    await _set_cache(prompt, model, text)
                                    logger.info("✅ LM Studio SUCCESS - Generated %d chars", len(text))
                                    logger.info("📝 Response preview: %s...", text[:150])
                                    return text
                                else:
                                    logger.warning("⚠️  LM Studio %s returned empty/unknown response: %s", ep, str(data)[:200])
                            except Exception as e2:
                                last_error = e2
                                logger.error("❌ LM Studio call failed at %s: %s", ep, e2)
                        if last_error:
                            logger.error("❌ All LM Studio endpoints failed")
                            raise last_error
                except Exception as e:
                    logger.error("❌ LM Studio failed completely: %s", e)
                    # continue to other providers/fallback

            if model == "hf" and HF_API_KEY:
                logger.info("🤗 Attempting HuggingFace API with model: %s", HF_MODEL)
                for attempt in range(3):
                    try:
                        headers = {"Authorization": f"Bearer {HF_API_KEY}"}
                        url = f"https://api-inference.huggingface.co/models/{HF_MODEL}"
                        logger.info("📤 HF Request (attempt %d/3) to: %s", attempt + 1, url)
                        timeout = HTTP_TIMEOUT if HTTP_TIMEOUT is not None else None
                        logger.info("⏱️  Timeout: %s seconds", timeout)
                        async with httpx.AsyncClient(timeout=timeout) as client:
                            payload = {
                                "inputs": prompt,
                                "parameters": {
                                    "max_new_tokens": max_tokens,
                                    "temperature": LLM_TEMPERATURE,
                                    "top_p": LLM_TOP_P
                                }
                            }
                            logger.debug("HF Payload: %s", str(payload)[:300])

                            r = await client.post(url, headers=headers, json=payload)
                            logger.info("📥 HF Response: Status %d", r.status_code)
                            r.raise_for_status()
                            data = r.json()
                            logger.debug("HF Response data: %s", str(data)[:300])

                            text = ""
                            if isinstance(data, list) and data and "generated_text" in data[0]:
                                text = data[0]["generated_text"]
                            else:
                                text = str(data)

                            await _set_cache(prompt, model, text)
                            logger.info("✅ HuggingFace SUCCESS - Generated %d chars", len(text))
                            logger.info("📝 Response preview: %s...", text[:150])
                            return text
                    except Exception as e:
                        logger.error("❌ HF LLM failed (attempt %d/3): %s", attempt + 1, e)
                        if attempt == 2:
                            logger.error("❌ All HuggingFace attempts exhausted")

            logger.warning("⚠️  All LLM providers failed - Using intelligent fallback generator")
            text = self._fallback(prompt)
            await _set_cache(prompt, model, text)
            logger.info("✅ Fallback generator produced %d chars", len(text))
            return text

    def _fallback(self, prompt: str) -> str:
        """Generate intelligent fallback responses based on prompt context"""
        logger.info("🔄 Using intelligent fallback generator")
        logger.debug("Fallback prompt analysis: %s", prompt[:200])
        
        # Extract context from prompt
        prompt_lower = prompt.lower()
        
        if "start" in prompt_lower or "begin" in prompt_lower:
            narration = "Narration: Your adventure begins in a mysterious place full of possibilities. The air is thick with anticipation as you stand at the threshold of your journey."
            choices = "\nChoices:\n1) Explore the immediate area\n2) Look for signs or clues\n3) Take a moment to plan your approach"
            clues = "\nClues: Something interesting awaits discovery in this place."
        elif "explore" in prompt_lower or "investigate" in prompt_lower:
            narration = "Narration: You carefully examine your surroundings, noticing details that others might miss. Your investigation reveals new possibilities."
            choices = "\nChoices:\n1) Continue exploring deeper\n2) Examine a specific object\n3) Take a different approach"
            clues = "\nClues: Your careful observation has revealed something important."
        elif "fight" in prompt_lower or "battle" in prompt_lower:
            narration = "Narration: The tension rises as you prepare for what lies ahead. Your courage and determination will be tested."
            choices = "\nChoices:\n1) Face the challenge head-on\n2) Look for a strategic advantage\n3) Try to find an alternative solution"
            clues = "\nClues: Your bravery has opened new possibilities."
        else:
            # Use centralized fallback for default case
            return FALLBACK_AI_TEXT
        
        return narration + choices + clues
