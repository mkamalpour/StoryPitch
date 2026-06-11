# story/postprocess.py
"""
Ultimate post-processing for story output: clean, normalize, validate.
"""

from __future__ import annotations

import re
import logging
from typing import Dict, List, Any

logger = logging.getLogger(__name__)

# ============================================================================
# CONSTANTS
# ============================================================================

FALLBACK_NARRATION = "The story continues..."
FALLBACK_CHOICES = ["Continue forward", "Look around", "Talk to someone", "Wait and see"]


# ============================================================================
# CLEANING FUNCTIONS
# ============================================================================

def _fix_unicode_garbage(text: str) -> str:
    """Fix common Unicode corruption."""
    if not text:
        return text
    
    replacements = {
        'â€”': '—', 'â€“': '–', 'â€œ': '"', 'â€\x9d': '"',
        'â€™': "'", 'â€¦': '...', 'â€¢': '•',
    }
    for bad, good in replacements.items():
        text = text.replace(bad, good)
    return text


def _clean_code_fences(text: str) -> str:
    """Remove markdown code fences."""
    if not text:
        return text
    text = re.sub(r'```(?:json|[\w+-]*)\n?([\s\S]*?)\n?```', r'\1', text)
    text = text.replace('```', '')
    return text.strip()


def _clean_whitespace(text: str) -> str:
    """Normalize whitespace."""
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = '\n'.join(line.rstrip() for line in text.splitlines())
    return text.strip()


def _strip_reasoning(text: str) -> str:
    """Remove reasoning before JSON."""
    if not text:
        return text
    
    # Fix Unicode first
    text = _fix_unicode_garbage(text)
    
    # Extract from content wrapper
    content_match = re.search(r'"content":\s*"({.*})"', text, re.DOTALL)
    if content_match:
        extracted = content_match.group(1)
        extracted = extracted.replace('\\"', '"').replace('\\n', '\n')
        if extracted.startswith('{'):
            return extracted
    
    # Find JSON by markers
    markers = ['{"narration"', '{\n"narration"', '```json\n{']
    for marker in markers:
        pos = text.find(marker)
        if pos != -1:
            return text[pos:]
    
    return text


def _clean_choices(choices: List[str], max_choices: int, max_len: int = 150) -> List[str]:
    """Deduplicate, trim, and clean choices."""
    seen = set()
    cleaned = []
    
    for ch in choices:
        ch_clean = (ch or "").strip()
        ch_clean = re.sub(r'^[\-\*\d\)\.]\s*', '', ch_clean)
        ch_clean = re.sub(r'^[0-9️⃣🔟]+\s*', '', ch_clean)
        
        if not ch_clean or len(ch_clean) < 3:
            continue
        
        if len(ch_clean) > max_len:
            ch_clean = ch_clean[:max_len - 1] + "…"
        
        if ch_clean.lower() in seen:
            continue
        
        seen.add(ch_clean.lower())
        cleaned.append(ch_clean)
        
        if len(cleaned) >= max_choices:
            break
    
    if not cleaned:
        cleaned = FALLBACK_CHOICES[:max_choices]
    
    return cleaned


def _truncate_narration(narration: str, max_chars: int = 1200) -> str:
    """Truncate narration gracefully at sentence boundary."""
    if len(narration) <= max_chars:
        return narration
    
    # Try to truncate at last sentence boundary
    truncated = narration[:max_chars]
    last_period = truncated.rfind('.')
    last_exclaim = truncated.rfind('!')
    last_question = truncated.rfind('?')
    last_boundary = max(last_period, last_exclaim, last_question)
    
    if last_boundary > max_chars - 100:
        truncated = truncated[:last_boundary + 1]
    else:
        truncated = truncated[:max_chars - 1] + "…"
    
    return truncated


# ============================================================================
# INTERNAL SIMPLE PARSER (Fallback)
# ============================================================================

def _simple_parse(text: str) -> Dict[str, Any]:
    """Simple fallback parser when main parser is unavailable."""
    result = {
        "narration": FALLBACK_NARRATION,
        "choices": [],
        "clues": "",
        "memory": {"npcs": [], "locations": [], "items": [], "events": [], "discoveries": []}
    }
    
    # Try JSON extraction
    json_match = re.search(r'\{[^{}]*"narration"[^{}]*\}', text, re.DOTALL)
    if json_match:
        try:
            import json
            parsed = json.loads(json_match.group())
            result["narration"] = parsed.get("narration", result["narration"])
            result["choices"] = parsed.get("choices", [])
            result["clues"] = parsed.get("clues", "")
            if result["choices"]:
                return result
        except:
            pass
    
    # Extract narration from paragraphs
    paragraphs = [p.strip() for p in text.split('\n\n') if len(p.strip()) > 30]
    if paragraphs:
        result["narration"] = paragraphs[0][:1000]
    else:
        sentences = re.split(r'(?<=[.!?])\s+', text)
        if len(sentences) >= 2:
            result["narration"] = ' '.join(sentences[:5])[:1000]
    
    # Extract choices
    choice_pattern = r'(?m)^\s*(\d+)[\.\)]\s*(.+?)$'
    matches = re.findall(choice_pattern, text)
    if matches:
        result["choices"] = [c[1].strip() for c in matches[:6]]
    else:
        result["choices"] = FALLBACK_CHOICES[:4]
    
    # Clean choices
    result["choices"] = [re.sub(r'^[\d\.\)\-\*•\s]+', '', c).strip() for c in result["choices"]]
    result["choices"] = [c for c in result["choices"] if c and len(c) > 3][:4]
    
    if not result["choices"]:
        result["choices"] = FALLBACK_CHOICES[:4]
    
    return result


# ============================================================================
# MAIN NORMALIZATION FUNCTION
# ============================================================================

def normalize_ai_text_to_story(
    ai_text: str, 
    max_choices: int = 4, 
    max_narration_chars: int = 1200
) -> Dict[str, Any]:
    """
    Normalize raw AI text into canonical story structure.
    
    Args:
        ai_text: Raw output from LLM
        max_choices: Maximum number of choices to return
        max_narration_chars: Maximum narration length
    
    Returns:
        Dict with narration, choices, clues, memory
    """
    
    # Handle empty input
    if not ai_text or not ai_text.strip():
        logger.warning("normalize_ai_text_to_story: empty input")
        return {
            "narration": FALLBACK_NARRATION,
            "choices": FALLBACK_CHOICES[:max_choices],
            "clues": "",
            "memory": {"npcs": [], "locations": [], "items": [], "events": [], "discoveries": []}
        }
    
    # Pre-clean
    text = _clean_code_fences(ai_text)
    text = _strip_reasoning(text)
    text = _clean_whitespace(text)
    text = _fix_unicode_garbage(text)
    
    # Try to use the main parser
    parsed = None
    try:
        from story.parser import parse_ai_output
        parsed = parse_ai_output(text)
        if parsed and parsed.get("narration") and len(parsed.get("choices", [])) >= 2:
            logger.debug("✅ Successfully parsed with main parser")
        else:
            logger.debug("Main parser returned insufficient content, using fallback")
            parsed = None
    except ImportError:
        logger.debug("story.parser not available, using internal parser")
        parsed = _simple_parse(text)
    except Exception as e:
        logger.warning(f"Parser error: {e}, using fallback")
        parsed = _simple_parse(text)
    
    # Ensure we have valid parsed data
    if not parsed or not isinstance(parsed, dict):
        parsed = _simple_parse(text)
    
    # Extract fields
    narration = parsed.get("narration", FALLBACK_NARRATION).strip()
    clues = parsed.get("clues", "").strip()
    choices = parsed.get("choices", [])
    memory = parsed.get("memory", {})
    
    # Apply constraints
    narration = _truncate_narration(narration, max_narration_chars)
    choices = _clean_choices(choices, max_choices)
    
    # Validate memory structure
    if not isinstance(memory, dict):
        memory = {}
    memory = {
        "npcs": memory.get("npcs", []) if isinstance(memory.get("npcs"), list) else [],
        "locations": memory.get("locations", []) if isinstance(memory.get("locations"), list) else [],
        "items": memory.get("items", []) if isinstance(memory.get("items"), list) else [],
        "events": memory.get("events", []) if isinstance(memory.get("events"), list) else [],
        "discoveries": memory.get("discoveries", []) if isinstance(memory.get("discoveries"), list) else []
    }
    
    # Build result
    result = {
        "narration": narration,
        "choices": choices,
        "clues": clues,
        "memory": memory
    }
    
    # Log summary for debugging
    memory_count = sum(len(v) for v in memory.values())
    logger.debug(
        f"Normalized: narration={len(narration)} chars, "
        f"choices={len(choices)}, clues={len(clues)} chars, "
        f"memory_items={memory_count}"
    )
    
    return result