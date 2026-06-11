# story/logic.py
from db.db import create_session, get_session, update_session, save_step, get_steps, init_db
from story.prompts import build_fast_prompt  # Optimized fast prompts
from story.parser import parse_ai_output
from story.postprocess import normalize_ai_text_to_story
from llm.adapters import generate
from story.memory import StoryMemory
from constants import (
    FALLBACK_AI_TEXT, 
    FALLBACK_NARRATION, 
    FALLBACK_CHOICES,
    NARRATION_HISTORY_COUNT,
    STORY_ARC_BEGINNING_END,
    STORY_ARC_RISING_END,
    STORY_ARC_CLIMAX_END
)
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)

async def start_session(
    user_id: int, 
    title: str, 
    theme: str | None = None, 
    traits: List[str] | None = None,
    character_name: str | None = None,
    model: str | None = None
) -> Dict[str, Any]:
    """
    Start a new story session with optional theme, traits, and character name.
    
    Args:
        user_id: The user's ID
        title: Session title
        theme: Story theme (e.g., "A mysterious school where everyone hides secrets")
        traits: Character traits (e.g., ["brave", "curious"])
        character_name: Character's name (e.g., "Alex")
    
    Returns:
        Dict with session_id, narration, choices, and clues
    """
    logger.info("=" * 100)
    logger.info("🎬 START NEW SESSION")
    logger.info("=" * 100)
    logger.info("User ID: %d", user_id)
    logger.info("Title: %s", title)
    logger.info("Theme: %s", theme or "An adventure begins")
    logger.info("Character Name: %s", character_name or "the hero")
    logger.info("Traits: %s", traits or [])
    logger.info("Model: %s", model or "default")
    logger.info("=" * 100)
    
    try:
        # Ensure DB is initialized (idempotent)
        logger.info("🗄️  Initializing database...")
        init_db()
        logger.info("✅ Database initialized")
        
        world_state = {
            "theme": theme or "An adventure begins",
            "traits": traits or [],
            "character_name": character_name or "the hero",
            "clues": [],
            "consequences": [],  # Track consequences of player actions
            "discoveries": [],  # Track important discoveries
            "relationships": {},  # Track relationships with NPCs (affinity, status)
            "inventory": [],  # Track items or abilities gained
            "objectives": [],  # Track active quests/goals
            "story_arc": "beginning",  # Track story progression: beginning, rising, climax, resolution
            "world_rules": []  # Track established world facts for consistency
        }
        
        logger.info("📝 Creating session in database...")
        sess = create_session(user_id=user_id, title=title, world_state=world_state)
        logger.info(f"✅ Session created - ID: {sess.id}")
        
        logger.info("🔨 Building initial story prompt (FAST MODE)...")
        prompt = build_fast_prompt(sess, user_input=None)  # USE FAST PROMPT
        logger.info("✅ Prompt built - Length: %d chars", len(prompt))
        logger.debug("Prompt preview: %s...", prompt[:300])
        
        # Generate with retry logic (short)
        logger.info("🤖 Generating AI story content (with retry logic)...")
        ai_text = None
        for attempt in range(2):
            try:
                logger.info("🔄 Generation attempt %d/2", attempt + 1)
                ai_text = await generate(prompt, primary=model)
                if ai_text and ai_text.strip():
                    logger.info("✅ AI generation successful on attempt %d", attempt + 1)
                    break
                logger.warning(f"⚠️  Empty AI response on attempt {attempt + 1}")
            except Exception as e:
                logger.error(f"❌ AI generation failed on attempt {attempt + 1}: {e}")
                if attempt == 1:  # Last attempt (0-indexed)
                    logger.error("❌ All retry attempts exhausted")
                    raise
        
        if not ai_text or not ai_text.strip():
            logger.error("❌ All AI generation attempts failed, using hardcoded fallback")
            ai_text = "Narration: Your adventure begins in a mysterious place full of possibilities.\n\nChoices:\n1) Explore the area\n2) Look for clues\n3) Take a different path\n\nClues: Something interesting awaits discovery."
        
        logger.info("📥 AI output received - Length: %d chars", len(ai_text))
        logger.debug("AI output preview: %s...", ai_text[:300])
        
        logger.info("🔍 Parsing and normalizing AI output...")
        parsed = normalize_ai_text_to_story(ai_text)
        logger.info("✅ Parsing complete")
        
        # Validate parsed content
        logger.info("🔍 Validating parsed content...")
        if not parsed.get("narration"):
            logger.warning("⚠️  No narration in parsed output, using fallback")
            parsed["narration"] = "Your adventure begins in a mysterious place full of possibilities."
        else:
            logger.info("✅ Narration validated - Length: %d chars", len(parsed["narration"]))
        
        if not parsed.get("choices"):
            logger.warning("⚠️  No choices in parsed output, using defaults")
            parsed["choices"] = ["Explore the area", "Look for clues", "Take a different path"]
        else:
            logger.info("✅ Choices validated - Count: %d", len(parsed["choices"]))
            for i, choice in enumerate(parsed["choices"], 1):
                logger.info("   Choice %d: %s", i, choice)
        
        # Update world state with first narration and clues
        logger.info("💾 Updating session world state...")
        ws = sess.get_world_state()
        ws["last_narration"] = parsed["narration"]
        ws["last_choices"] = parsed["choices"]  # Store choices for reference
        
        # NEW: Track narration history for context (configurable via constants)
        ws.setdefault("narration_history", [])
        ws["narration_history"].append(parsed["narration"])
        ws["narration_history"] = ws["narration_history"][-NARRATION_HISTORY_COUNT:]  # Keep last N
        
        if parsed.get("clues"):
            ws["clues"].append(parsed["clues"])
            logger.info("🔍 Clues added: %s", parsed["clues"])
        
        # Track story beginning
        ws["story_arc"] = "beginning"
        ws.setdefault("step_count", 0)
        ws["step_count"] = 1
        
        # 🧠 SAVE MEMORY DIRECTLY (from AI output - no extra call needed!)
        if parsed.get("memory"):
            logger.info("🧠 Processing memory from AI output...")
            memory = StoryMemory(ws)
            extracted_memory = parsed["memory"]
            
            # Add NPCs (with step tracking for interaction counts)
            for npc_name in extracted_memory.get("npcs", []):
                if npc_name and npc_name.strip():
                    memory.add_npc(npc_name.strip(), step=1)
                    logger.info(f"  👤 Added NPC: {npc_name}")
            
            # Add locations (with step tracking for visit counts)
            for location in extracted_memory.get("locations", []):
                if location and location.strip():
                    memory.add_location(location.strip(), step=1)
                    logger.info(f"  🗺️ Added location: {location}")
            
            # Add items
            for item in extracted_memory.get("items", []):
                if item and item.strip():
                    memory.add_item(item.strip(), step=1)
                    logger.info(f"  🎒 Added item: {item}")
            
            # Add events
            for event in extracted_memory.get("events", []):
                if event and event.strip():
                    memory.add_event(event.strip(), step=1)
                    logger.info(f"  📅 Added event: {event}")
            
            # Add discoveries
            for discovery in extracted_memory.get("discoveries", []):
                if discovery and discovery.strip():
                    memory.add_discovery(discovery.strip(), step=1)
                    logger.info(f"  💡 Added discovery: {discovery}")
            
            logger.info("✅ Memory saved successfully")
        
        logger.info("💾 Saving session state to database...")
        update_session(sess.id, world_state=ws, current_step=1)
        save_step(sess.id, 1, prompt, ai_text, None)
        logger.info("✅ Session state saved")
        
        logger.info("=" * 100)
        logger.info(f"🎉 SESSION {sess.id} STARTED SUCCESSFULLY")
        logger.info(f"   Narration: {len(parsed['narration'])} chars")
        logger.info(f"   Choices: {len(parsed['choices'])} options")
        logger.info(f"   Clues: {parsed.get('clues', 'None')}")
        logger.info("=" * 100)
        
        result = {
            "session_id": sess.id, 
            "narration": parsed["narration"], 
            "choices": parsed["choices"], 
            "clues": parsed["clues"]
        }
        
        print("\n" + "=" * 100)
        print(f"✅ SESSION STARTED: ID={sess.id}")
        print(f"📖 Narration: {parsed['narration'][:100]}...")
        print(f"🎯 Choices: {len(parsed['choices'])} available")
        print("=" * 100 + "\n")
        
        return result
        
    except Exception as e:
        logger.error("=" * 100)
        logger.error(f"❌ FAILED TO START SESSION for user {user_id}")
        logger.error(f"Error: {e}")
        logger.error("=" * 100)
        raise ValueError(f"Failed to start session: {str(e)}")

async def advance_session(session_id: int, user_input: str | None = None, choice_index: int | None = None, model: str | None = None) -> Dict[str, Any]:
    logger.info("=" * 100)
    logger.info("⏭️  ADVANCE SESSION")
    logger.info("=" * 100)
    logger.info("Session ID: %d", session_id)
    logger.info("User Input: %s", user_input or "(None)")
    logger.info("Choice Index: %s", choice_index if choice_index is not None else "(None)")
    logger.info("Model: %s", model or "default")
    logger.info("=" * 100)
    
    try:
        # Ensure DB is initialized (idempotent)
        logger.info("🗄️  Initializing database...")
        init_db()
        logger.info("✅ Database initialized")
        
        logger.info("🔍 Fetching session from database...")
        sess = get_session(session_id)
        if not sess:
            logger.error("❌ Session %d not found in database", session_id)
            raise ValueError("session not found")
        logger.info(f"✅ Session found - Current step: {sess.current_step}")
        
        # SMART LOGIC: Prioritize choice_index over user_input (only one should be used)
        final_input = None
        
        if choice_index is not None:
            # User selected a predefined choice - use it
            logger.info("🎯 SMART MODE: Using predefined choice (index %d)", choice_index)
            history = get_steps(session_id)
            if history:
                last = history[-1]
                parsed_last = parse_ai_output(last.ai_output)
                choices = parsed_last.get("choices", [])
                logger.info("📋 Available choices from last step: %d", len(choices))
                if 1 <= choice_index <= len(choices):
                    final_input = choices[choice_index - 1]
                    logger.info(f"✅ Selected choice {choice_index}: '{final_input}'")
                else:
                    logger.warning(f"⚠️  Invalid choice index {choice_index}, available: {len(choices)}")
                    raise ValueError(f"Invalid choice index {choice_index}. Available: 1-{len(choices)}")
            else:
                logger.warning("⚠️  No history found for choice translation")
                raise ValueError("Cannot use choice_index: no previous step found")
        elif user_input and user_input.strip():
            # User typed custom input - use it
            logger.info("✍️  SMART MODE: Using custom user input")
            final_input = user_input.strip()
            logger.info(f"✅ Custom input: '{final_input}'")
        else:
            # Neither provided - error
            logger.error("❌ No input provided (neither choice_index nor user_input)")
            raise ValueError("Must provide either choice_index or user_input")
        
        logger.info("🔨 Building story prompt with final input (FAST MODE)...")
        prompt = build_fast_prompt(sess, user_input=final_input)  # USE FAST PROMPT
        logger.info("✅ Prompt built - Length: %d chars", len(prompt))
        logger.debug("Prompt preview: %s...", prompt[:300])
        
        # Generate with retry logic (short)
        logger.info("🤖 Generating AI story continuation (with retry logic)...")
        ai_text = None
        for attempt in range(2):
            try:
                logger.info("🔄 Generation attempt %d/2", attempt + 1)
                ai_text = await generate(prompt, primary=model)
                if ai_text and ai_text.strip():
                    logger.info("✅ AI generation successful on attempt %d", attempt + 1)
                    break
                logger.warning(f"⚠️  Empty AI response on attempt {attempt + 1}")
            except Exception as e:
                logger.error(f"❌ AI generation failed on attempt {attempt + 1}: {e}")
                if attempt == 1:  # Last attempt (0-indexed)
                    logger.error("❌ All retry attempts exhausted")
                    raise
        
        if not ai_text or not ai_text.strip():
            logger.error("❌ All AI generation attempts failed, using hardcoded fallback")
            ai_text = FALLBACK_AI_TEXT
        
        logger.info("📥 AI output received - Length: %d chars", len(ai_text))
        logger.debug("AI output preview: %s...", ai_text[:300])
        
        logger.info("🔍 Parsing and normalizing AI output...")
        parsed = normalize_ai_text_to_story(ai_text)
        logger.info("✅ Parsing complete")
        
        # Validate parsed content
        logger.info("🔍 Validating parsed content...")
        if not parsed.get("narration"):
            logger.warning("⚠️  No narration in parsed output, using fallback")
            parsed["narration"] = FALLBACK_NARRATION
        else:
            logger.info("✅ Narration validated - Length: %d chars", len(parsed["narration"]))
        
        if not parsed.get("choices"):
            logger.warning("⚠️  No choices in parsed output, using defaults")
            parsed["choices"] = FALLBACK_CHOICES[:3]
        else:
            logger.info("✅ Choices validated - Count: %d", len(parsed["choices"]))
            for i, choice in enumerate(parsed["choices"], 1):
                logger.info("   Choice %d: %s", i, choice)
        
        logger.info("💾 Updating session world state...")
        ws = sess.get_world_state()
        ws["last_narration"] = parsed["narration"]
        ws["last_choices"] = parsed["choices"]  # Store choices for reference
        ws["last_action"] = final_input  # Store what player did
        
        # NEW: Track narration history for context (configurable via constants)
        ws.setdefault("narration_history", [])
        ws["narration_history"].append(parsed["narration"])
        ws["narration_history"] = ws["narration_history"][-NARRATION_HISTORY_COUNT:]  # Keep last N
        
        if parsed.get("clues"):
            ws.setdefault("clues", []).append(parsed["clues"])
            logger.info("🔍 Clues added: %s", parsed["clues"])
        
        # Track consequences of this action
        consequence_summary = f"Step {sess.current_step + 1}: {final_input[:50]}..."
        ws.setdefault("consequences", []).append(consequence_summary)
        logger.info("⚖️ Consequence tracked: %s", consequence_summary)
        
        # Update step count and story arc
        ws.setdefault("step_count", 0)
        ws["step_count"] += 1
        
        # Update story arc based on progression (configurable via constants)
        step_count = ws["step_count"]
        if step_count <= STORY_ARC_BEGINNING_END:
            ws["story_arc"] = "beginning"
        elif step_count <= STORY_ARC_RISING_END:
            ws["story_arc"] = "rising"
        elif step_count <= STORY_ARC_CLIMAX_END:
            ws["story_arc"] = "climax"
        else:
            ws["story_arc"] = "resolution"
        
        logger.info(f"📊 Story progression: Step {step_count}, Arc: {ws['story_arc']}")
        
        # Calculate next step index (needed for memory tracking)
        step_index = sess.current_step + 1
        
        # 🧠 SAVE MEMORY DIRECTLY (from AI output - no extra call needed!)
        if parsed.get("memory"):
            logger.info("🧠 Processing memory from AI output...")
            memory = StoryMemory(ws)
            extracted_memory = parsed["memory"]
            
            # Add NPCs (with step tracking for interaction counts)
            for npc_name in extracted_memory.get("npcs", []):
                if npc_name and npc_name.strip():
                    memory.add_npc(npc_name.strip(), step=step_index)
                    logger.info(f"  👤 Added NPC: {npc_name}")
            
            # Add locations (with step tracking for visit counts)
            for location in extracted_memory.get("locations", []):
                if location and location.strip():
                    memory.add_location(location.strip(), step=step_index)
                    logger.info(f"  🗺️ Added location: {location}")
            
            # Add items
            for item in extracted_memory.get("items", []):
                if item and item.strip():
                    memory.add_item(item.strip(), step=step_index)
                    logger.info(f"  🎒 Added item: {item}")
            
            # Add events
            for event in extracted_memory.get("events", []):
                if event and event.strip():
                    memory.add_event(event.strip(), step=step_index)
                    logger.info(f"  📅 Added event: {event}")
            
            # Add discoveries
            for discovery in extracted_memory.get("discoveries", []):
                if discovery and discovery.strip():
                    memory.add_discovery(discovery.strip(), step=step_index)
                    logger.info(f"  💡 Added discovery: {discovery}")
            
            logger.info("✅ Memory saved successfully")
        logger.info("💾 Saving session state to database (step %d -> %d)...", sess.current_step, step_index)
        update_session(session_id, world_state=ws, current_step=step_index)
        save_step(session_id, step_index, prompt, ai_text, final_input)
        logger.info("✅ Session state saved")
        
        logger.info("=" * 100)
        logger.info(f"🎉 SESSION {session_id} ADVANCED TO STEP {step_index}")
        logger.info(f"   Narration: {len(parsed['narration'])} chars")
        logger.info(f"   Choices: {len(parsed['choices'])} options")
        logger.info(f"   Clues: {parsed.get('clues', 'None')}")
        logger.info("=" * 100)
        
        result = {
            "narration": parsed["narration"], 
            "choices": parsed["choices"], 
            "clues": parsed["clues"], 
            "step_index": step_index
        }
        
        print("\n" + "=" * 100)
        print(f"✅ SESSION ADVANCED: ID={session_id}, Step={step_index}")
        print(f"📖 Narration: {parsed['narration'][:100]}...")
        print(f"🎯 Choices: {len(parsed['choices'])} available")
        print("=" * 100 + "\n")
        
        return result
        
    except Exception as e:
        logger.error("=" * 100)
        logger.error(f"❌ FAILED TO ADVANCE SESSION {session_id}")
        logger.error(f"Error: {e}")
        logger.error("=" * 100)
        raise ValueError(f"Failed to advance session: {str(e)}")
