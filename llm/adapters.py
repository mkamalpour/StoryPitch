# llm/adapters.py
from llm.manager import LLMManager
from config import DEFAULT_MODEL
import logging

llm = LLMManager()

logger = logging.getLogger(__name__)

async def generate(prompt: str, primary: str | None = None, fallback: str | None = None, max_tokens: int | None = None):
    primary = (primary or DEFAULT_MODEL).lower()
    fallback = fallback or ("hf" if primary == "local" else "local")
    
    logger.info("=" * 80)
    logger.info("🎯 LLM GENERATE REQUEST")
    logger.info("Primary Model: %s | Fallback Model: %s", primary, fallback)
    logger.info("Prompt Length: %d characters", len(prompt))
    if max_tokens:
        logger.info("Max Tokens Override: %d", max_tokens)
    logger.info("=" * 80)
    
    try:
        logger.info("🔄 Attempting PRIMARY model: %s", primary)
        result = await llm.generate(prompt, model=primary, max_tokens=max_tokens)
        logger.info("✅ PRIMARY model SUCCESS - Response: %d chars", len(result))
        return result
    except Exception as e:
        logger.error("❌ PRIMARY model FAILED: %s", str(e))
        logger.warning("🔄 Switching to FALLBACK model: %s", fallback)
        try:
            result = await llm.generate(prompt, model=fallback, max_tokens=max_tokens)
            logger.info("✅ FALLBACK model SUCCESS - Response: %d chars", len(result))
            return result
        except Exception as e2:
            logger.error("❌ FALLBACK model FAILED: %s", str(e2))
            logger.error("❌ ALL LLM attempts failed - This should trigger fallback generator")
            raise
