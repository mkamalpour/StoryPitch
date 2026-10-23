import asyncio
import json
import pytest
import httpx
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from db import db
from api import main
from story.parser import parse_ai_output
from story.postprocess import normalize_ai_text_to_story
from llm.manager import LLMManager
import llm.manager as models


@pytest.fixture
def client():
    with TestClient(main.app) as connection:
        yield connection


def start(client):
    user = client.post("/api/user", json={"username": "Reader"}).json()
    response = client.post(
        "/api/session/start",
        json={
            "user_id": user["id"],
            "title": "Test story",
            "theme": "A hidden library",
            "character_name": "Alex",
            "model": "fallback",
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["choices"]
    return response.json()["session_id"]


def test_story_save_branch_restore_and_export(client):
    sid = start(client)

    def advance(action):
        response = client.post(
            f"/api/session/{sid}/step", json={"user_input": action, "model": "fallback"}
        )
        assert response.status_code == 200, response.text

    advance("Investigate the library")
    save_a = client.post(
        f"/api/session/{sid}/save", json={"title": "First path"}
    ).json()["snapshot_id"]
    advance("Open the silver door")
    save_b = client.post(
        f"/api/session/{sid}/save", json={"title": "Silver path"}
    ).json()["snapshot_id"]
    assert client.post(f"/api/session/{sid}/load/{save_a}").status_code == 200
    advance("Open the wooden door")
    assert client.post(f"/api/session/{sid}/load/{save_b}").status_code == 200
    history = client.get(f"/api/session/{sid}/history").json()["steps"]
    assert len(history) == 3
    assert history[-1]["user_input"] == "Open the silver door"
    response = client.post(
        f"/api/session/{sid}/step", json={"choice_index": 1, "model": "fallback"}
    )
    assert response.status_code == 200, response.text
    assert (
        client.get(f"/api/session/{sid}/export").json()["session"]["current_step"] == 4
    )
    assert "Test story" in client.get(f"/api/session/{sid}/export?fmt=text").text
    assert client.get(f"/api/session/{sid}/export?fmt=bad").status_code == 422


def test_checkpoint_cannot_cross_sessions(client):
    first, second = start(client), start(client)
    snapshot = client.post(f"/api/session/{first}/save", json={}).json()["snapshot_id"]
    assert client.post(f"/api/session/{second}/load/{snapshot}").status_code == 404
    assert db.get_session(second).current_step == 1


def test_user_deletion_cleans_children(client):
    sid = start(client)
    client.post(f"/api/session/{sid}/save", json={})
    uid = db.get_session(sid).user_id
    assert client.delete(f"/api/admin/user/{uid}").status_code == 200
    with Session(db.engine) as connection:
        for model in (db.User, db.SessionModel, db.Step, db.Snapshot):
            assert not connection.exec(select(model)).all()


def test_atomic_scene_write_rejects_stale_generation(client):
    sid = start(client)
    before = db.get_session(sid).world_state
    with pytest.raises(ValueError):
        db.commit_story_step(sid, 1, {"bad": True}, "prompt", "output")
    assert db.get_session(sid).world_state == before
    assert len(db.get_steps(sid)) == 1


def test_validation_missing_resources_and_origin(client):
    assert client.post("/api/user", json={"username": "  "}).status_code == 422
    assert client.post("/api/session/start", json={"user_id": 999}).status_code == 404
    assert client.get("/api/session/999/history").status_code == 404
    sid = start(client)
    for payload in (
        {},
        {"choice_index": 0},
        {"model": "invalid"},
        {"choice_index": 1, "user_input": "act"},
    ):
        assert client.post(f"/api/session/{sid}/step", json=payload).status_code == 422
    assert (
        client.post(
            "/api/admin/clear-all", headers={"Origin": "https://untrusted.example"}
        ).status_code
        == 403
    )
    assert db.get_session(sid)


def test_key_protects_admin_and_story(client, monkeypatch):
    import api.auth

    monkeypatch.setattr(api.auth, "API_KEY", "test-key")
    assert client.get("/api/health").status_code == 200
    for path in ("/api/admin/users", "/api/admin/sessions", "/api/session/1/state"):
        assert client.get(path).status_code == 401
    assert (
        client.get("/api/admin/users", headers={"X-API-Key": "test-key"}).status_code
        == 200
    )


def test_concurrent_generation_blocks_mutations(client, monkeypatch):
    sid = start(client)

    async def scenario():
        entered, release = asyncio.Event(), asyncio.Event()

        async def slow(*args, **kwargs):
            entered.set()
            await release.wait()
            return {"step_index": 2}

        monkeypatch.setattr(main, "advance_session", slow)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=main.app), base_url="http://testserver"
        ) as connection:
            pending = asyncio.create_task(
                connection.post(f"/api/session/{sid}/step", json={"choice_index": 1})
            )
            await entered.wait()
            try:
                for method, path, payload in [
                    ("POST", f"/api/session/{sid}/reset", None),
                    ("POST", f"/api/session/{sid}/save", {}),
                    ("DELETE", f"/api/admin/session/{sid}", None),
                    ("POST", "/api/admin/clear-all", None),
                ]:
                    assert (
                        await connection.request(method, path, json=payload)
                    ).status_code == 409
            finally:
                release.set()
                assert (await pending).status_code == 200
            assert not main._session_processing

    asyncio.run(scenario())


def test_offline_hf_and_demo_never_contact_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("No network expected")

    monkeypatch.setattr(models.httpx, "AsyncClient", forbidden)
    monkeypatch.setattr(models, "OFFLINE_MODE", True)
    for provider in ("hf", "fallback"):
        result = asyncio.run(LLMManager().generate("Begin the story", model=provider))
        assert parse_ai_output(result)["choices"]


def test_local_model_failure_returns_demo(monkeypatch):
    async def unavailable(*args, **kwargs):
        raise httpx.ConnectError("Unavailable")

    monkeypatch.setattr(LLMManager, "_local", unavailable)
    assert parse_ai_output(
        asyncio.run(LLMManager().generate("A story", model="local"))
    )["narration"]


def test_local_model_normalizes_v1_and_parses_chat(monkeypatch):
    urls = []

    def handle(request):
        urls.append(str(request.url))
        if request.method == "GET":
            return httpx.Response(200, json={"data": [{"id": "test-model"}]})
        assert json.loads(request.content)["model"] == "test-model"
        return httpx.Response(
            200, json={"choices": [{"message": {"content": "A model response"}}]}
        )

    original = httpx.AsyncClient
    monkeypatch.setattr(models, "LM_STUDIO_URL", "http://model.test/v1")
    monkeypatch.setattr(models, "LM_STUDIO_MODEL", "")
    monkeypatch.setattr(
        models.httpx,
        "AsyncClient",
        lambda **kwargs: original(transport=httpx.MockTransport(handle), **kwargs),
    )
    assert (
        asyncio.run(LLMManager().generate("Unique model prompt", model="local"))
        == "A model response"
    )
    assert urls == [
        "http://model.test/v1/models",
        "http://model.test/v1/chat/completions",
    ]


@pytest.mark.parametrize("wrapped", [False, True])
def test_parser_preserves_structured_story_and_memory(wrapped):
    data = {
        "narration": "You meet Sarah.",
        "choices": ["Listen", "Leave"],
        "clues": "An old key",
        "memory": {"npcs": ["Sarah"]},
    }
    raw = json.dumps(data)
    if wrapped:
        raw = "```json\n" + raw + "\n```"
    parsed = normalize_ai_text_to_story(raw, max_choices=4)
    assert parsed["narration"] == data["narration"]
    assert parsed["choices"][:2] == data["choices"]
    assert parsed["memory"]["npcs"] == ["Sarah"]


def test_ui_response_cannot_break_runtime_script(client, monkeypatch):
    monkeypatch.setattr(main, "API_KEY", "</script><script>alert(1)</script>")
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert "</script><script>alert(1)</script>" not in response.text


def test_legacy_checkpoint_choices_work_without_deleted_scene(client):
    sid = start(client)
    with Session(db.engine) as connection:
        for row in connection.exec(
            select(db.Step).where(db.Step.session_id == sid)
        ).all():
            connection.delete(row)
        connection.commit()
    response = client.post(
        f"/api/session/{sid}/step", json={"choice_index": 1, "model": "fallback"}
    )
    assert response.status_code == 200, response.text
    assert db.get_session(sid).current_step == 2


def test_story_creation_blocks_destructive_operations(client, monkeypatch):
    sid = start(client)
    monkeypatch.setattr(main, "_pending_starts", 1)
    assert client.post("/api/admin/clear-all").status_code == 409
    assert client.delete(f"/api/admin/session/{sid}").status_code == 409
    assert client.post(f"/api/session/{sid}/reset").status_code == 409
    assert client.get(f"/api/session/{sid}/state").status_code == 200
    assert db.get_session(sid).current_step == 1


def test_demo_summary_and_memory_match_mode(client):
    sid = start(client)
    scene = "A key opens the door. Alex enters the library. A shadow follows."
    response = client.post(
        f"/api/session/{sid}/summarize", json={"text": scene, "model": "fallback"}
    )
    assert response.status_code == 200
    assert (
        response.json()["summary"] == "A key opens the door. Alex enters the library."
    )
    memory = client.post(
        f"/api/session/{sid}/refresh-memory", json={"model": "fallback"}
    )
    assert memory.status_code == 200
    assert "Demo mode" in memory.json()["summary"]


def test_database_additive_migration_preserves_legacy_checkpoint(isolated_database):
    from sqlalchemy import inspect, text

    with isolated_database.begin() as connection:
        connection.execute(text("DROP TABLE snapshot"))
        connection.execute(
            text("""CREATE TABLE snapshot (
            id INTEGER PRIMARY KEY, session_id INTEGER NOT NULL, created_at DATETIME NOT NULL,
            title VARCHAR NOT NULL, description VARCHAR NOT NULL, world_state VARCHAR NOT NULL,
            current_step INTEGER NOT NULL)""")
        )
        connection.execute(
            text("""INSERT INTO snapshot VALUES
            (1, 7, '2026-01-01 00:00:00', 'Legacy save', '', '{}', 3)""")
        )
    db.init_db()
    db.init_db()
    assert "history" in {
        row["name"] for row in inspect(isolated_database).get_columns("snapshot")
    }
    snapshot = db.get_snapshot_details(1)
    assert snapshot.title == "Legacy save"
    assert snapshot.current_step == 3
    assert snapshot.history == "[]"


def test_untrusted_host_is_rejected(client):
    assert client.get("/", headers={"Host": "untrusted.example"}).status_code == 400


def test_journal_renders_narration_instead_of_raw_model_json(client):
    sid = start(client)
    raw = json.dumps(
        {"narration": "A silver door opens.", "choices": ["Enter", "Wait"]}
    )
    db.commit_story_step(
        sid, 2, db.get_session(sid).get_world_state(), "prompt", raw, "Open door"
    )
    data = client.get(f"/api/session/{sid}/story-full").json()
    assert data["steps"][-1]["narration"] == "A silver door opens."
    text = client.get(f"/api/session/{sid}/export?fmt=text").text
    assert "A silver door opens." in text
    assert raw not in text


def test_hosted_chat_uses_router_only_when_explicitly_enabled(monkeypatch):
    def handle(request):
        assert str(request.url) == "https://router.huggingface.co/v1/chat/completions"
        assert request.headers["Authorization"] == "Bearer mocked-key"
        payload = json.loads(request.content)
        assert payload["model"] == "test/chat-model"
        assert payload["messages"] == [
            {"role": "user", "content": "Hosted test prompt"}
        ]
        return httpx.Response(
            200, json={"choices": [{"message": {"content": "Hosted response"}}]}
        )

    original = httpx.AsyncClient
    monkeypatch.setattr(models, "OFFLINE_MODE", False)
    monkeypatch.setattr(models, "HF_API_KEY", "mocked-key")
    monkeypatch.setattr(models, "HF_MODEL", "test/chat-model")
    monkeypatch.setattr(
        models.httpx,
        "AsyncClient",
        lambda **kwargs: original(transport=httpx.MockTransport(handle), **kwargs),
    )
    assert (
        asyncio.run(LLMManager().generate("Hosted test prompt", model="hf"))
        == "Hosted response"
    )


def test_unsupported_local_chat_route_uses_completion_route(monkeypatch):
    paths = []

    def handle(request):
        paths.append(request.url.path)
        if request.url.path.endswith("chat/completions"):
            return httpx.Response(404)
        assert json.loads(request.content)["prompt"] == "Completion fallback test"
        return httpx.Response(200, json={"choices": [{"text": "Completion response"}]})

    original = httpx.AsyncClient
    monkeypatch.setattr(models, "LM_STUDIO_URL", "http://model.test")
    monkeypatch.setattr(models, "LM_STUDIO_MODEL", "test-model")
    monkeypatch.setattr(models, "LM_STUDIO_USE_CHAT", True)
    monkeypatch.setattr(
        models.httpx,
        "AsyncClient",
        lambda **kwargs: original(transport=httpx.MockTransport(handle), **kwargs),
    )
    assert (
        asyncio.run(LLMManager().generate("Completion fallback test", model="local"))
        == "Completion response"
    )
    assert paths == ["/v1/chat/completions", "/v1/completions"]


def test_naive_datetime_fields_have_explicit_sql_mapping():
    from datetime import datetime, timezone
    from sqlalchemy import DateTime
    from pydantic import ValidationError
    from db.db import User
    assert isinstance(User.__table__.c.created_at.type, DateTime)
    with pytest.raises(ValidationError):
        User.model_validate({"username": "Reader", "created_at": datetime.now(timezone.utc)})
