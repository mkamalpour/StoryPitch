# story/memory_analyzer.py
"""
Memory Analysis System
Handles deep memory extraction from story narrations
COMPATIBLE VERSION: Works with existing manager.py and adapters.py
"""

import json
import logging
import re
from typing import Dict, Any, Optional
from db.db import SessionModel, get_session
from story.prompts import build_memory_analysis_prompt
from story.memory import StoryMemory
from llm.adapters import generate

logger = logging.getLogger(__name__)


async def analyze_and_refresh_memory(session_id: int, model: str | None = None) -> Dict[str, Any]:
    """
    🧠 Analyze recent story narrations and extract/update ALL memory elements.
    
    COMPATIBLE with existing manager.py - uses max_tokens only.
    Relies on smart parsing to handle reasoning text and truncation.
    """
    logger.info("=" * 60)
    logger.info("🧠 MEMORY ANALYSIS STARTED for session %d", session_id)
    
    try:
        session = get_session(session_id)
        if not session:
            return {
                "success": False,
                "message": f"Session {session_id} not found",
                "memory": _empty_memory(),
                "summary": ""
            }
        
        state = session.get_world_state()
        
        # Build memory analysis prompt
        logger.info("Building memory analysis prompt...")
        prompt = build_memory_analysis_prompt(session)
        
        if not prompt:
            return {
                "success": False,
                "message": "No story content to analyze yet. Play a few turns first!",
                "memory": _empty_memory(),
                "summary": ""
            }
        
        logger.info("Prompt built - Length: %d chars", len(prompt))
        
        # ================================================================
        # Call LLM with HIGH max_tokens (3000) to prevent truncation
        # Note: Cannot pass temperature or stop sequences with current manager
        # ================================================================
        logger.info("Calling LLM for memory extraction with max_tokens=3000...")
        ai_text = await generate(prompt, primary=model, max_tokens=3000)
        
        if not ai_text or not ai_text.strip():
            raise ValueError("Empty response from LLM")
        
        logger.info("AI output received - Length: %d chars", len(ai_text))
        logger.debug("AI output preview: %s...", ai_text[:300])
        
        # ================================================================
        # SMART PARSING - Handles reasoning, truncation, malformed JSON
        # ================================================================
        memory_data = _super_smart_parse_memory_json(ai_text)
        
        if not memory_data:
            logger.warning("Failed to parse memory JSON, using empty memory")
            memory_data = _empty_memory()
        
        logger.info("Memory parsed: NPCs=%d, Locations=%d, Items=%d, Events=%d",
                    len(memory_data.get("npcs", [])),
                    len(memory_data.get("locations", [])),
                    len(memory_data.get("inventory", [])),
                    len(memory_data.get("events", [])))
        
        # Save to memory system
        logger.info("Saving memory to session...")
        memory = StoryMemory(state)
        current_step = session.current_step
        
        for npc in memory_data.get("npcs", []):
            if npc.get("name"):
                memory.add_npc(
                    name=npc["name"][:50],
                    description=npc.get("description", "")[:200],
                    personality=npc.get("personality", "")[:50],
                    step=current_step
                )
        
        for loc in memory_data.get("locations", []):
            if loc.get("name"):
                memory.add_location(
                    name=loc["name"][:50],
                    description=loc.get("description", "")[:200],
                    step=current_step
                )
        
        for item in memory_data.get("inventory", []):
            if item.get("item"):
                memory.add_item(
                    item=item["item"][:50],
                    description=item.get("description", "")[:200],
                    step=current_step
                )
        
        for rel in memory_data.get("relationships", []):
            if rel.get("npc"):
                memory.set_relationship(
                    npc_name=rel["npc"][:50],
                    affinity=max(-100, min(100, rel.get("affinity", 0))),
                    notes=rel.get("status", "")[:100]
                )
        
        for event in memory_data.get("events", []):
            if event:
                memory.add_event(event[:200], step=current_step)
        
        for discovery in memory_data.get("discoveries", []):
            if discovery:
                memory.add_discovery(discovery[:200], step=current_step)
        
        from db.db import update_session
        update_session(session_id, world_state=state)
        logger.info("Memory saved successfully")
        
        return {
            "success": True,
            "message": "Memory refreshed successfully!",
            "memory": memory_data,
            "summary": _create_memory_summary(memory_data)
        }
        
    except Exception as e:
        logger.error("Memory analysis failed: %s", e)
        logger.exception("Full error:")
        return {
            "success": False,
            "message": f"Memory analysis failed: {str(e)}",
            "memory": _empty_memory(),
            "summary": ""
        }


def _super_smart_parse_memory_json(ai_text: str) -> Optional[Dict[str, Any]]:
    """
    SUPER SMART PARSER - Works with reasoning text, truncation, malformed JSON.
    Designed to work without temperature/stop control.
    """
    if not ai_text:
        return None
    
    original = ai_text
    logger.debug("Parsing memory JSON from %d chars", len(original))
    
    # ================================================================
    # STRATEGY 1: Find JSON by looking for {"npcs" or {"locations"
    # ================================================================
    json_start_markers = [
        '{"npcs"', '{\n  "npcs"', '{\n\t"npcs"',
        '{"locations"', '{\n  "locations"', 
        '{"inventory"', '{"events"'
    ]
    
    for marker in json_start_markers:
        idx = original.find(marker)
        if idx != -1:
            candidate = original[idx:]
            # Find matching closing brace
            extracted = _extract_to_matching_brace(candidate)
            if extracted:
                try:
                    # Fix common JSON issues
                    fixed = _fix_json(extracted)
                    parsed = json.loads(fixed)
                    if _has_memory_fields(parsed):
                        logger.info("✅ Found JSON with marker: %s", marker)
                        return parsed
                except:
                    pass
    
    # ================================================================
    # STRATEGY 2: Find any JSON object and try to parse
    # ================================================================
    all_braces = [i for i, c in enumerate(original) if c == '{']
    
    for start in all_braces:
        candidate = _extract_to_matching_brace(original[start:])
        if candidate and len(candidate) > 50:
            try:
                fixed = _fix_json(candidate)
                parsed = json.loads(fixed)
                if _has_memory_fields(parsed):
                    logger.info("✅ Found JSON at position %d", start)
                    return parsed
            except:
                continue
    
    # ================================================================
    # STRATEGY 3: Look for JSON-like structure with regex
    # ================================================================
    patterns = [
        r'\{[^{}]*"npcs"[^{}]*\}',
        r'\{[^{}]*"locations"[^{}]*\}',
        r'\{[^{}]*"inventory"[^{}]*\}',
        r'\{[^{}]*"events"[^{}]*\}',
        r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}',  # Nested
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, original, re.DOTALL)
        for candidate in matches:
            if len(candidate) > 50:
                try:
                    fixed = _fix_json(candidate)
                    parsed = json.loads(fixed)
                    if _has_memory_fields(parsed):
                        logger.info("✅ Found JSON via regex")
                        return parsed
                except:
                    pass
    
    # ================================================================
    # STRATEGY 4: Try to complete truncated JSON
    # ================================================================
    # If we see a partial JSON, try to add missing braces
    if '{"npcs"' in original or '"npcs"' in original:
        # Find where JSON starts
        start = original.find('{')
        if start != -1:
            truncated = original[start:]
            # Count braces
            open_braces = truncated.count('{')
            close_braces = truncated.count('}')
            if open_braces > close_braces:
                truncated += '}' * (open_braces - close_braces)
            # Count brackets
            open_brackets = truncated.count('[')
            close_brackets = truncated.count(']')
            if open_brackets > close_brackets:
                truncated += ']' * (open_brackets - close_brackets)
            # Fix trailing commas
            truncated = re.sub(r',\s*}', '}', truncated)
            truncated = re.sub(r',\s*]', ']', truncated)
            try:
                parsed = json.loads(truncated)
                if _has_memory_fields(parsed):
                    logger.info("✅ Completed truncated JSON (+%d braces)", open_braces - close_braces)
                    return parsed
            except:
                pass
    
    # ================================================================
    # STRATEGY 5: Extract from reasoning text (infer)
    # ================================================================
    inferred = _infer_from_reasoning_text(original)
    if inferred:
        logger.info("✅ Inferred from reasoning text")
        return inferred
    
    logger.warning("❌ All parsing strategies failed")
    return None


def _extract_to_matching_brace(text: str) -> Optional[str]:
    """Extract from first { to matching }."""
    start = text.find('{')
    if start == -1:
        return None
    
    depth = 0
    in_string = False
    escape = False
    
    for i, ch in enumerate(text[start:], start):
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
                return text[start:i + 1]
    
    # Incomplete JSON - return what we have
    if depth > 0:
        return text[start:]
    return None


def _fix_json(json_str: str) -> str:
    """Fix common JSON issues."""
    if not json_str:
        return json_str
    
    # Remove trailing commas
    json_str = re.sub(r',\s*}', '}', json_str)
    json_str = re.sub(r',\s*]', ']', json_str)
    
    # Fix unclosed strings (crude)
    lines = json_str.split('\n')
    fixed_lines = []
    for line in lines:
        quote_count = line.count('"')
        if quote_count % 2 == 1:
            line += '"'
        fixed_lines.append(line)
    json_str = '\n'.join(fixed_lines)
    
    # Remove control characters
    json_str = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', json_str)
    
    return json_str


def _has_memory_fields(data: Dict) -> bool:
    """Check if dict has any memory-related fields."""
    if not isinstance(data, dict):
        return False
    expected = ["npcs", "locations", "inventory", "relationships", "events", "discoveries"]
    return any(k in data for k in expected)


def _infer_from_reasoning_text(text: str) -> Optional[Dict[str, Any]]:
    """Last resort: infer memory from reasoning text."""
    result = _empty_memory()
    
    # Look for character names (capitalized words)
    import re
    words = re.findall(r'\b([A-Z][a-z]{2,})\b', text)
    seen = set()
    for name in words:
        if name.lower() not in ["nexus", "the", "and", "for", "but", "was", "had", "that"]:
            if name not in seen:
                seen.add(name)
                result["npcs"].append({
                    "name": name,
                    "personality": "unknown",
                    "description": f"{name} appears in the story"
                })
                if len(result["npcs"]) >= 5:
                    break
    
    # Look for location phrases
    loc_pattern = r'(?:in the|at the|to the|from the)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)'
    loc_matches = re.findall(loc_pattern, text)
    for name in loc_matches[:5]:
        result["locations"].append({
            "name": name,
            "description": f"{name} is a location"
        })
    
    if result["npcs"] or result["locations"]:
        logger.info("Inferred: %d NPCs, %d locations", len(result["npcs"]), len(result["locations"]))
        return result
    
    return None


def _empty_memory() -> Dict[str, Any]:
    """Return empty memory structure."""
    return {
        "npcs": [],
        "locations": [],
        "inventory": [],
        "relationships": [],
        "events": [],
        "discoveries": []
    }


def _create_memory_summary(memory_data: Dict[str, Any]) -> str:
    """Create a human-readable summary."""
    parts = []
    
    npcs = memory_data.get("npcs", [])
    locations = memory_data.get("locations", [])
    inventory = memory_data.get("inventory", [])
    events = memory_data.get("events", [])
    discoveries = memory_data.get("discoveries", [])
    
    if npcs:
        names = [n.get("name", "?") for n in npcs[:5]]
        parts.append(f"👥 Characters: {', '.join(names)}")
    if locations:
        names = [l.get("name", "?") for l in locations[:5]]
        parts.append(f"🗺️ Locations: {', '.join(names)}")
    if inventory:
        names = [i.get("item", "?") for i in inventory[:5]]
        parts.append(f"🎒 Items: {', '.join(names)}")
    if events:
        parts.append(f"📅 Events: {len(events)} recorded")
    if discoveries:
        parts.append(f"💡 Discoveries: {len(discoveries)} revealed")
    
    if not parts:
        parts.append("No significant memory elements found yet.")
    
    return " | ".join(parts)