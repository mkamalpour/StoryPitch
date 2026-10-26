# api/main.py
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from story.parser import parse_ai_output
from pathlib import Path
from contextlib import asynccontextmanager
from urllib.parse import urlsplit
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict
from api.auth import api_key_required
from db.db import (
    init_db,
    create_user,
    create_session,
    get_session,
    reset_session,
    get_steps,
    create_snapshot,
    load_snapshot,
    get_user,
    get_all_users,
    get_all_sessions,
    delete_user,
    delete_session,
    delete_snapshot,
    get_all_snapshots,
    get_session_snapshots,
    get_snapshot_details,
    rename_snapshot,
    update_snapshot_description,
    Session,
    select,
    User,
    SessionModel,
    Step,
    Snapshot,
    engine,
)
from story.logic import start_session, advance_session
from story.memory_analyzer import analyze_and_refresh_memory  # NEW: Memory analysis
from utils.http_client import create_async_client
import logging
from config import API_HOST, API_PORT, API_KEY, configure_logging, LM_STUDIO_URL
from constants import LOG_SEPARATOR
import time
import json

logger = logging.getLogger(__name__)


async def log_request(request: Request):
    logger.debug("Request %s %s", request.method, request.url.path)


@asynccontextmanager
async def lifespan(app):
    configure_logging()
    init_db()
    yield


app = FastAPI(
    title="StoryPitch",
    description="Interactive stories with local AI and branching checkpoints.",
    version="1.1.0",
    lifespan=lifespan,
)
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=list({"127.0.0.1", "localhost", "::1", "testserver", API_HOST}),
)
_session_processing: dict[int, bool] = {}
_pending_starts = 0
_UI_DIR = Path(__file__).resolve().parents[1] / "ui"
if (_UI_DIR / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=_UI_DIR / "assets"), name="assets")


@app.middleware("http")
async def protect_requests(request: Request, call_next):
    path = request.url.path
    if path.startswith("/api/") and path != "/api/health":
        try:
            api_key_required(request.headers.get("x-api-key"))
        except HTTPException as exc:
            return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
    mutating = request.method in {"POST", "PUT", "PATCH", "DELETE"}
    origin = request.headers.get("origin")
    if mutating and origin and urlsplit(origin).netloc != request.url.netloc:
        return JSONResponse(
            {"detail": "Cross-origin writes are disabled"}, status_code=403
        )
    parts = path.strip("/").split("/")
    session_ids = []
    if len(parts) > 2 and parts[:2] == ["api", "session"] and parts[2].isdigit():
        session_id = int(parts[2])
        if not get_session(session_id):
            return JSONResponse({"detail": "Session not found"}, status_code=404)
        session_ids.append(session_id)
    if mutating:
        if _pending_starts and (session_ids or path.startswith("/api/admin/")):
            return JSONResponse(
                {"detail": "A story is being created. Please wait."}, status_code=409
            )
        if len(parts) > 2 and parts[:2] == ["api", "snapshot"] and parts[2].isdigit():
            snapshot = get_snapshot_details(int(parts[2]))
            if snapshot:
                session_ids.append(snapshot.session_id)
        if (
            parts[:3] == ["api", "admin", "session"]
            and len(parts) > 3
            and parts[3].isdigit()
        ):
            session_ids.append(int(parts[3]))
        if (
            parts[:3] == ["api", "admin", "user"]
            and len(parts) > 3
            and parts[3].isdigit()
        ):
            session_ids.extend(
                row.id for row in get_all_sessions() if row.user_id == int(parts[3])
            )
        if path == "/api/admin/clear-all":
            session_ids.extend(_session_processing)
        if any(_session_processing.get(value) for value in session_ids):
            return JSONResponse(
                {"detail": "Story is busy. Wait for the current operation to finish."},
                status_code=409,
            )
        for value in session_ids:
            _session_processing[value] = True
    try:
        return await call_next(request)
    finally:
        if mutating:
            for value in session_ids:
                _session_processing.pop(value, None)


class InputModel(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)


# Request models
class UserCreate(InputModel):
    username: str = Field(min_length=1, max_length=100)


class SessionStart(InputModel):
    user_id: int = Field(gt=0)
    title: str = Field(default="Untitled", min_length=1, max_length=200)
    theme: str | None = Field(default=None, max_length=2000)
    traits: list[str] | None = Field(default=None, max_length=20)
    character_name: str | None = Field(default=None, max_length=100)
    model: Literal["local", "hf", "fallback"] | None = None  # 'local' or 'hf'


class StepRequest(InputModel):
    user_input: str | None = Field(default=None, max_length=4000)
    choice_index: int | None = Field(default=None, ge=1, le=20)
    model: Literal["local", "hf", "fallback"] | None = None


class SaveRequest(InputModel):
    title: str = Field(default="Quick Save", min_length=1, max_length=200)
    description: str = Field(default="", max_length=4000)


class RenameSnapshotRequest(InputModel):
    new_title: str = Field(min_length=1, max_length=200)


class UpdateDescriptionRequest(InputModel):
    new_description: str = Field(max_length=4000)


# endpoints
@app.post(
    "/api/user",
)
async def api_create_user(req: UserCreate, request: Request):
    await log_request(request)
    logger.info("📝 Creating new user: %s", req.username)
    try:
        user = create_user(req.username)
        logger.info("✅ User created - ID: %d, Username: %s", user.id, user.username)
        return {"id": user.id, "username": user.username}
    except Exception as e:
        logger.error("❌ Failed to create user: %s", str(e))
        logger.exception("Full error details:")
        raise HTTPException(status_code=500, detail=f"Failed to create user: {str(e)}")


@app.post(
    "/api/session/start",
)
async def api_start_session(req: SessionStart, request: Request):
    await log_request(request)
    logger.info("🎬 API: Starting new session for user %d", req.user_id)
    logger.info("   Title: %s", req.title)
    logger.info("   Theme: %s", req.theme or "default")
    logger.info("   Character: %s", req.character_name or "default")
    logger.info("   Traits: %s", req.traits or [])
    logger.info("   Model: %s", req.model or "default")

    global _pending_starts
    if not get_user(req.user_id):
        raise HTTPException(status_code=404, detail="User not found")
    _pending_starts += 1
    try:
        out = await start_session(
            req.user_id,
            req.title,
            theme=req.theme,
            traits=req.traits,
            character_name=req.character_name,
            model=req.model,
        )

        logger.info(
            "✅ API: Session started successfully - ID: %d", out.get("session_id")
        )
        return out
    except Exception as e:
        logger.error("❌ API: Failed to start session for user %d", req.user_id)
        logger.exception("Full error details:")
        raise HTTPException(
            status_code=500, detail=f"Failed to start session: {str(e)}"
        )
    finally:
        _pending_starts -= 1


@app.get(
    "/api/session/{session_id}/state",
)
async def api_get_state(session_id: int):
    s = get_session(session_id)
    if not s:
        raise HTTPException(status_code=404, detail="session not found")
    return {
        "session_id": s.id,
        "user_id": s.user_id,
        "title": s.title,
        "current_step": s.current_step,
        "world_state": s.get_world_state(),
        "is_processing": _session_processing.get(session_id, False),
    }


@app.get(
    "/api/session/{session_id}/processing",
)
async def api_check_processing(session_id: int):
    """Check if a session is currently processing a request"""
    return {
        "session_id": session_id,
        "is_processing": _session_processing.get(session_id, False),
    }


@app.post("/api/session/{session_id}/step")
async def api_step(session_id: int, req: StepRequest, request: Request):
    if bool(req.user_input) == (req.choice_index is not None):
        raise HTTPException(
            status_code=422, detail="Provide one choice or one custom action"
        )
    try:
        return await advance_session(
            session_id,
            user_input=req.user_input,
            choice_index=req.choice_index,
            model=req.model,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post(
    "/api/session/{session_id}/reset",
)
async def api_reset(session_id: int):
    s = reset_session(session_id)
    if not s:
        raise HTTPException(status_code=404, detail="session not found")
    return {"status": "ok", "session_id": s.id}


@app.post(
    "/api/session/{session_id}/save",
)
async def api_save(session_id: int, req: SaveRequest, request: Request):
    """
    💾 Create a game save snapshot.
    Like saving your game in a specific slot with a custom name.

    Args:
        session_id: The session to save
        req: Save details (title and optional description)

    Returns:
        Snapshot details including ID, title, description, step number, and timestamp
    """
    await log_request(request)
    logger.info("💾 Creating save: session=%d title='%s'", session_id, req.title)

    try:
        snap = create_snapshot(session_id, title=req.title, description=req.description)
        if not snap:
            raise HTTPException(status_code=404, detail="session not found")

        logger.info(
            "✅ Save created: snapshot_id=%d step=%d", snap.id, snap.current_step
        )
        return {
            "status": "ok",
            "snapshot_id": snap.id,
            "session_id": session_id,
            "title": snap.title,
            "description": snap.description,
            "current_step": snap.current_step,
            "created_at": str(snap.created_at),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("❌ Failed to create save: %s", str(e))
        logger.exception("Full error details:")
        raise HTTPException(status_code=500, detail=f"Failed to create save: {str(e)}")


@app.post(
    "/api/session/{session_id}/load",
)
async def api_load(session_id: int, request: Request):
    await log_request(request)
    s = load_snapshot(session_id, snapshot_id=None)
    if not s:
        raise HTTPException(status_code=404, detail="no snapshot or session not found")
    return {
        "status": "ok",
        "session_id": s.id,
        "current_step": s.current_step,
        "world_state": s.get_world_state(),
    }


@app.get(
    "/api/session/{session_id}/history",
)
async def api_history(session_id: int):
    steps = get_steps(session_id)
    return {
        "steps": [
            {
                "step_index": st.step_index,
                "prompt": st.prompt,
                "ai_output": st.ai_output,
                "user_input": st.user_input,
                "created_at": str(st.created_at),
            }
            for st in steps
        ]
    }


@app.post("/api/session/{session_id}/refresh-memory")
async def api_refresh_memory(session_id: int, req: StepRequest, request: Request):
    return await analyze_and_refresh_memory(session_id, model=req.model)


@app.get("/api/health")
async def api_health():
    return {"status": "ok"}


@app.get("/api/performance")
async def api_performance():
    """Get performance statistics and cache info"""
    try:
        from utils.performance import get_performance_stats, get_cache_stats

        stats = get_performance_stats()
        return {"status": "ok", "performance": stats}
    except Exception as e:
        logger.error(f"Failed to get performance stats: {e}")
        return {"status": "error", "error": str(e)}


@app.get("/api/admin/ping-lmstudio")
async def api_ping_lmstudio():
    logger.info("🔍 API: Pinging LM Studio...")
    if not LM_STUDIO_URL:
        logger.warning("⚠️  LM_STUDIO_URL not configured")
        return {"ok": False, "error": "LM_STUDIO_URL not configured"}
    base = LM_STUDIO_URL.rstrip("/")
    endpoints = ["/v1/models", "/v1/health", "/health"]
    results = {}
    logger.info("Testing endpoints: %s", endpoints)
    async with create_async_client(timeout=5) as client:
        for ep in endpoints:
            url = f"{base}{ep}"
            try:
                logger.info("   Testing: %s", url)
                r = await client.get(url)
                results[ep] = {"status": r.status_code, "ok": r.status_code == 200}
                logger.info("   ✅ %s: Status %d", ep, r.status_code)
            except Exception as e:
                results[ep] = {"ok": False, "error": str(e)}
                logger.error("   ❌ %s: %s", ep, str(e))
    logger.info("✅ LM Studio ping complete")
    return {"base": base, "checks": results}


# Basic timing/logging middleware for full request flow visibility
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    response = None
    try:
        response = await call_next(request)
        return response
    finally:
        duration_ms = int((time.time() - start) * 1000)
        status = response.status_code if response is not None else "?"
        logger.info(
            "HTTP %s %s -> %s in %dms",
            request.method,
            request.url.path,
            status,
            duration_ms,
        )


@app.get("/", response_class=HTMLResponse)
@app.get("/index.html", response_class=HTMLResponse, include_in_schema=False)
async def root(request: Request):
    # Only the local operator receives the configured key automatically.
    local = request.client and request.client.host in {"127.0.0.1", "::1", "testclient"}
    runtime = json.dumps(
        {
            "apiBase": str(request.base_url).rstrip("/"),
            "apiKey": API_KEY if local else "",
        }
    )
    runtime = (
        runtime.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    )
    html = (_UI_DIR / "index.html").read_text(encoding="utf-8")
    return HTMLResponse(
        html.replace("__STORYPITCH_RUNTIME_CONFIG__", runtime),
        headers={
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
            "X-Frame-Options": "DENY",
        },
    )


@app.get("/api/admin/users")
async def api_get_all_users():
    users = get_all_users()
    return {
        "users": [
            {"id": u.id, "username": u.username, "created_at": str(u.created_at)}
            for u in users
        ]
    }


@app.get("/api/admin/sessions")
async def api_get_all_sessions():
    sessions = get_all_sessions()
    return {
        "sessions": [
            {
                "id": s.id,
                "user_id": s.user_id,
                "title": s.title,
                "current_step": s.current_step,
                "created_at": str(s.created_at),
            }
            for s in sessions
        ]
    }


@app.get("/api/admin/snapshots")
async def api_get_all_snapshots():
    try:
        logger.debug("Fetching all snapshots")
        snapshots = get_all_snapshots()
        logger.debug(f"Found {len(snapshots)} snapshots")
        return {
            "snapshots": [
                {
                    "id": s.id,
                    "session_id": s.session_id,
                    "title": s.title,
                    "created_at": str(s.created_at),
                }
                for s in snapshots
            ]
        }
    except Exception as e:
        logger.error(f"Error fetching snapshots: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Error fetching snapshots: {str(e)}"
        )


@app.delete("/api/admin/user/{user_id}")
async def api_delete_user(user_id: int):
    success = delete_user(user_id)
    if not success:
        raise HTTPException(status_code=404, detail="user not found")
    return {"status": "ok", "message": f"User {user_id} deleted"}


@app.delete("/api/admin/session/{session_id}")
async def api_delete_session(session_id: int):
    success = delete_session(session_id)
    if not success:
        raise HTTPException(status_code=404, detail="session not found")
    return {"status": "ok", "message": f"Session {session_id} deleted"}


@app.post("/api/admin/clear-all")
async def api_clear_all():
    """Clear all data - use with caution!"""
    with Session(engine) as s:
        logger.warning("ADMIN clear-all requested")
        snaps = s.exec(select(Snapshot)).all()
        steps = s.exec(select(Step)).all()
        sessions = s.exec(select(SessionModel)).all()
        users = s.exec(select(User)).all()
        for snap in snaps:
            s.delete(snap)
        for step in steps:
            s.delete(step)
        for session in sessions:
            s.delete(session)
        for user in users:
            s.delete(user)
        s.commit()
        logger.info(
            "ADMIN clear-all deleted: snapshots=%s steps=%s sessions=%s users=%s",
            len(snaps),
            len(steps),
            len(sessions),
            len(users),
        )

    return {"status": "ok", "message": "All data cleared"}


@app.get(
    "/api/session/{session_id}/snapshots",
)
async def api_get_session_snapshots(session_id: int):
    """
    📋 Get all save slots for a session.
    Like viewing the "Load Game" menu with all your saves.

    Returns:
        List of all saves with full details (ID, title, description, step, timestamp)
    """
    snapshots = get_session_snapshots(session_id)
    return {
        "snapshots": [
            {
                "id": s.id,
                "title": s.title,
                "description": s.description,
                "current_step": s.current_step,
                "created_at": str(s.created_at),
                "session_id": s.session_id,
            }
            for s in snapshots
        ]
    }


@app.get('/api/session/{session_id}/compare/{snapshot_id}')
async def api_compare_checkpoint(session_id: int, snapshot_id: int):
    from story.checkpoints import compare_worlds
    current = get_session(session_id)
    saved = get_snapshot_details(snapshot_id)
    if current is None or saved is None or saved.session_id != session_id:
        raise HTTPException(404, 'session or checkpoint not found')
    try:
        comparison = compare_worlds(current.get_world_state(), json.loads(saved.world_state))
    except (ValueError, TypeError) as error:
        raise HTTPException(409, 'Checkpoint state cannot be compared; no story data was changed.') from error
    return JSONResponse(dict(session_id=session_id, snapshot_id=snapshot_id,
                        current_step=current.current_step, saved_step=saved.current_step,
                        checkpoint_title=saved.title, **comparison), headers={'Cache-Control': 'no-store'})


@app.post(
    "/api/session/{session_id}/load/{snapshot_id}",
)
async def api_load_specific_snapshot(session_id: int, snapshot_id: int):
    """
    📂 Load a specific save slot.
    Like clicking "Load Game" and selecting a specific save.
    This restores the game to the exact state when the save was created.

    Args:
        session_id: The session to restore
        snapshot_id: The specific save to load

    Returns:
        Restored session details (step number, world state)
    """
    logger.info("📂 Loading save: session=%d snapshot=%d", session_id, snapshot_id)

    # Get snapshot details first for logging
    snap = get_snapshot_details(snapshot_id)
    if snap:
        logger.info(
            "   Save: '%s' (Step %d, created %s)",
            snap.title,
            snap.current_step,
            snap.created_at,
        )

    s = load_snapshot(session_id, snapshot_id=snapshot_id)
    if not s:
        raise HTTPException(status_code=404, detail="snapshot or session not found")

    logger.info("✅ Save loaded successfully: restored to step %d", s.current_step)
    return {
        "status": "ok",
        "session_id": s.id,
        "current_step": s.current_step,
        "world_state": s.get_world_state(),
        "message": f"Game loaded from '{snap.title if snap else 'save'}'",
    }


@app.get(
    "/api/session/{session_id}/export",
)
async def api_export(session_id: int, fmt: Literal["json", "text"] = "json"):
    s = get_session(session_id)
    if not s:
        raise HTTPException(status_code=404, detail="session not found")
    history = get_steps(session_id)
    data = {
        "session": {
            "id": s.id,
            "user_id": s.user_id,
            "title": s.title,
            "current_step": s.current_step,
            "world_state": s.get_world_state(),
        },
        "steps": [
            {
                "step_index": st.step_index,
                "prompt": st.prompt,
                "ai_output": st.ai_output,
                "user_input": st.user_input,
                "created_at": str(st.created_at),
            }
            for st in history
        ],
    }
    if fmt == "text":
        lines = [f"Title: {s.title}", "", "Story:"]
        for st in history:
            lines.append(f"\nStep {st.step_index}:")
            lines.append(parse_ai_output(st.ai_output).get("narration", st.ai_output))
            if st.user_input:
                lines.append(f"\nUser: {st.user_input}")
        return PlainTextResponse("\n".join(lines))
    return JSONResponse(data)


@app.get(
    "/api/snapshot/{snapshot_id}",
)
async def api_get_snapshot_details(snapshot_id: int):
    """
    🔍 Get detailed information about a specific save.

    Args:
        snapshot_id: The save to inspect

    Returns:
        Full save details including title, description, step, world state, timestamp
    """
    snap = get_snapshot_details(snapshot_id)
    if not snap:
        raise HTTPException(status_code=404, detail="snapshot not found")

    return {
        "id": snap.id,
        "session_id": snap.session_id,
        "title": snap.title,
        "description": snap.description,
        "current_step": snap.current_step,
        "created_at": str(snap.created_at),
        "world_state": json.loads(snap.world_state) if snap.world_state else {},
    }


@app.put(
    "/api/snapshot/{snapshot_id}/rename",
)
async def api_rename_snapshot(snapshot_id: int, req: RenameSnapshotRequest):
    """
    ✏️ Rename a save slot.
    Like renaming "Save 1" to "Before Dragon Boss Fight".

    Args:
        snapshot_id: The save to rename
        req: New title

    Returns:
        Success status
    """
    logger.info("✏️ Renaming snapshot %d to '%s'", snapshot_id, req.new_title)
    success = rename_snapshot(snapshot_id, req.new_title)
    if not success:
        raise HTTPException(status_code=404, detail="snapshot not found")

    logger.info("✅ Snapshot renamed successfully")
    return {"status": "ok", "message": f"Save renamed to '{req.new_title}'"}


@app.put(
    "/api/snapshot/{snapshot_id}/description",
)
async def api_update_snapshot_description(
    snapshot_id: int, req: UpdateDescriptionRequest
):
    """
    📝 Update the description/preview text of a save.

    Args:
        snapshot_id: The save to update
        req: New description

    Returns:
        Success status
    """
    success = update_snapshot_description(snapshot_id, req.new_description)
    if not success:
        raise HTTPException(status_code=404, detail="snapshot not found")

    return {"status": "ok", "message": "Description updated"}


@app.delete(
    "/api/snapshot/{snapshot_id}",
)
async def api_delete_snapshot(snapshot_id: int):
    """
    🗑️ Delete a save slot.
    Like deleting an old save you don't need anymore.

    Args:
        snapshot_id: The save to delete

    Returns:
        Success status
    """
    logger.warning("🗑️ Deleting snapshot %d", snapshot_id)
    success = delete_snapshot(snapshot_id)
    if not success:
        raise HTTPException(status_code=404, detail="snapshot not found")

    logger.info("✅ Snapshot deleted successfully")
    return {"status": "ok", "message": "Save deleted"}


@app.get(
    "/api/session/{session_id}/memory",
)
async def api_get_memory(session_id: int):
    """Get all memory data for a session (NPCs, locations, events, relationships, inventory, discoveries)"""
    s = get_session(session_id)
    if not s:
        raise HTTPException(status_code=404, detail="session not found")

    world_state = s.get_world_state()
    memory = world_state.get("memory", {})

    return {
        "session_id": session_id,
        "npcs": memory.get("npcs", {}),
        "locations": memory.get("locations", {}),
        "events": memory.get("events", []),
        "relationships": memory.get("relationships", {}),
        "inventory": memory.get("inventory", []),
        "discoveries": memory.get("discoveries", []),
    }


@app.get(
    "/api/session/{session_id}/story-full",
)
async def api_get_full_story(session_id: int):
    """Get the complete story with all steps in a structured format"""
    s = get_session(session_id)
    if not s:
        raise HTTPException(status_code=404, detail="session not found")

    history = get_steps(session_id)

    return {
        "session_id": session_id,
        "title": s.title,
        "current_step": s.current_step,
        "total_steps": len(history),
        "steps": [
            {
                "step_index": st.step_index,
                "narration": parse_ai_output(st.ai_output).get(
                    "narration", st.ai_output
                ),
                "user_action": st.user_input,
                "timestamp": str(st.created_at),
            }
            for st in history
        ],
    }


class SummarizeRequest(InputModel):
    text: str = Field(min_length=1, max_length=30000)
    model: Literal["local", "hf", "fallback"] | None = None


@app.post(
    "/api/session/{session_id}/summarize",
)
async def api_summarize_scene(session_id: int, req: SummarizeRequest, request: Request):
    """Generate a summary of the provided scene text using AI"""
    await log_request(request)
    logger.info("📝 API: Summarizing scene for session %d", session_id)
    logger.info("   Text length: %d chars", len(req.text))
    logger.info("   Model: %s", req.model or "default")

    try:
        from llm.manager import LLMManager

        # Create a prompt for summarization
        summary_prompt = f"""Please provide a brief summary of what happened in this scene. Focus on the key events, actions, and important details. Keep it concise (2-3 sentences).

Scene:
{req.text}

Summary:"""

        llm = LLMManager()
        summary = await llm.generate(summary_prompt, model=req.model, max_tokens=200)

        # Clean up the summary (remove any extra formatting)
        summary = summary.strip()

        logger.info("✅ API: Summary generated successfully (%d chars)", len(summary))
        return {"summary": summary, "session_id": session_id}
    except Exception as e:
        logger.error("❌ API: Failed to generate summary for session %d", session_id)
        logger.exception("Full error details:")
        raise HTTPException(
            status_code=500, detail=f"Failed to generate summary: {str(e)}"
        )


if __name__ == "__main__":
    uvicorn.run("api.main:app", host=API_HOST, port=API_PORT, log_level="info")
