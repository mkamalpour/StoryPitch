# story/prompts.py
"""
🚀 OPTIMIZED Story Prompt Generation System

Two-mode system for maximum performance with quality:
1. build_fast_prompt() - FAST MODE: Minimal context for quick story generation (DEFAULT)
2. build_memory_analysis_prompt() - MEMORY MODE: Deep analysis for memory extraction

Use build_fast_prompt() for all story turns - it's 3-5x faster!
"""

import json
import logging
import random
from db.db import SessionModel
from config import (
    STORY_CHOICES_COUNT,
    STORY_NARRATION_MIN_SENTENCES,
    STORY_NARRATION_MAX_SENTENCES,
    STORY_COMPLEXITY
)
from constants import (
    PROMPT_RECENT_NARRATIONS,
    PROMPT_ACTIVE_NPCS,
    PROMPT_KEY_ITEMS,
    PROMPT_RECENT_DISCOVERIES,
    PROMPT_IMPORTANT_EVENTS,
    PROMPT_RECENT_CONSEQUENCES,
    PROMPT_ACTIVE_RELATIONSHIPS,
    PROMPT_INVENTORY_ITEMS,
    MEMORY_ANALYSIS_NARRATION_COUNT,
    TRAIT_GUIDELINES
)

logger = logging.getLogger(__name__)


# ============================================================================
# FAST MODE - USE THIS FOR STORY GENERATION (DEFAULT)
# ============================================================================

def build_fast_prompt(session: SessionModel, user_input: str | None = None, max_choices: int = None) -> str:
    """
    ⚡ SMART MODE: Build optimized prompt that guarantees complete JSON output.
    
    Key improvements over original:
    - Reduced context size (uses less tokens → more room for output)
    - Added complete JSON example (shows LLM exactly what to produce)
    - Stronger termination instructions (prevents truncation)
    - NO reasoning encouragement (pure output only)
    """
    if max_choices is None:
        max_choices = STORY_CHOICES_COUNT
    
    state = session.get_world_state()
    theme = state.get("theme", "An adventure begins")
    traits = state.get("traits", [])
    character_name = state.get("character_name", "the character")
    
    # Get minimal context 
    recent_narrations = _get_recent_narrations(state, PROMPT_RECENT_NARRATIONS)  # Only last 2
    current_location = _get_current_location(state)
    active_npcs = _get_active_npcs(state, PROMPT_ACTIVE_NPCS)  # Only 2 NPCs
    
    # Get story arc
    story_arc = state.get("story_arc", "beginning")
    step_count = state.get("step_count", 0)
    
    # =========================================================================
    # BUILD ULTRA-LEAN PROMPT
    # =========================================================================
    
    parts = []
    
    # 1. STRICT OUTPUT RULE (FIRST LINE - GETS ATTENTION)
    parts.append("OUTPUT ONLY VALID JSON. NOTHING ELSE. NO REASONING. NO EXTRA TEXT.")
    parts.append("")
    
    # 2. COMPLETE EXAMPLE (SHOWS EXACTLY WHAT TO OUTPUT)
    parts.append("EXAMPLE:")
    parts.append('{"narration": "The door creaks open. A shadow moves in the corner. You step inside cautiously.", "choices": ["Enter cautiously", "Call out into darkness", "Turn back and leave", "Wait and listen"], "clues": "Something moved behind the shelf"}')
    parts.append("")
    
    # 3. CONTEXT (KEPT MINIMAL)
    parts.append("CONTEXT:")
    parts.append(f"  Theme: {theme}")
    parts.append(f"  Character: {character_name}")
    if traits:
        random_traits = random.sample(traits, min(3, len(traits)))
        parts.append(f"  Traits: {', '.join(random_traits)}")
    else:
        parts.append("  Traits: None")
    if current_location:
        parts.append(f"  Location: {current_location}")
    if active_npcs:
        parts.append(f"  NPCs present: {', '.join(active_npcs)}")
    parts.append(f"  Story phase: {story_arc.upper()} (Step {step_count})")
    
    # CONTINUATION INSTRUCTION 
    if recent_narrations:
        last_narr = recent_narrations[-1]
        parts.append(f"  PREVIOUS SCENE (CONTEXT ONLY, DO NOT COPY): {last_narr[-100:]}")
    
    if user_input:
        parts.append(f"")
        parts.append(f"  WHAT THE PLAYER DOES NEXT: {user_input}")
        parts.append(f"  YOUR SCENE MUST BE THE DIRECT RESULT OF THIS ACTION.")
        parts.append(f"  WRITE WHAT HAPPENS AFTER THE PLAYER DOES THIS.")
    else:
        parts.append(f"  Write the opening scene.")
    
    parts.append("")
    
    # 4. INVESTIGATION DETECTION (only if needed)
    if user_input and any(word in user_input.lower() for word in ["look", "search", "examine", "investigate", "inspect", "check", "find", "clue", "explore"]):
        parts.append("➡️ INVESTIGATION: Include a specific discovery in 'clues' field.")
    parts.append("")
    
    # 5. OUTPUT SPECIFICATION
    parts.append(f"OUTPUT FORMAT:")
    parts.append(f"  - Narration: {STORY_NARRATION_MIN_SENTENCES}-{STORY_NARRATION_MAX_SENTENCES} sentences")
    parts.append(f"  - Choices: Exactly {max_choices} distinct options")
    parts.append(f"  - Clues: One sentence hint (or empty string)")
    parts.append("")
    
    # 6. FINAL STRICT INSTRUCTION
    parts.append("CRITICAL RULES:")
    parts.append("  1. Output ONLY the JSON object")
    parts.append("  2. Start with '{' and end with '}'")
    parts.append("  3. Do NOT add text before or after")
    parts.append("  4. Do NOT add markdown code fences")
    parts.append("  5. Do NOT explain your thinking")
    parts.append("  6. Do NOT truncate - complete the JSON")
    parts.append("")
    
    # 7. OPENING BRACE (trick to encourage completion)
    parts.append('{"narration": "')
    
    return "\n".join(parts)


# ============================================================================
# MEMORY MODE - USE THIS FOR "REFRESH MEMORY" FEATURE
# ============================================================================

def build_memory_analysis_prompt(session: SessionModel, narration_count: int = None) -> str:
    """
    🧠 MEMORY MODE: Build OPTIMIZED prompt for fast memory extraction.
    
    This is called separately when user clicks "Refresh Memory" button.
    Analyzes recent narrations and extracts memory elements.
    """
    if narration_count is None:
        narration_count = MEMORY_ANALYSIS_NARRATION_COUNT
    state = session.get_world_state()
    
    # Get recent narrations for analysis
    recent_narrations = _get_recent_narrations(state, count=narration_count)
    
    if not recent_narrations:
        logger.warning("No narrations found for memory analysis")
        return ""
    
    parts = []
    
    # System role
    parts.append("Extract memory from story narrations. Output ONLY valid JSON. NO extra text.")
    parts.append("")
    
    # Provide narrations to analyze
    parts.append(f"NARRATIONS TO ANALYZE ({len(recent_narrations)} total):")
    parts.append("-" * 50)
    for i, narr in enumerate(recent_narrations, 1):
        parts.append(f"{i}. {narr}")
    parts.append("-" * 50)
    parts.append("")
    
    # Extraction instructions
    parts.append("EXTRACT THE FOLLOWING (use [] if none found):")
    parts.append("  - NPCs: name, personality (2-5 words), description (1 sentence)")
    parts.append("  - Locations: name, description (1 sentence)")
    parts.append("  - Items: name, description (1 sentence)")
    parts.append("  - Relationships: npc name, affinity (-100 to 100), status")
    parts.append("  - Events: brief description (1 sentence each)")
    parts.append("  - Discoveries: revelations/secrets (1 sentence each)")
    parts.append("")
    
    # Output format
    parts.append("OUTPUT JSON FORMAT:")
    parts.append('{')
    parts.append('  "npcs": [{"name": "Name", "personality": "traits", "description": "desc"}],')
    parts.append('  "locations": [{"name": "Place", "description": "desc"}],')
    parts.append('  "inventory": [{"item": "Item", "description": "desc"}],')
    parts.append('  "relationships": [{"npc": "Name", "affinity": 50, "status": "friendly"}],')
    parts.append('  "events": ["Event description"],')
    parts.append('  "discoveries": ["Discovery description"]')
    parts.append('}')
    parts.append("")
    
    # Rules
    parts.append("RULES:")
    parts.append("  - Extract ONLY what is explicitly stated or strongly implied")
    parts.append("  - Use [] for empty arrays")
    parts.append("  - Output ONLY the JSON. No explanations.")
    parts.append("")
    
    parts.append('{"npcs": []')
    
    return "\n".join(parts)


# ============================================================================
# HELPER FUNCTIONS (Unchanged - keep as is)
# ============================================================================

def _get_recent_narrations(state: dict, count: int = 5) -> list:
    """Get last N narrations from history"""
    narrations = []
    
    if "narration_history" in state:
        narrations = state["narration_history"][-count:]
    elif "last_narration" in state:
        narrations = [state["last_narration"]]
    
    return narrations


def _get_current_location(state: dict) -> str:
    """Get current location from memory with description"""
    memory = state.get("memory", {})
    locations = memory.get("locations", {})
    
    if not locations:
        return ""
    
    sorted_locs = sorted(
        locations.items(),
        key=lambda x: x[1].get("last_visited_step", 0),
        reverse=True
    )
    
    if sorted_locs:
        name, data = sorted_locs[0]
        location_str = name
        if data.get("description"):
            location_str += f" - {data['description']}"
        return location_str
    
    return ""


def _get_active_npcs(state: dict, count: int = 3) -> list:
    """Get most recently seen NPCs"""
    memory = state.get("memory", {})
    npcs = memory.get("npcs", {})
    relationships = memory.get("relationships", {})
    
    if not npcs:
        return []
    
    sorted_npcs = sorted(
        npcs.items(),
        key=lambda x: x[1].get("last_seen_step", 0),
        reverse=True
    )
    
    result = []
    for name, data in sorted_npcs[:count]:
        npc_str = name
        if data.get("personality"):
            npc_str += f" ({data['personality']})"
        
        if name in relationships:
            affinity = relationships[name].get("affinity", 0)
            if affinity >= 30:
                npc_str += f" [Friendly]"
            elif affinity <= -30:
                npc_str += f" [Hostile]"
        
        result.append(npc_str)
    
    return result


def _get_key_items(state: dict, count: int = 5) -> list:
    """Get most important inventory items"""
    memory = state.get("memory", {})
    inventory = memory.get("inventory", [])
    
    if not inventory:
        return []
    
    sorted_items = sorted(
        inventory,
        key=lambda x: x.get("acquired_step", 0),
        reverse=True
    )
    
    return [item["item"] for item in sorted_items[:count]]


def _get_character_development(state: dict) -> str:
    """Get brief character development summary"""
    step_count = state.get("step_count", 0)
    
    if step_count < 3:
        return "just beginning"
    elif step_count < 8:
        return "developing through experiences"
    elif step_count < 12:
        return "grown significantly, facing critical moments"
    else:
        return "journey reaching conclusion"


def _get_recent_discoveries(state: dict, count: int = 3) -> list:
    """Get recent important discoveries"""
    memory = state.get("memory", {})
    discoveries = memory.get("discoveries", [])
    
    if not discoveries:
        return []
    
    sorted_discoveries = sorted(
        discoveries,
        key=lambda x: x.get("step", 0),
        reverse=True
    )
    
    return [d.get("discovery", "") for d in sorted_discoveries[:count]]


def _get_important_events(state: dict, count: int = 2) -> list:
    """Get recent important events"""
    memory = state.get("memory", {})
    events = memory.get("events", [])
    
    if not events:
        return []
    
    important_events = [e for e in events if e.get("importance") in ["high", "critical"]]
    
    if len(important_events) >= count:
        sorted_events = sorted(
            important_events,
            key=lambda x: x.get("step", 0),
            reverse=True
        )
    else:
        sorted_events = sorted(
            events,
            key=lambda x: x.get("step", 0),
            reverse=True
        )
    
    return [e.get("description", "") for e in sorted_events[:count]]


def _get_recent_consequences(state: dict, count: int = 3) -> list:
    """Get recent consequences of player actions"""
    consequences = state.get("consequences", [])
    if not consequences:
        return []
    return consequences[-count:]


def _get_active_relationships(state: dict, count: int = 5) -> list:
    """Get active NPC relationships"""
    relationships = state.get("relationships", {})
    
    if not relationships:
        return []
    
    sorted_rels = sorted(
        relationships.items(),
        key=lambda x: abs(x[1].get("affinity", 0)),
        reverse=True
    )
    
    result = []
    for npc_name, rel_data in sorted_rels[:count]:
        affinity = rel_data.get("affinity", 0)
        status = rel_data.get("status", "neutral")
        
        if affinity >= 30:
            emoji = "💚"
        elif affinity <= -30:
            emoji = "⚠️"
        else:
            emoji = "🤝"
        
        result.append(f"{emoji} {npc_name}: {status}")
    
    return result


def _get_inventory_items(state: dict, count: int = 8) -> list:
    """Get inventory items"""
    inventory = state.get("inventory", [])
    if not inventory:
        return []
    return inventory[-count:]


def _get_current_objectives(state: dict) -> list:
    """Get active quests/objectives"""
    objectives = state.get("objectives", [])
    if not objectives:
        return []
    
    active = [obj for obj in objectives if obj.get("status") == "active"]
    return [obj.get("description", "") for obj in active[:3]]