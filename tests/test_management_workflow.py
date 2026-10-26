import asyncio
import httpx
from db import db, manage
from api.main import app


def test_database_manager_deletes_snapshot_through_actual_api(monkeypatch):
    user = db.create_user("synthetic-manager")
    session = db.create_session(user.id, "Kept story")
    snapshot = db.create_snapshot(session.id, title="Disposable checkpoint")
    def client(*args, **kwargs):
        return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver")
    monkeypatch.setattr(manage, "create_async_client", client)
    manager = manage.DatabaseManager()
    manager.base_url = "http://testserver"
    result = asyncio.run(manager.delete_snapshot(snapshot.id))
    assert result["status"] == "ok"
    assert db.get_snapshot_details(snapshot.id) is None
    assert db.get_session(session.id) is not None
    assert db.get_user(user.id) is not None
