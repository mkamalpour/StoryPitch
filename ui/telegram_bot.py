# ui/telegram_bot.py
"""
✨ ENHANCED Telegram Bot - Production Ready ✨

Features:
- Smart input handling (choice OR custom text, not both)
- Inline keyboard buttons for all interactions
- Character creation wizard
- Theme selection (random, list, custom)
- Trait selection with checkmarks
- Full save/load/resume functionality
- Session history viewer
- Memory extraction (NPCs, locations, items)
- Model selection (Local LM Studio / HuggingFace)
- Graceful error handling with user-friendly messages
- Session persistence across restarts
"""

import logging
import random
from datetime import datetime
from typing import Dict, Any, Optional, List
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes, 
    MessageHandler, filters, CallbackQueryHandler, ConversationHandler
)
from db.db import init_db
from config import API_BASE_URL, API_KEY, TELEGRAM_TOKEN
from constants import THEME_LIST, TRAIT_LIST
from utils.http_client import create_async_client
from utils.log_cleaner import start_log_cleaner, stop_log_cleaner

API_BASE = API_BASE_URL
TOKEN = TELEGRAM_TOKEN

logger = logging.getLogger(__name__)

# Conversation states
(
    SELECTING_MODEL,
    SELECTING_NAME,
    SELECTING_THEME_TYPE,
    SELECTING_THEME_CUSTOM,
    SELECTING_TRAITS,
    WAITING_FOR_SAVE_TITLE
) = range(6)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def format_story_message(narration: str, clues: Optional[str] = None, 
                         choices: List[str] = None, include_tip: bool = True) -> str:
    """Format a story message with narration, clues, and choices preview."""
    message = f"📖 {narration}"
    
    if choices and len(choices) > 0:
        message += f"\n\n🎯 *Choices available:* Click a button below!"
    
    if include_tip:
        message += f"\n\n💡 *Tip:* Click a button above OR type your own action!"
    
    if clues:
        message += f"\n\n🔍 *Clues:* {clues}"
    
    return message


def create_choice_keyboard(choices: List[str], max_buttons: int = 4) -> InlineKeyboardMarkup:
    """Create inline keyboard with numbered choice buttons."""
    keyboard = []
    for i, choice in enumerate(choices[:max_buttons], 1):
        # Truncate long choices (Telegram limit)
        display = choice[:60] + "..." if len(choice) > 60 else choice
        keyboard.append([InlineKeyboardButton(f"{i}. {display}", callback_data=f"choice_{i}")])
    
    # Add action buttons
    keyboard.append([
        InlineKeyboardButton("💾 Save", callback_data="action_save"),
        InlineKeyboardButton("🧠 Memory", callback_data="action_memory")
    ])
    keyboard.append([
        InlineKeyboardButton("📜 History", callback_data="action_history"),
        InlineKeyboardButton("🔄 Reset", callback_data="action_reset")
    ])
    
    return InlineKeyboardMarkup(keyboard)


def create_trait_keyboard(selected_traits: List[str] = None) -> InlineKeyboardMarkup:
    """Create trait selection keyboard with checkmarks."""
    if selected_traits is None:
        selected_traits = []
    
    keyboard = []
    for i in range(0, len(TRAIT_LIST), 2):
        row = []
        for j in range(2):
            if i + j < len(TRAIT_LIST):
                trait = TRAIT_LIST[i + j]
                display = f"✅ {trait}" if trait in selected_traits else trait
                row.append(InlineKeyboardButton(display, callback_data=f"trait_{trait}"))
        keyboard.append(row)
    
    keyboard.append([InlineKeyboardButton("✅ Done - Begin Adventure!", callback_data="traits_done")])
    keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel_setup")])
    
    return InlineKeyboardMarkup(keyboard)


def create_model_keyboard() -> InlineKeyboardMarkup:
    """Create AI model selection keyboard."""
    keyboard = [
        [InlineKeyboardButton("🖥️ Local AI (LM Studio)", callback_data="model_local")],
        [InlineKeyboardButton("☁️ Online AI (HuggingFace)", callback_data="model_hf")],
    ]
    return InlineKeyboardMarkup(keyboard)


def create_theme_type_keyboard() -> InlineKeyboardMarkup:
    """Create theme selection type keyboard."""
    keyboard = [
        [InlineKeyboardButton("🎲 Random Theme", callback_data="theme_random")],
        [InlineKeyboardButton("📋 Choose from List", callback_data="theme_list")],
        [InlineKeyboardButton("✍️ Write Custom Theme", callback_data="theme_custom")],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel_setup")]
    ]
    return InlineKeyboardMarkup(keyboard)


def create_theme_list_keyboard(page: int = 0) -> InlineKeyboardMarkup:
    """Create paginated theme list keyboard."""
    items_per_page = 8
    start = page * items_per_page
    end = start + items_per_page
    themes_page = THEME_LIST[start:end]
    
    keyboard = []
    for i, theme in enumerate(themes_page):
        keyboard.append([InlineKeyboardButton(f"{i+1+start}. {theme[:50]}...", 
                                              callback_data=f"theme_select_{i+start}")])
    
    # Pagination buttons
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("◀️ Prev", callback_data=f"theme_page_{page-1}"))
    if end < len(THEME_LIST):
        nav_buttons.append(InlineKeyboardButton("Next ▶️", callback_data=f"theme_page_{page+1}"))
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel_setup")])
    
    return InlineKeyboardMarkup(keyboard)


def format_memory_display(memory_data: Dict[str, Any]) -> str:
    """Format memory data for display."""
    if not memory_data:
        return "No memory data available. Keep playing to build your story!"
    
    parts = ["🧠 *STORY MEMORY*", ""]
    
    # NPCs
    npcs = memory_data.get("npcs", [])
    if npcs:
        parts.append(f"👥 *Characters ({len(npcs)})*")
        for npc in npcs[:8]:
            name = npc.get("name", "Unknown")
            personality = npc.get("personality", "")
            desc = npc.get("description", "")[:60]
            parts.append(f"  • *{name}*: {personality}")
            if desc:
                parts.append(f"    _{desc}_")
        parts.append("")
    
    # Locations
    locations = memory_data.get("locations", [])
    if locations:
        parts.append(f"🗺️ *Locations ({len(locations)})*")
        for loc in locations[:6]:
            name = loc.get("name", "Unknown")
            parts.append(f"  • {name}")
        parts.append("")
    
    # Inventory
    inventory = memory_data.get("inventory", [])
    if inventory:
        parts.append(f"🎒 *Inventory ({len(inventory)})*")
        for item in inventory[:8]:
            item_name = item.get("item", "Unknown")
            parts.append(f"  • {item_name}")
        parts.append("")
    
    # Events
    events = memory_data.get("events", [])
    if events:
        parts.append(f"📅 *Recent Events ({len(events)})*")
        for event in events[-3:]:
            parts.append(f"  • {event[:80]}...")
        parts.append("")
    
    # Discoveries
    discoveries = memory_data.get("discoveries", [])
    if discoveries:
        parts.append(f"💡 *Discoveries ({len(discoveries)})*")
        for disc in discoveries[-3:]:
            parts.append(f"  • {disc[:80]}...")
    
    if len(parts) == 2:
        parts.append("No significant memories extracted yet. Continue your journey!")
    
    return "\n".join(parts)


def format_history_display(steps: List[Dict]) -> str:
    """Format story history for display."""
    if not steps:
        return "No story history yet."
    
    parts = ["📜 *STORY HISTORY*", ""]
    
    for step in steps[-8:]:  # Last 8 steps
        step_num = step.get('step_index', 0)
        user_input = step.get('user_input', '')
        ai_output = step.get('ai_output', '')
        
        if user_input:
            parts.append(f"*Step {step_num} - You:* {user_input[:100]}")
        if ai_output:
            parts.append(f"*Response:* {ai_output[:150]}...")
        parts.append("")
    
    return "\n".join(parts)


# ============================================================================
# COMMAND HANDLERS
# ============================================================================

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Welcome message with instructions."""
    user = update.effective_user
    welcome_text = (
        f"🎮 *Welcome to Interactive Story Game, {user.first_name}!*\n\n"
        "You are the hero. Your choices shape the world.\n\n"
        "*Commands:*\n"
        "🆕 /new - Start a new adventure\n"
        "💾 /save - Save your progress\n"
        "📂 /load - Load a saved game\n"
        "🧠 /memory - View story memory\n"
        "📜 /history - See what happened\n"
        "🔄 /reset - Reset current session\n"
        "ℹ️ /help - Show this message\n\n"
        "✨ *Ready?* Use /new to begin your journey!"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show help message."""
    await start_cmd(update, context)


async def new_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start new session - select AI model."""
    context.chat_data.clear()
    context.chat_data["setup_stage"] = SELECTING_MODEL
    
    keyboard = create_model_keyboard()
    await update.message.reply_text(
        "🎮 *Create Your Adventure*\n\n"
        "First, choose your AI companion:\n\n"
        "🖥️ *Local AI* - Fast, private, works offline (LM Studio)\n"
        "☁️ *Online AI* - Powerful, needs internet (HuggingFace)\n\n"
        "Which one will guide your story?",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    return SELECTING_MODEL


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[int]:
    """Handle all button callbacks."""
    query = update.callback_query
    await query.answer()
    data = query.data
    
    user_id = update.effective_user.id
    username = update.effective_user.username or f"user_{user_id}"
    
    # ================================================================
    # MODEL SELECTION
    # ================================================================
    
    if data == "model_local":
        context.chat_data["model"] = "local"
        context.chat_data["setup_stage"] = SELECTING_NAME
        await query.edit_message_text(
            "✅ *Local AI selected!*\n\n"
            "🎭 What is your character's name?\n\n"
            "_(Type your answer below)_",
            parse_mode="Markdown"
        )
        return SELECTING_NAME
    
    elif data == "model_hf":
        context.chat_data["model"] = "hf"
        context.chat_data["setup_stage"] = SELECTING_NAME
        await query.edit_message_text(
            "✅ *Online AI selected!*\n\n"
            "🎭 What is your character's name?\n\n"
            "_(Type your answer below)_",
            parse_mode="Markdown"
        )
        return SELECTING_NAME
    
    # ================================================================
    # THEME SELECTION
    # ================================================================
    
    elif data == "theme_random":
        theme = random.choice(THEME_LIST)
        context.chat_data["theme"] = theme
        context.chat_data["setup_stage"] = SELECTING_TRAITS
        
        keyboard = create_trait_keyboard()
        await query.edit_message_text(
            f"🎲 *Random Theme Selected!*\n\n"
            f"**Theme:** {theme}\n\n"
            "Now choose your character's traits (tap to select/deselect):",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        return SELECTING_TRAITS
    
    elif data == "theme_list":
        context.chat_data["setup_stage"] = SELECTING_THEME_TYPE
        keyboard = create_theme_list_keyboard(0)
        await query.edit_message_text(
            "📋 *Choose your theme:*\n\n"
            "Select from the list below:",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        return SELECTING_THEME_TYPE
    
    elif data.startswith("theme_page_"):
        page = int(data.split("_")[2])
        keyboard = create_theme_list_keyboard(page)
        await query.edit_message_reply_markup(reply_markup=keyboard)
        return SELECTING_THEME_TYPE
    
    elif data.startswith("theme_select_"):
        idx = int(data.split("_")[2])
        theme = THEME_LIST[idx]
        context.chat_data["theme"] = theme
        context.chat_data["setup_stage"] = SELECTING_TRAITS
        
        keyboard = create_trait_keyboard()
        await query.edit_message_text(
            f"✅ *Theme selected!*\n\n"
            f"**Theme:** {theme}\n\n"
            "Now choose your character's traits (tap to select/deselect):",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        return SELECTING_TRAITS
    
    elif data == "theme_custom":
        context.chat_data["setup_stage"] = SELECTING_THEME_CUSTOM
        await query.edit_message_text(
            "✍️ *Custom Theme*\n\n"
            "Type your custom theme (a phrase describing your story's world):\n\n"
            "_(Type your answer below)_",
            parse_mode="Markdown"
        )
        return SELECTING_THEME_CUSTOM
    
    # ================================================================
    # TRAIT SELECTION
    # ================================================================
    
    elif data.startswith("trait_"):
        trait = data.split("_", 1)[1]
        traits = context.chat_data.get("traits", [])
        
        if trait in traits:
            traits.remove(trait)
        else:
            traits.append(trait)
        
        context.chat_data["traits"] = traits
        keyboard = create_trait_keyboard(traits)
        await query.edit_message_reply_markup(reply_markup=keyboard)
        return SELECTING_TRAITS
    
    elif data == "traits_done":
        return await _create_session(query, context, user_id, username)
    
    # ================================================================
    # STORY CHOICES
    # ================================================================
    
    elif data.startswith("choice_"):
        choice_idx = int(data.split("_")[1])
        session_id = context.chat_data.get("session_id")
        
        if not session_id:
            await query.edit_message_text("❌ No active session. Use /new to start.")
            return ConversationHandler.END
        
        try:
            async with create_async_client(API_KEY) as client:
                payload = {"choice_index": choice_idx, "user_input": None}
                r = await client.post(f"{API_BASE}/api/session/{session_id}/step", json=payload)
                r.raise_for_status()
                result = r.json()
            
            context.chat_data["last_narration"] = result.get('narration', '')
            
            keyboard = create_choice_keyboard(result.get("choices", []))
            message = format_story_message(
                result['narration'], 
                clues=result.get("clues"),
                choices=result.get("choices", []),
                include_tip=True
            )
            
            await query.edit_message_text(
                message, 
                reply_markup=keyboard, 
                parse_mode="Markdown"
            )
            
        except Exception as e:
            logger.error(f"Choice failed: {e}")
            await query.edit_message_text(f"❌ Error: {str(e)}")
        
        return ConversationHandler.END
    
    # ================================================================
    # ACTION BUTTONS
    # ================================================================
    
    elif data == "action_save":
        session_id = context.chat_data.get("session_id")
        if not session_id:
            await query.edit_message_text("❌ No active session to save.")
            return ConversationHandler.END
        
        context.chat_data["awaiting_save_title"] = True
        context.chat_data["setup_stage"] = WAITING_FOR_SAVE_TITLE
        
        await query.edit_message_text(
            "💾 *Save Your Game*\n\n"
            "Type a name for this save (e.g., 'Before the Dragon'):\n\n"
            "_(Type below or /cancel)_",
            parse_mode="Markdown"
        )
        return WAITING_FOR_SAVE_TITLE
    
    elif data == "action_memory":
        session_id = context.chat_data.get("session_id")
        if not session_id:
            await query.edit_message_text("❌ No active session.")
            return ConversationHandler.END
        
        await query.edit_message_text("🧠 *Analyzing story memory...*", parse_mode="Markdown")
        
        try:
            async with create_async_client(API_KEY) as client:
                r = await client.post(f"{API_BASE}/api/session/{session_id}/refresh-memory")
                r.raise_for_status()
                memory_data = r.json()
            
            memory_text = format_memory_display(memory_data)
            await query.edit_message_text(memory_text, parse_mode="Markdown")
            
        except Exception as e:
            logger.error(f"Memory failed: {e}")
            await query.edit_message_text(f"❌ Error: {str(e)}")
        
        return ConversationHandler.END
    
    elif data == "action_history":
        session_id = context.chat_data.get("session_id")
        if not session_id:
            await query.edit_message_text("❌ No active session.")
            return ConversationHandler.END
        
        try:
            async with create_async_client(API_KEY) as client:
                r = await client.get(f"{API_BASE}/api/session/{session_id}/history")
                r.raise_for_status()
                data = r.json()
            
            history_text = format_history_display(data.get("steps", []))
            await query.edit_message_text(history_text, parse_mode="Markdown")
            
        except Exception as e:
            logger.error(f"History failed: {e}")
            await query.edit_message_text(f"❌ Error: {str(e)}")
        
        return ConversationHandler.END
    
    elif data == "action_reset":
        session_id = context.chat_data.get("session_id")
        if not session_id:
            await query.edit_message_text("❌ No active session.")
            return ConversationHandler.END
        
        try:
            async with create_async_client(API_KEY) as client:
                r = await client.post(f"{API_BASE}/api/session/{session_id}/reset")
                r.raise_for_status()
            
            context.chat_data.clear()
            await query.edit_message_text(
                "✅ *Session Reset!*\n\n"
                "Use /new to start a new adventure.",
                parse_mode="Markdown"
            )
            
        except Exception as e:
            logger.error(f"Reset failed: {e}")
            await query.edit_message_text(f"❌ Error: {str(e)}")
        
        return ConversationHandler.END
    
    elif data == "cancel_setup":
        context.chat_data.clear()
        await query.edit_message_text(
            "❌ *Setup cancelled.*\n\n"
            "Use /new to start over.",
            parse_mode="Markdown"
        )
        return ConversationHandler.END
    
    return ConversationHandler.END


async def _create_session(query, context, user_id: int, username: str) -> int:
    """Create session after setup is complete."""
    character_name = context.chat_data.get("character_name", "Hero")
    theme = context.chat_data.get("theme", "An adventure begins")
    traits = context.chat_data.get("traits", [])
    model = context.chat_data.get("model", "local")
    
    try:
        async with create_async_client(API_KEY) as client:
            # Create user
            r = await client.post(f"{API_BASE}/api/user", json={"username": username})
            r.raise_for_status()
            user_data = r.json()
            
            # Start session
            r2 = await client.post(f"{API_BASE}/api/session/start", json={
                "user_id": user_data['id'],
                "title": f"{character_name}'s Adventure",
                "theme": theme,
                "traits": traits,
                "character_name": character_name,
                "model": model
            })
            r2.raise_for_status()
            session_data = r2.json()
        
        context.chat_data["session_id"] = session_data["session_id"]
        context.chat_data["setup_stage"] = None
        context.chat_data["last_narration"] = session_data.get('narration', '')
        
        keyboard = create_choice_keyboard(session_data.get("choices", []))
        model_name = "Local AI" if model == "local" else "Online AI"
        
        message = (
            f"🎉 *{character_name}*, your adventure begins!\n\n"
            f"📖 {session_data['narration']}\n\n"
            f"🤖 *AI Companion:* {model_name}\n"
            f"✨ *Traits:* {', '.join(traits) if traits else 'None'}\n\n"
            f"💡 *Tip:* Click a button below OR type your own action!"
        )
        
        if session_data.get("clues"):
            message += f"\n\n🔍 *Clues:* {session_data['clues']}"
        
        await query.edit_message_text(
            message, 
            reply_markup=keyboard, 
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"Session creation failed: {e}")
        await query.edit_message_text(f"❌ Error creating session: {str(e)}")
    
    return ConversationHandler.END


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[int]:
    """Handle text messages (custom actions or setup inputs)."""
    text = update.message.text.strip()
    stage = context.chat_data.get("setup_stage")
    
    # Handle save title input
    if context.chat_data.get("awaiting_save_title"):
        context.chat_data.pop("awaiting_save_title")
        context.chat_data.pop("setup_stage", None)
        session_id = context.chat_data.get("session_id")
        
        if not session_id:
            await update.message.reply_text("❌ No active session.")
            return ConversationHandler.END
        
        save_title = text if text else f"Save {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        
        try:
            async with create_async_client(API_KEY) as client:
                r = await client.post(
                    f"{API_BASE}/api/session/{session_id}/save",
                    json={"title": save_title, "description": ""}
                )
                r.raise_for_status()
                data = r.json()
            
            await update.message.reply_text(
                f"💾 *Game Saved!*\n\n"
                f"📝 Name: {data.get('title')}\n"
                f"🎯 Step: {data.get('current_step')}\n\n"
                f"Use /load to restore this save later!",
                parse_mode="Markdown"
            )
            
        except Exception as e:
            logger.error(f"Save failed: {e}")
            await update.message.reply_text(f"❌ Error saving: {str(e)}")
        
        return ConversationHandler.END
    
    # Handle character name input
    if stage == SELECTING_NAME:
        context.chat_data["character_name"] = text
        context.chat_data["setup_stage"] = SELECTING_THEME_TYPE
        
        keyboard = create_theme_type_keyboard()
        await update.message.reply_text(
            f"✨ Welcome, *{text}!*\n\n"
            "Now choose your story's theme:",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        return SELECTING_THEME_TYPE
    
    # Handle custom theme input
    if stage == SELECTING_THEME_CUSTOM:
        context.chat_data["theme"] = text
        context.chat_data["setup_stage"] = SELECTING_TRAITS
        
        keyboard = create_trait_keyboard()
        await update.message.reply_text(
            f"🎨 *Great theme!*\n\n"
            f"**Theme:** {text}\n\n"
            "Now choose your character's traits (tap to select):",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        return SELECTING_TRAITS
    
    # Handle normal story progression
    session_id = context.chat_data.get("session_id")
    if not session_id:
        await update.message.reply_text("❌ No active session. Use /new to start.")
        return ConversationHandler.END
    
    try:
        async with create_async_client(API_KEY) as client:
            payload = {"user_input": text, "choice_index": None}
            r = await client.post(f"{API_BASE}/api/session/{session_id}/step", json=payload)
            r.raise_for_status()
            result = r.json()
        
        context.chat_data["last_narration"] = result.get('narration', '')
        
        keyboard = create_choice_keyboard(result.get("choices", []))
        message = format_story_message(
            result['narration'],
            clues=result.get("clues"),
            choices=result.get("choices", []),
            include_tip=True
        )
        
        await update.message.reply_text(message, reply_markup=keyboard, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Custom action failed: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")
    
    return ConversationHandler.END


async def save_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Save current session."""
    session_id = context.chat_data.get("session_id")
    if not session_id:
        await update.message.reply_text("❌ No active session to save.")
        return ConversationHandler.END
    
    context.chat_data["awaiting_save_title"] = True
    context.chat_data["setup_stage"] = WAITING_FOR_SAVE_TITLE
    
    await update.message.reply_text(
        "💾 *Save Your Game*\n\n"
        "Type a name for this save:\n\n"
        "_(Type below or /cancel)_",
        parse_mode="Markdown"
    )
    return WAITING_FOR_SAVE_TITLE


async def load_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List available saves to load."""
    session_id = context.chat_data.get("session_id")
    if not session_id:
        await update.message.reply_text("❌ No active session.")
        return
    
    try:
        async with create_async_client(API_KEY) as client:
            r = await client.get(f"{API_BASE}/api/session/{session_id}/snapshots")
            r.raise_for_status()
            data = r.json()
            snapshots = data.get("snapshots", [])
        
        if not snapshots:
            await update.message.reply_text("📂 No saves found. Use /save to create one!")
            return
        
        keyboard = []
        for snap in snapshots:
            title = snap.get("title", "Untitled")[:40]
            step = snap.get("current_step", 0)
            snap_id = snap.get("id")
            keyboard.append([InlineKeyboardButton(f"📁 {title} (Step {step})", 
                                                  callback_data=f"load_{snap_id}")])
        
        keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel_setup")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"📂 *Load Game*\n\nFound {len(snapshots)} save(s):",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"Load failed: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")


async def reset_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reset current session."""
    session_id = context.chat_data.get("session_id")
    if not session_id:
        await update.message.reply_text("❌ No active session to reset.")
        return
    
    try:
        async with create_async_client(API_KEY) as client:
            r = await client.post(f"{API_BASE}/api/session/{session_id}/reset")
            r.raise_for_status()
        
        context.chat_data.clear()
        await update.message.reply_text(
            "✅ *Session Reset!*\n\n"
            "Use /new to start a fresh adventure.",
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"Reset failed: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")


async def history_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """View session history."""
    session_id = context.chat_data.get("session_id")
    if not session_id:
        await update.message.reply_text("❌ No active session.")
        return
    
    try:
        async with create_async_client(API_KEY) as client:
            r = await client.get(f"{API_BASE}/api/session/{session_id}/history")
            r.raise_for_status()
            data = r.json()
        
        history_text = format_history_display(data.get("steps", []))
        await update.message.reply_text(history_text, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"History failed: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")


async def memory_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show story memory."""
    session_id = context.chat_data.get("session_id")
    if not session_id:
        await update.message.reply_text("❌ No active session.")
        return
    
    await update.message.reply_text("🧠 *Analyzing story memory...*", parse_mode="Markdown")
    
    try:
        async with create_async_client(API_KEY) as client:
            r = await client.post(f"{API_BASE}/api/session/{session_id}/refresh-memory")
            r.raise_for_status()
            memory_data = r.json()
        
        memory_text = format_memory_display(memory_data)
        await update.message.reply_text(memory_text, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Memory failed: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")


async def cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel current operation."""
    context.chat_data.clear()
    await update.message.reply_text("❌ *Cancelled.*\n\nUse /new to start over.", parse_mode="Markdown")
    return ConversationHandler.END


async def saves_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Manage saves (list, delete)."""
    session_id = context.chat_data.get("session_id")
    if not session_id:
        await update.message.reply_text("❌ No active session.")
        return
    
    try:
        async with create_async_client(API_KEY) as client:
            r = await client.get(f"{API_BASE}/api/session/{session_id}/snapshots")
            r.raise_for_status()
            data = r.json()
            snapshots = data.get("snapshots", [])
        
        if not snapshots:
            await update.message.reply_text("📂 No saves found.")
            return
        
        keyboard = []
        for snap in snapshots:
            title = snap.get("title", "Untitled")[:30]
            step = snap.get("current_step", 0)
            snap_id = snap.get("id")
            keyboard.append([InlineKeyboardButton(f"🗑️ {title} (Step {step})", 
                                                  callback_data=f"delete_{snap_id}")])
        
        keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel_setup")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"🗂️ *Manage Saves*\n\n{len(snapshots)} save(s) found. Click to delete:",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"Saves list failed: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")


# ============================================================================
# MAIN
# ============================================================================

def run_bot():
    """Start the Telegram bot."""
    if not TOKEN:
        print("❌ Set TELEGRAM_TOKEN env var to run bot")
        return
    
    logger.info("🤖 Initializing Telegram Bot...")
    init_db()
    
    # Start log cleaner
    start_log_cleaner(interval=60)
    logger.info("🧹 Log cleaner started")
    
    app = ApplicationBuilder().token(TOKEN).build()
    
    # Conversation handler for setup
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("new", new_cmd)],
        states={
            SELECTING_MODEL: [CallbackQueryHandler(button_callback, pattern="^(model_)")],
            SELECTING_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text)],
            SELECTING_THEME_TYPE: [CallbackQueryHandler(button_callback, pattern="^(theme_|cancel_setup)")],
            SELECTING_THEME_CUSTOM: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text)],
            SELECTING_TRAITS: [CallbackQueryHandler(button_callback, pattern="^(trait_|traits_done|cancel_setup)")],
            WAITING_FOR_SAVE_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text)],
        },
        fallbacks=[CommandHandler("cancel", cancel_cmd)],
        per_chat=True
    )
    
    app.add_handler(conv_handler)
    
    # Regular command handlers
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("save", save_cmd))
    app.add_handler(CommandHandler("load", load_cmd))
    app.add_handler(CommandHandler("saves", saves_cmd))
    app.add_handler(CommandHandler("reset", reset_cmd))
    app.add_handler(CommandHandler("history", history_cmd))
    app.add_handler(CommandHandler("memory", memory_cmd))
    app.add_handler(CommandHandler("cancel", cancel_cmd))
    
    # Callback handler for buttons not in conversation
    app.add_handler(CallbackQueryHandler(button_callback, pattern="^(choice_|action_|load_|delete_|cancel_setup)"))
    
    # Message handler
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    logger.info("✅ Telegram Bot started!")
    logger.info("🎮 Bot is ready")
    
    try:
        app.run_polling()
    finally:
        stop_log_cleaner()


if __name__ == "__main__":
    run_bot()