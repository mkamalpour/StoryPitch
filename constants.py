"""
constants.py - Centralized Constants for Story Maker Bot
=========================================================

This file contains ALL shared constants used across the application to eliminate
duplication and ensure consistency. Any hardcoded values that appear in multiple
places should be defined here.

USAGE:
    from constants import THEME_LIST, TRAIT_LIST, FALLBACK_CHOICES, LOG_SEPARATOR
    
CONSTANT CATEGORIES:
    1. THEME_LIST - Predefined story themes for quick selection
    2. TRAIT_LIST - Character personality traits that influence story
    3. TRAIT_GUIDELINES - How each trait affects AI-generated choices
    4. FALLBACK_RESPONSES - Default responses when AI fails or returns invalid data
    5. LOGGING_CONSTANTS - Separators and formatting for consistent logs

WHY CENTRALIZED CONSTANTS?
    - Single Source of Truth: Change once, update everywhere
    - Consistency: Same values across all modules
    - Maintainability: Easy to find and update constants
    - DRY Principle: Don't Repeat Yourself
    
NOTES:
    - These constants are imported by multiple modules (api, ui, story, llm)
    - Fallback responses ensure the app never crashes due to AI failures
    - Trait guidelines help the AI generate personality-appropriate choices
"""

# ============================================================================
# THEME CONSTANTS
# ============================================================================

THEME_LIST = [
    # Fantasy & Magic
    "A medieval kingdom with magic and dragons",
    "A magical forest where time flows differently",
    "An enchanted library where books come alive",
    "A floating island city powered by ancient crystals",
    "A realm where dreams and reality merge",
    "A wizard academy for forbidden magic",
    "A cursed kingdom frozen in eternal winter",
    "A world where mythical creatures rule",
    
    # Sci-Fi & Space
    "A space station on the edge of the galaxy",
    "A cyberpunk city with advanced technology",
    "A colony on Mars facing mysterious threats",
    "A time-traveling adventure through history",
    "An AI-controlled megacity in the year 3000",
    "A generation ship searching for a new home",
    "A virtual reality world with hidden glitches",
    "A parallel dimension with alternate physics",
    
    # Mystery & Horror
    "A mysterious school where everyone hides secrets",
    "A haunted mansion with supernatural mysteries",
    "A detective agency solving paranormal cases",
    "A small town where people keep disappearing",
    "An abandoned hospital with dark experiments",
    "A cursed antique shop that grants wishes",
    "A fog-covered Victorian city with serial mysteries",
    "A carnival that appears only at midnight",
    
    # Adventure & Exploration
    "An underwater civilization with ancient secrets",
    "A post-apocalyptic wasteland with hidden survivors",
    "A jungle expedition searching for lost temples",
    "A sky pirate crew sailing on airships",
    "A desert caravan discovering buried cities",
    "An arctic research station with strange findings",
    "A mountain monastery guarding ancient knowledge",
    "A treasure hunt across multiple continents",
    
    # Urban & Modern
    "A bustling city where magic is hidden in plain sight",
    "A high school with supernatural students",
    "A coffee shop that serves as a portal hub",
    "A underground resistance fighting corporate control",
    "A music festival that changes reality",
    "A street racing scene with modified vehicles",
    "A fashion empire with dark secrets",
    "A social media platform that predicts the future",
    
    # Historical & Period
    "A samurai's journey in feudal Japan",
    "A pirate adventure on the high seas",
    "An Egyptian tomb with ancient curses",
    "A Wild West town with supernatural elements",
    "A Renaissance court full of intrigue",
    "A Viking voyage to unknown lands",
    "A Roman gladiator arena with hidden magic",
    "A 1920s speakeasy with time anomalies",
    
    # Unique & Creative
    "A world inside a giant clockwork machine",
    "A restaurant at the end of the universe",
    "A museum where exhibits come to life at night",
    "A circus that travels between dimensions",
    "A garden where plants have consciousness",
    "A train that never stops moving",
    "A bookstore that exists in multiple timelines",
    "A lighthouse that guides souls between worlds"
]

# ============================================================================
# CHARACTER TRAIT CONSTANTS
# ============================================================================

# Core traits that significantly impact story choices and AI behavior
# Each trait has specific guidelines that influence how the AI generates choices
TRAIT_LIST = [
    "Brave",
    "Cautious", 
    "Clever",
    "Curious",
    "Charismatic",
    "Honest",
    "Deceptive",
    "Patient",
    "Impulsive",
    "Resourceful",
    "Analytical",
    "Creative",
    "Compassionate",
    "Ruthless",
    "Optimistic",
    "Cynical",
    "Loyal",
    "Rebellious",
    "Funny",
    "Mysterious"
]

# Trait-based choice generation guidelines for AI prompts
# Maps each trait to how it should influence story choices
# These are actively used in prompt generation to ensure traits have real impact
TRAIT_GUIDELINES = {
    "brave": "Bold, risky options that face danger head-on",
    "cautious": "Safe, calculated options that minimize risk",
    "clever": "Strategic, intellectual solutions using wit",
    "curious": "Investigative choices seeking knowledge",
    "charismatic": "Persuasive social options using charm",
    "honest": "Truthful, straightforward choices valuing integrity",
    "deceptive": "Manipulative, cunning options hiding intentions",
    "patient": "Observational, careful planning approaches",
    "impulsive": "Quick, spontaneous actions without planning",
    "resourceful": "Creative solutions using limited means",
    "analytical": "Logical, systematic paths examining evidence",
    "creative": "Innovative, unconventional outside-the-box solutions",
    "compassionate": "Caring options prioritizing others' wellbeing",
    "ruthless": "Efficient, morally-gray choices prioritizing results",
    "optimistic": "Hopeful, positive choices seeing the best",
    "cynical": "Skeptical options doubting motives",
    "loyal": "Faithful choices standing by allies",
    "rebellious": "Rule-breaking choices challenging authority",
    "funny": "Lighthearted, humorous options using wit",
    "mysterious": "Enigmatic, secretive choices hiding intentions"
}

# ============================================================================
# CHARACTER NAME PRESETS
# ============================================================================

CHARACTER_NAME_LIST = [
    # Classic Fantasy
    "Alex", "Morgan", "Jordan", "Riley", "Casey",
    "Aria", "Luna", "Nova", "Sage", "Phoenix",
    "Rowan", "Ash", "Ember", "Storm", "River",
    
    # Medieval/Fantasy
    "Aldric", "Theron", "Gareth", "Cedric", "Dorian",
    "Elara", "Lyra", "Seraphina", "Isolde", "Freya",
    "Kael", "Zephyr", "Orion", "Atlas", "Magnus",
    
    # Sci-Fi/Futuristic
    "Zane", "Cyrus", "Axel", "Neo", "Kai",
    "Nova", "Echo", "Vega", "Astrid", "Celeste",
    "Jax", "Rex", "Blaze", "Volt", "Cipher",
    
    # Mysterious/Dark
    "Raven", "Shadow", "Onyx", "Midnight", "Obsidian",
    "Vesper", "Nyx", "Sable", "Dusk", "Eclipse",
    "Wraith", "Phantom", "Shade", "Umbra", "Void",
    
    # Nature-Inspired
    "Willow", "Hazel", "Ivy", "Jasper", "Jade",
    "Autumn", "Summer", "Winter", "Dawn", "Sky",
    "Ocean", "Forest", "Mountain", "Meadow", "Brook",
    
    # Strong/Heroic
    "Victor", "Maximus", "Titan", "Hunter", "Ranger",
    "Valeria", "Victoria", "Athena", "Diana", "Artemis",
    "Drake", "Griffin", "Leon", "Dante", "Blade",
    
    # Elegant/Sophisticated
    "Sebastian", "Alexander", "Theodore", "Vincent", "Adrian",
    "Isabella", "Anastasia", "Genevieve", "Evangeline", "Vivienne",
    "Lucian", "Damien", "Julian", "Tristan", "Raphael",
    
    # Short & Punchy
    "Max", "Sam", "Lee", "Jay", "Finn",
    "Mia", "Zoe", "Ava", "Kai", "Rex",
    "Ace", "Fox", "Jet", "Sky", "Ray",
    
    # Exotic/Unique
    "Zephyra", "Kairos", "Lyric", "Solstice", "Zenith",
    "Azura", "Indigo", "Crimson", "Saffron", "Cobalt",
    "Quantum", "Nexus", "Prism", "Aether", "Cosmos"
]

# ============================================================================
# STORY TITLE PRESETS
# ============================================================================

STORY_TITLE_LIST = [
    # Epic Fantasy
    "The Legend of the Lost Kingdom",
    "Chronicles of the Dragon's Heir",
    "Quest for the Ancient Artifact",
    "The Last Mage of Eldoria",
    "Shadows of the Forgotten Realm",
    
    # Sci-Fi Adventures
    "Beyond the Stars",
    "The Quantum Paradox",
    "Echoes from the Future",
    "Starship Chronicles",
    "The Cybernetic Awakening",
    
    # Mystery & Thriller
    "The Midnight Conspiracy",
    "Secrets of the Manor",
    "The Detective's Last Case",
    "Whispers in the Dark",
    "The Vanishing Hour",
    
    # Horror & Dark
    "Tales from the Abyss",
    "The Haunting of Blackwood",
    "Nightmare Chronicles",
    "The Cursed Inheritance",
    "Shadows That Follow",
    
    # Adventure & Exploration
    "Journey to the Unknown",
    "The Explorer's Odyssey",
    "Treasures of the Lost World",
    "Adventures Beyond the Horizon",
    "The Wanderer's Tale",
    
    # Urban & Modern
    "City of Secrets",
    "The Underground Network",
    "Neon Nights",
    "Streets of Destiny",
    "The Urban Legend",
    
    # Heroic & Epic
    "Rise of the Champion",
    "The Hero's Journey",
    "Destiny's Call",
    "The Chosen One",
    "Legends Never Die",
    
    # Mysterious & Magical
    "The Enchanted Path",
    "Mysteries of the Arcane",
    "The Sorcerer's Apprentice",
    "Realm of Wonders",
    "The Magic Within",
    
    # Short & Punchy
    "The Quest",
    "New Beginnings",
    "The Awakening",
    "Uncharted",
    "The Journey",
    "Destiny",
    "The Adventure",
    "Revelations",
    
    # Creative & Unique
    "When Time Stood Still",
    "The Price of Power",
    "Echoes of Eternity",
    "The Forgotten Promise",
    "Where Legends Begin"
]

# ============================================================================
# FALLBACK RESPONSES (Single Source of Truth)
# ============================================================================

# Standard fallback narration when AI fails
FALLBACK_NARRATION = (
    "The story continues with new possibilities ahead. "
    "What would you like to do?"
)

# Standard fallback choices (used across parser, postprocess, logic, manager)
FALLBACK_CHOICES = [
    "Continue exploring",
    "Investigate further",
    "Take a different approach",
    "Plan your next move"
]

# Standard fallback clues
FALLBACK_CLUES = "Something interesting might be nearby..."

# Complete fallback response dict (for parser and logic)
FALLBACK_RESPONSE = {
    "narration": FALLBACK_NARRATION,
    "choices": FALLBACK_CHOICES[:3],  # Use first 3 by default
    "clues": FALLBACK_CLUES
}

# Text format fallback (for LLM manager)
FALLBACK_AI_TEXT = (
    "Narration: The story continues with new developments.\n\n"
    "Choices:\n"
    "1) Continue exploring\n"
    "2) Investigate further\n"
    "3) Take a different approach\n\n"
    "Clues: New information has been discovered."
)

# ============================================================================
# STORY MEMORY CONSTANTS
# ============================================================================

# How many recent narrations to keep in context for story generation
NARRATION_HISTORY_COUNT = 3  # Keep last N narrations for continuity

# Memory refresh settings (for "Refresh Memory" button)
MEMORY_ANALYSIS_NARRATION_COUNT = 3  # Analyze last N narrations for memory extraction

# Memory limits (to prevent bloat)
MEMORY_MAX_EVENTS = 50  # Maximum events to keep in memory
MEMORY_MAX_DISCOVERIES = 30  # Maximum discoveries to keep
MEMORY_RECENT_EVENTS_KEEP = 30  # Keep last N events when trimming

# Context window sizes for prompts
PROMPT_RECENT_NARRATIONS = 2  # Recent narrations to include in prompt (REDUCED for speed)
PROMPT_ACTIVE_NPCS = 2  # Active NPCs to show in current scene (REDUCED for speed)
PROMPT_KEY_ITEMS = 2  # Key items to mention (REDUCED for speed)
PROMPT_RECENT_DISCOVERIES = 1  # Recent discoveries to include (REDUCED for speed)
PROMPT_IMPORTANT_EVENTS = 1  # Important events to include (REDUCED for speed)
PROMPT_RECENT_CONSEQUENCES = 1  # Recent consequences to show (REDUCED for speed)
PROMPT_ACTIVE_RELATIONSHIPS = 1  # Active relationships to track (REDUCED for speed)
PROMPT_INVENTORY_ITEMS = 1  # Inventory items to display (REDUCED for speed)

# Story arc progression thresholds (in steps)
STORY_ARC_BEGINNING_END = 3  # Steps 1-3: beginning
STORY_ARC_RISING_END = 8  # Steps 4-8: rising action
STORY_ARC_CLIMAX_END = 12  # Steps 9-12: climax
# Steps 13+: resolution

# ============================================================================
# LOGGING CONSTANTS
# ============================================================================

LOG_SEPARATOR = "=" * 100
LOG_SEPARATOR_SHORT = "=" * 60

# Note: Log rotation settings (LOG_MAX_BYTES, LOG_BACKUP_COUNT, LOG_RETENTION_MINUTES)
# are defined in config.py to avoid circular imports and keep configuration centralized

# ============================================================================
# SYSTEM CONSTANTS
# ============================================================================

# Startup timing
API_STARTUP_WAIT_SECONDS = 4  # Time to wait for API server to be ready
THREAD_SHUTDOWN_TIMEOUT_SECONDS = 2  # Timeout for graceful thread shutdown

# File size constants
BYTES_PER_KB = 1024
BYTES_PER_MB = 1024 * 1024
MEGABYTES_TO_BYTES = 1024 * 1024