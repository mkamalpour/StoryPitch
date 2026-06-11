# story/parser.py
"""
ULTIMATE LLM Response Parser
Handles: JSON, truncated JSON, reasoning blocks, Unicode issues, wrapped responses,
         missing braces, malformed arrays, OpenAI format, and everything else.
"""

import re
import json
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

# ============================================================================
# CONSTANTS
# ============================================================================

FALLBACK_NARRATION = "The story continues..."
FALLBACK_CHOICES = ["Continue forward", "Look around", "Talk to someone", "Wait and see"]


# ============================================================================
# TEXT CLEANING (First Layer)
# ============================================================================

def _fix_unicode_garbage(text: str) -> str:
    """Fix common Unicode corruption from LLM outputs."""
    if not text:
        return text
    
    replacements = {
        'â€”': '—',      # em dash
        'â€“': '–',      # en dash
        'â€œ': '"',      # left smart quote
        'â€\x9d': '"',   # right smart quote
        'â€™': "'",      # apostrophe
        'â€¦': '...',    # ellipsis
        'â€¢': '•',      # bullet
        'â€°': '%',      # percent
        'â€¹': '<',      # left angle quote
        'â€º': '>',      # right angle quote
    }
    
    for bad, good in replacements.items():
        text = text.replace(bad, good)
    
    return text


def _clean_code_fences(text: str) -> str:
    """Remove all markdown code fences."""
    if not text:
        return text
    
    # Remove ```json ... ```
    text = re.sub(r'```(?:json|[\w+-]*)\n?([\s\S]*?)\n?```', r'\1', text)
    # Remove standalone ```
    text = text.replace('```', '')
    # Remove inline `code` that might interfere
    text = re.sub(r'`([^`]+)`', r'\1', text)
    
    return text.strip()


def _clean_whitespace(text: str) -> str:
    """Normalize whitespace without destroying structure."""
    if not text:
        return text
    
    # Replace multiple newlines with double newline
    text = re.sub(r'\n{3,}', '\n\n', text)
    # Remove trailing spaces on each line
    text = '\n'.join(line.rstrip() for line in text.splitlines())
    # Remove empty first/last lines
    text = text.strip()
    
    return text


def _unescape_json_string(text: str) -> str:
    """Fully unescape a JSON string."""
    if not text:
        return text
    
    # Order matters: backslash first, then quotes
    text = text.replace('\\\\', '\\')
    text = text.replace('\\"', '"')
    text = text.replace('\\n', '\n')
    text = text.replace('\\t', '\t')
    text = text.replace('\\r', '\r')
    text = text.replace('\\/', '/')
    
    return text


def _fix_trailing_commas(text: str) -> str:
    """Remove trailing commas before closing braces/brackets."""
    if not text:
        return text
    
    text = re.sub(r',\s*}', '}', text)
    text = re.sub(r',\s*]', ']', text)
    text = re.sub(r',\s*,', ',', text)  # Double commas
    
    return text


def _balance_braces(text: str) -> str:
    """Add missing closing braces and brackets."""
    if not text:
        return text
    
    open_braces = text.count('{')
    close_braces = text.count('}')
    open_brackets = text.count('[')
    close_brackets = text.count(']')
    
    if open_braces > close_braces:
        text += '}' * (open_braces - close_braces)
    
    if open_brackets > close_brackets:
        # Find where to add closing brackets (after choices array)
        choices_pos = text.find('"choices"')
        if choices_pos != -1:
            # Try to find where choices array ends
            bracket_pos = text.find('[', choices_pos)
            if bracket_pos != -1:
                # Count brackets from there
                depth = 0
                for i, ch in enumerate(text[bracket_pos:], bracket_pos):
                    if ch == '[':
                        depth += 1
                    elif ch == ']':
                        depth -= 1
                        if depth == 0:
                            # Already closed, no need
                            break
                else:
                    # Never closed, add now
                    text = text + ']'
        else:
            text += ']' * (open_brackets - close_brackets)
    
    return text


# ============================================================================
# INTELLIGENT JSON EXTRACTION (Multiple Strategies)
# ============================================================================

def _extract_via_brace_balance(text: str, start_pos: int) -> Optional[str]:
    """
    Extract JSON by tracking brace balance from a start position.
    Returns complete JSON string when braces balance.
    """
    depth = 0
    in_string = False
    escape = False
    json_start = start_pos
    
    for idx in range(start_pos, len(text)):
        ch = text[idx]
        
        if escape:
            escape = False
            continue
        if ch == '\\':
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                return text[json_start:idx + 1]
    
    return None


def _extract_json_by_scanning(text: str) -> Optional[str]:
    """Scan through text finding first valid JSON by brace balance."""
    # Find all possible JSON start positions
    for match in re.finditer(r'{', text):
        candidate = _extract_via_brace_balance(text, match.start())
        if candidate:
            # Verify it looks like story JSON
            if '"narration"' in candidate or '"choices"' in candidate:
                # Try to parse it
                try:
                    json.loads(candidate)
                    return candidate
                except json.JSONDecodeError:
                    # Try to fix common issues
                    fixed = _fix_trailing_commas(candidate)
                    fixed = _balance_braces(fixed)
                    try:
                        json.loads(fixed)
                        return fixed
                    except:
                        continue
    return None


def _extract_json_by_pattern(text: str) -> Optional[str]:
    """Extract JSON using regex patterns."""
    patterns = [
        # Full JSON with both narration and choices
        r'\{[^{}]*"narration"[^{}]*"choices"[^{}]*\}',
        r'\{[^{}]*"choices"[^{}]*"narration"[^{}]*\}',
        # At least narration
        r'\{[^{}]*"narration"[^{}]*\}',
        # At least choices
        r'\{[^{}]*"choices"[^{}]*\}',
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, text, re.DOTALL)
        for candidate in matches:
            try:
                fixed = _fix_trailing_commas(candidate)
                json.loads(fixed)
                return fixed
            except:
                continue
    return None


def _extract_json_from_content_wrapper(text: str) -> Optional[str]:
    """Extract JSON from "content": "{...}" pattern."""
    # Pattern for content field with escaped JSON
    pattern = r'"content":\s*"(\{.*?)(?:"\s*[,}]|\}\s*$|\Z)'
    match = re.search(pattern, text, re.DOTALL)
    if match:
        content = match.group(1)
        content = _unescape_json_string(content)
        content = _fix_trailing_commas(content)
        content = _balance_braces(content)
        try:
            json.loads(content)
            return content
        except:
            pass
    
    # Pattern for content field with unescaped JSON
    pattern2 = r'"content":\s*(\{.*?\}),?\s*"reasoning"'
    match = re.search(pattern2, text, re.DOTALL)
    if match:
        content = match.group(1)
        content = _fix_trailing_commas(content)
        content = _balance_braces(content)
        try:
            json.loads(content)
            return content
        except:
            pass
    
    return None


def _extract_json_from_truncated_response(text: str) -> Optional[str]:
    """
    Special handler for truncated JSON where narration contains colons.
    This handles your specific problematic response.
    """
    # Find the content field
    match = re.search(r'"content":\s*"({.*)', text, re.DOTALL)
    if not match:
        return None
    
    content = match.group(1)
    
    # Unescape
    content = _unescape_json_string(content)
    
    # Now find the last complete JSON structure
    brace_count = 0
    in_string = False
    escape = False
    last_good_pos = 0
    
    for i, ch in enumerate(content):
        if escape:
            escape = False
            continue
        if ch == '\\':
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == '{':
            brace_count += 1
        elif ch == '}':
            brace_count -= 1
            if brace_count == 0:
                last_good_pos = i + 1
    
    if last_good_pos > 0:
        content = content[:last_good_pos]
    else:
        # Add missing braces
        if brace_count > 0:
            content += '}' * brace_count
    
    # Fix choices array if truncated
    if '"choices"' in content:
        # Check if choices array is closed
        choices_section = content[content.find('"choices"'):]
        open_brackets = choices_section.count('[')
        close_brackets = choices_section.count(']')
        if open_brackets > close_brackets:
            # Add missing closing bracket and brace
            content += ']}'
    
    content = _fix_trailing_commas(content)
    
    try:
        json.loads(content)
        return content
    except:
        return None


def _extract_json_from_reasoning(text: str) -> Optional[str]:
    """Extract JSON from after reasoning markers."""
    markers = [
        r'OUTPUT:\s*(\{.*\})',
        r'JSON:\s*(\{.*\})',
        r'```json\s*(\{.*\})\s*```',
        r'Let me output:\s*(\{.*\})',
        r'Here is the JSON:\s*(\{.*\})',
        r'Final JSON:\s*(\{.*\})',
    ]
    
    for pattern in markers:
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        if match:
            candidate = match.group(1)
            candidate = _fix_trailing_commas(candidate)
            candidate = _balance_braces(candidate)
            try:
                json.loads(candidate)
                return candidate
            except:
                continue
    return None


def _extract_json_from_text_fallback(text: str) -> Optional[str]:
    """Absolute last resort: find anything that looks like JSON."""
    # Find all brace-enclosed blocks
    all_candidates = []
    
    # Progressive extraction: try larger and larger blocks
    for start in re.finditer(r'{', text):
        for end in range(start.start() + 1, min(start.start() + 5000, len(text))):
            if text[end] == '}':
                candidate = text[start.start():end + 1]
                if len(candidate) > 30 and ('"narration"' in candidate or '"choices"' in candidate):
                    all_candidates.append(candidate)
    
    # Sort by length (longest first, likely the most complete)
    all_candidates.sort(key=len, reverse=True)
    
    for candidate in all_candidates[:5]:
        try:
            fixed = _fix_trailing_commas(candidate)
            fixed = _balance_braces(fixed)
            json.loads(fixed)
            return fixed
        except:
            continue
    
    return None


# ============================================================================
# REASONING STRIPPING (Find the JSON)
# ============================================================================

def _find_json_in_text(text: str) -> str:
    """
    Find and extract the JSON from any LLM response.
    Uses multiple strategies in order of intelligence.
    """
    if not text:
        return text
    
    original = text
    
    # Strategy 1: Handle truncated response (your specific case)
    extracted = _extract_json_from_truncated_response(text)
    if extracted:
        logger.debug("✅ Extracted via truncated response handler")
        return extracted
    
    # Strategy 2: Extract from content wrapper
    extracted = _extract_json_from_content_wrapper(text)
    if extracted:
        logger.debug("✅ Extracted via content wrapper")
        return extracted
    
    # Strategy 3: Extract from reasoning markers
    extracted = _extract_json_from_reasoning(text)
    if extracted:
        logger.debug("✅ Extracted via reasoning markers")
        return extracted
    
    # Strategy 4: Scan by brace balance
    extracted = _extract_json_by_scanning(text)
    if extracted:
        logger.debug("✅ Extracted via brace scanning")
        return extracted
    
    # Strategy 5: Pattern matching
    extracted = _extract_json_by_pattern(text)
    if extracted:
        logger.debug("✅ Extracted via pattern matching")
        return extracted
    
    # Strategy 6: Text fallback
    extracted = _extract_json_from_text_fallback(text)
    if extracted:
        logger.debug("✅ Extracted via text fallback")
        return extracted
    
    # Nothing worked, return original
    logger.warning("⚠️ No JSON extracted, using original text")
    return original


def _strip_reasoning_text(text: str) -> str:
    """Remove all reasoning/thinking text and return only the JSON."""
    if not text:
        return text
    
    # First, fix Unicode garbage
    text = _fix_unicode_garbage(text)
    
    # Clean code fences
    text = _clean_code_fences(text)
    
    # Find and extract JSON
    json_text = _find_json_in_text(text)
    
    return json_text


# ============================================================================
# VALUE NORMALIZATION
# ============================================================================

def _normalize_choice_value(value: Any) -> str:
    """Convert any choice format to clean string."""
    if isinstance(value, str):
        cleaned = value.strip()
        # Remove bullet points and numbering
        cleaned = re.sub(r'^[\d]+[\.\)]\s*', '', cleaned)
        cleaned = re.sub(r'^[-*•]\s*', '', cleaned)
        cleaned = re.sub(r'^[a-z]\)\s*', '', cleaned)
        return cleaned
    if isinstance(value, dict):
        return value.get("text") or value.get("choice") or value.get("label") or ""
    return str(value).strip()


def _validate_memory(memory: Any) -> Dict[str, List]:
    """Ensure memory has correct structure."""
    if not isinstance(memory, dict):
        memory = {}
    
    return {
        "npcs": memory.get("npcs", []) if isinstance(memory.get("npcs"), list) else [],
        "locations": memory.get("locations", []) if isinstance(memory.get("locations"), list) else [],
        "items": memory.get("items", []) if isinstance(memory.get("items"), list) else [],
        "events": memory.get("events", []) if isinstance(memory.get("events"), list) else [],
        "discoveries": memory.get("discoveries", []) if isinstance(memory.get("discoveries"), list) else []
    }


# ============================================================================
# MAIN PARSING FUNCTION
# ============================================================================

def parse_ai_output(ai_text: str) -> Dict[str, Any]:
    """
    Parse ANY AI output into structured format.
    Returns dict with narration, choices, clues, memory.
    """
    
    # Handle empty input
    if not ai_text or not ai_text.strip():
        logger.warning("Empty AI output received")
        return {
            "narration": FALLBACK_NARRATION,
            "choices": FALLBACK_CHOICES[:4],
            "clues": "",
            "memory": {"npcs": [], "locations": [], "items": [], "events": [], "discoveries": []}
        }
    
    original = ai_text
    ai_text = ai_text.strip()
    
    logger.debug(f"Original input length: {len(ai_text)} chars")
    logger.debug(f"First 300 chars: {ai_text[:300]}...")
    
    # Step 1: Strip reasoning and extract JSON
    ai_text = _strip_reasoning_text(ai_text)
    logger.debug(f"After reasoning strip: {ai_text[:200]}...")
    
    # Step 2: Clean whitespace
    ai_text = _clean_whitespace(ai_text)
    
    # Step 3: Fix common JSON issues
    ai_text = _fix_trailing_commas(ai_text)
    ai_text = _balance_braces(ai_text)
    
    # Step 4: Try to parse JSON
    obj = None
    parse_error = None
    
    try:
        obj = json.loads(ai_text)
        logger.debug("✅ Direct JSON parse successful")
    except json.JSONDecodeError as e:
        parse_error = str(e)
        logger.debug(f"Direct parse failed: {e}")
    
    # Step 5: Try to extract from within cleaned text
    if obj is None:
        extracted = _extract_json_by_scanning(ai_text)
        if extracted:
            try:
                obj = json.loads(extracted)
                logger.debug("✅ Extracted via scanning")
            except json.JSONDecodeError as e:
                logger.debug(f"Scanning extraction failed: {e}")
    
    # Step 6: Try pattern matching
    if obj is None:
        extracted = _extract_json_by_pattern(ai_text)
        if extracted:
            try:
                obj = json.loads(extracted)
                logger.debug("✅ Extracted via pattern matching")
            except json.JSONDecodeError as e:
                logger.debug(f"Pattern extraction failed: {e}")
    
    # Step 7: Handle OpenAI wrapper format
    if obj and isinstance(obj.get("choices"), list) and obj["choices"]:
        first_choice = obj["choices"][0]
        if isinstance(first_choice, dict):
            content = None
            if "message" in first_choice and isinstance(first_choice["message"], dict):
                content = first_choice["message"].get("content")
            if not content:
                content = first_choice.get("text")
            if content and isinstance(content, str) and content.strip().startswith('{'):
                logger.debug("Unwrapping OpenAI response")
                return parse_ai_output(content)
    
    # Step 8: Extract fields from parsed object
    if obj and isinstance(obj, dict):
        narration = str(obj.get("narration", "")).strip()
        choices = obj.get("choices", []) or obj.get("options", [])
        clues = str(obj.get("clues", "")).strip()
        memory = obj.get("memory", {})
        
        # Normalize choices
        if isinstance(choices, list):
            choices = [_normalize_choice_value(c) for c in choices if _normalize_choice_value(c)]
        elif isinstance(choices, str):
            choices = [c.strip() for c in re.split(r'[;,]\s*', choices) if c.strip()]
        else:
            choices = []
        
        # Validate we have minimum content
        if narration and len(choices) >= 2:
            return {
                "narration": narration[:3000],
                "choices": choices[:6],
                "clues": clues[:1000],
                "memory": _validate_memory(memory)
            }
        else:
            logger.warning(f"Invalid content: narration={bool(narration)}, choices_count={len(choices)}")
    
    # Step 9: Absolute last resort - text parsing
    logger.warning("All JSON parsing failed, using text-based fallback")
    
    result = {
        "narration": "",
        "choices": [],
        "clues": "",
        "memory": {"npcs": [], "locations": [], "items": [], "events": [], "discoveries": []}
    }
    
    # Extract narration (first meaningful block)
    paragraphs = [p.strip() for p in original.split('\n\n') if len(p.strip()) > 30]
    if paragraphs:
        result["narration"] = paragraphs[0][:1500]
    else:
        sentences = re.split(r'(?<=[.!?])\s+', original)
        if len(sentences) >= 2:
            result["narration"] = ' '.join(sentences[:5])[:1500]
        else:
            result["narration"] = FALLBACK_NARRATION
    
    # Extract choices
    choice_patterns = [
        r'(?m)^\s*(\d+)[\.\)]\s*(.+?)$',
        r'(?m)^\s*[-*•]\s*(.+?)$',
        r'"choices":\s*\[(.*?)\]',
    ]
    
    for pattern in choice_patterns:
        matches = re.findall(pattern, original, re.DOTALL | re.MULTILINE)
        if matches:
            choices = []
            for m in matches[:8]:
                if isinstance(m, tuple):
                    choice_text = m[1].strip() if len(m) > 1 else m[0].strip()
                else:
                    choice_text = m.strip() if isinstance(m, str) else str(m)
                if choice_text and len(choice_text) > 3:
                    choices.append(choice_text)
            if len(choices) >= 2:
                result["choices"] = choices[:6]
                break
    
    if not result["choices"]:
        result["choices"] = FALLBACK_CHOICES[:4]
    
    # Clean choices
    result["choices"] = [re.sub(r'^[\d\.\)\-\*•\s]+', '', c).strip() for c in result["choices"]]
    result["choices"] = [c for c in result["choices"] if c and len(c) > 3][:6]
    
    if not result["choices"]:
        result["choices"] = FALLBACK_CHOICES[:4]
    
    logger.debug(f"Text fallback: narration={len(result['narration'])} chars, choices={len(result['choices'])}")
    
    return result