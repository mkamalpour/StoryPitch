import asyncio
import pytest
from db import db
from story import logic


def test_failed_initial_generation_leaves_no_empty_story(monkeypatch):
    user = db.create_user("synthetic-player")
    async def unavailable(*args, **kwargs):
        raise RuntimeError("Synthetic unavailable provider")
    monkeypatch.setattr(logic, "generate", unavailable)
    with pytest.raises(ValueError, match="Failed to start session"):
        asyncio.run(logic.start_session(user.id, "Failed story"))
    assert db.get_all_sessions() == []
    assert db.get_user(user.id) is not None


def test_successful_initial_generation_is_still_saved(monkeypatch):
    user = db.create_user("synthetic-player")
    async def generate(*args, **kwargs):
        return "Narration: A door opens.\nChoices:\n1) Enter\n2) Wait\n3) Leave"
    monkeypatch.setattr(logic, "generate", generate)
    result = asyncio.run(logic.start_session(user.id, "New story"))
    assert db.get_session(result["session_id"]).current_step == 1
    assert len(db.get_steps(result["session_id"])) == 1


def test_failed_new_story_preserves_existing_player_work(monkeypatch):
    user = db.create_user("existing-player")
    existing = db.create_session(user.id, "Existing story", {"last_narration": "Keep this scene"})
    db.commit_story_step(existing.id, 1, {"last_narration": "Keep this scene"}, "Existing prompt", "Existing output")
    saved = db.create_snapshot(existing.id, title="Keep this checkpoint")
    async def unavailable(*args, **kwargs):
        raise RuntimeError("Synthetic unavailable provider")
    monkeypatch.setattr(logic, "generate", unavailable)
    with pytest.raises(ValueError):
        asyncio.run(logic.start_session(user.id, "Failed new story"))
    assert [row.id for row in db.get_all_sessions()] == [existing.id]
    assert db.get_session(existing.id).get_world_state()["last_narration"] == "Keep this scene"
    assert db.get_steps(existing.id)[0].ai_output == "Existing output"
    assert db.get_snapshot_details(saved.id).title == "Keep this checkpoint"
