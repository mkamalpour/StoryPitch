import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
import httpx
import pytest
from api import main
from db import db
# Exercise the actual callback sources without installing the optional Telegram SDK.
# SDK transport/keyboard containers are small test doubles; HTTP reaches the real API.
import ast
from pathlib import Path
from types import ModuleType
bot = ModuleType("telegram_workflow_under_test")
source = Path(__file__).resolve().parents[1] / "ui" / "telegram_bot.py"
tree = ast.parse(source.read_text(encoding="utf-8"))
names = {"format_story_message", "create_choice_keyboard", "format_memory_display", "button_callback", "handle_text", "memory_cmd"}
functions = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names]
namespace = bot.__dict__
namespace.update(ConversationHandler=SimpleNamespace(END=-1),
                 InlineKeyboardButton=lambda text, **kwargs: SimpleNamespace(text=text, **kwargs),
                 InlineKeyboardMarkup=lambda keyboard: SimpleNamespace(inline_keyboard=keyboard),
                 API_KEY="", API_BASE="http://testserver", create_async_client=None,
                 logger=__import__("logging").getLogger(__name__))
namespace.update(dict(zip(["SELECTING_MODEL", "SELECTING_NAME", "SELECTING_THEME_TYPE", "SELECTING_THEME_CUSTOM", "SELECTING_TRAITS", "WAITING_FOR_SAVE_TITLE"], range(6))))
import __future__
exec(compile(ast.Module(body=functions, type_ignores=[]), str(source), "exec", flags=__future__.annotations.compiler_flag), namespace)


@pytest.fixture
def story_client(monkeypatch):
    def client(*args, **kwargs):
        return httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url="http://testserver")
    monkeypatch.setattr(bot, "create_async_client", client)
    monkeypatch.setattr(bot, "API_BASE", "http://testserver")
    user = db.create_user("synthetic-telegram")
    memory = {"npcs": {"Ada": {"personality": "curious"}}, "locations": {"Library": {}}, "events": [{"description": "A door opened"}], "discoveries": [{"discovery": "A map"}], "inventory": [{"item": "Key"}]}
    session = db.create_session(user.id, "Test", {"last_narration": "The saved door.", "last_choices": ["Enter", "Wait"], "memory": memory})
    return session


def update_for(data=None):
    query = SimpleNamespace(data=data, answer=AsyncMock(), edit_message_text=AsyncMock())
    return SimpleNamespace(callback_query=query, effective_user=SimpleNamespace(id=1, username="synthetic"), message=SimpleNamespace(reply_text=AsyncMock(), text="Investigate"))


def test_telegram_load_button_restores_saved_scene(story_client):
    snapshot = db.create_snapshot(story_client.id)
    db.update_session(story_client.id, world_state={"last_narration": "Different branch"})
    update = update_for(f"load_{snapshot.id}")
    context = SimpleNamespace(chat_data={"session_id": story_client.id})
    asyncio.run(bot.button_callback(update, context))
    assert db.get_session(story_client.id).get_world_state()["last_narration"] == "The saved door."
    assert context.chat_data["last_narration"] == "The saved door."
    assert "The saved door." in update.callback_query.edit_message_text.call_args.args[0]
    assert update.callback_query.edit_message_text.call_args.kwargs["reply_markup"].inline_keyboard


@pytest.mark.parametrize("callback", [False, True])
def test_telegram_memory_views_use_saved_memory(story_client, callback):
    update = update_for("action_memory")
    context = SimpleNamespace(chat_data={"session_id": story_client.id})
    asyncio.run(bot.button_callback(update, context) if callback else bot.memory_cmd(update, context))
    message = update.callback_query.edit_message_text if callback else update.message.reply_text
    text = message.call_args.args[0]
    assert all(value in text for value in ["Ada", "Library", "A door opened", "A map", "Key"])


@pytest.mark.parametrize("callback", [False, True])
def test_telegram_actions_keep_selected_provider(story_client, callback, monkeypatch):
    seen = []
    async def advance(session_id, user_input=None, choice_index=None, model=None):
        seen.append(model)
        return {"narration": "Next scene", "choices": ["Enter", "Wait"], "clues": ""}
    monkeypatch.setattr(main, "advance_session", advance)
    update = update_for("choice_1")
    context = SimpleNamespace(chat_data={"session_id": story_client.id, "model": "hf"})
    asyncio.run(bot.button_callback(update, context) if callback else bot.handle_text(update, context))
    assert seen == ["hf"]
