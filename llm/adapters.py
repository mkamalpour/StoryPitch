"""Single provider selection; cloud requests are always explicit."""

from llm.manager import LLMManager

llm = LLMManager()


async def generate(prompt: str, primary=None, fallback=None, max_tokens=None):
    return await llm.generate(prompt, model=primary, max_tokens=max_tokens)
