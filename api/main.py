# api/main.py
import uvicorn
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel
from api.auth import api_key_required
from db.db import init_db, create_user, create_session, get_session, reset_session, get_steps, create_snapshot, load_snapshot, get_user, get_all_users, get_all_sessions, delete_user, delete_session, delete_snapshot, get_all_snapshots, get_session_snapshots, get_snapshot_details, rename_snapshot, update_snapshot_description, Session, select, User, SessionModel, Step, Snapshot, engine
from story.logic import start_session, advance_session
from story.memory_analyzer import analyze_and_refresh_memory  # NEW: Memory analysis
from utils.log_cleaner import start_log_cleaner, stop_log_cleaner
from utils.http_client import create_async_client
import asyncio
import logging
from config import API_HOST, API_PORT, API_KEY, configure_logging, LM_STUDIO_URL
from constants import LOG_SEPARATOR
import time
import json

logger = logging.getLogger(__name__)

# Request logging utility
async def log_request(request: Request):
    """Log incoming request details for debugging"""
    try:
        body = await request.body()
        logger.debug("Request %s %s body=%s", request.method, request.url.path, body[:200])
    except Exception:
        pass
app = FastAPI(title="Interactive Story Game API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# session locks to prevent race conditions
_session_locks: dict[int, asyncio.Lock] = {}

# Track which sessions are currently processing
_session_processing: dict[int, bool] = {}

@app.on_event("startup")
def on_startup():
    configure_logging()
    logger.info(LOG_SEPARATOR)
    logger.info("🚀 STORY MAKER BOT API - STARTING UP")
    logger.info(LOG_SEPARATOR)
    logger.info("Host: %s", API_HOST)
    logger.info("Port: %d", API_PORT)
    logger.info("LM Studio URL: %s", LM_STUDIO_URL)
    logger.info(LOG_SEPARATOR)
    
    init_db()
    logger.info("✅ Database initialized successfully")
    
    # Start automatic log cleaner (clears logs every 60 seconds)
    start_log_cleaner(interval=60)
    logger.info("🧹 Automatic log cleaner started (60s interval)")
    
    logger.info("🎉 API Server ready to accept requests")
    logger.info(LOG_SEPARATOR)

@app.on_event("shutdown")
def on_shutdown():
    logger.info("🛑 Shutting down API server...")
    stop_log_cleaner()
    logger.info("✅ Shutdown complete")

# Request models
class UserCreate(BaseModel):
    username: str

class SessionStart(BaseModel):
    user_id: int
    title: str = "Untitled"
    theme: str | None = None
    traits: list | None = None
    character_name: str | None = None
    model: str | None = None  # 'local' or 'hf'

class StepRequest(BaseModel):
    user_input: str | None = None
    choice_index: int | None = None
    model: str | None = None

class SaveRequest(BaseModel):
    title: str = "Quick Save"
    description: str = ""

class RenameSnapshotRequest(BaseModel):
    new_title: str

class UpdateDescriptionRequest(BaseModel):
    new_description: str

# endpoints
@app.post("/api/user", )
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

@app.post("/api/session/start", )
async def api_start_session(req: SessionStart, request: Request):
    await log_request(request)
    logger.info("🎬 API: Starting new session for user %d", req.user_id)
    logger.info("   Title: %s", req.title)
    logger.info("   Theme: %s", req.theme or "default")
    logger.info("   Character: %s", req.character_name or "default")
    logger.info("   Traits: %s", req.traits or [])
    logger.info("   Model: %s", req.model or "default")
    
    try:
        out = await start_session(
            req.user_id, 
            req.title, 
            theme=req.theme, 
            traits=req.traits,
            character_name=req.character_name,
            model=req.model
        )
        
        logger.info("✅ API: Session started successfully - ID: %d", out.get("session_id"))
        return out
    except Exception as e:
        logger.error("❌ API: Failed to start session for user %d", req.user_id)
        logger.exception("Full error details:")
        raise HTTPException(status_code=500, detail=f"Failed to start session: {str(e)}")

@app.get("/api/session/{session_id}/state", )
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
        "is_processing": _session_processing.get(session_id, False)
    }

@app.get("/api/session/{session_id}/processing", )
async def api_check_processing(session_id: int):
    """Check if a session is currently processing a request"""
    return {"session_id": session_id, "is_processing": _session_processing.get(session_id, False)}

@app.post("/api/session/{session_id}/step", )
async def api_step(session_id: int, req: StepRequest, request: Request):
    await log_request(request)
    logger.info("⏭️  API: Advancing session %d", session_id)
    logger.info("   User Input: %s", req.user_input or "(None)")
    logger.info("   Choice Index: %s", req.choice_index if req.choice_index is not None else "(None)")
    logger.info("   Model: %s", req.model or "default")
    
    # Check if session is already processing
    if _session_processing.get(session_id, False):
        logger.warning("⚠️  Session %d is already processing a request", session_id)
        raise HTTPException(
            status_code=409, 
            detail="Session is already processing a request. Please wait for the current generation to complete."
        )
    
    lock = _session_locks.get(session_id)
    if lock is None:
        lock = asyncio.Lock()
        _session_locks[session_id] = lock
        logger.debug("Created new lock for session %d", session_id)
    
    async with lock:
        try:
            # Mark session as processing
            _session_processing[session_id] = True
            logger.info("🔒 Lock acquired for session %d", session_id)
            
            out = await advance_session(session_id, user_input=req.user_input, choice_index=req.choice_index, model=req.model)
            logger.info("✅ API: Session %d advanced successfully to step %d", session_id, out.get("step_index"))
            return out
        except Exception as e:
            logger.error("❌ API: Error advancing session %d", session_id)
            logger.exception("Full error details:")
            raise HTTPException(status_code=400, detail=str(e))
        finally:
            # Always clear processing flag, even on error
            _session_processing[session_id] = False
            logger.debug("🔓 Session %d processing flag cleared", session_id)

@app.post("/api/session/{session_id}/reset", )
async def api_reset(session_id: int):
    s = reset_session(session_id)
    if not s:
        raise HTTPException(status_code=404, detail="session not found")
    return {"status": "ok", "session_id": s.id}

@app.post("/api/session/{session_id}/save", )
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
        
        logger.info("✅ Save created: snapshot_id=%d step=%d", snap.id, snap.current_step)
        return {
            "status": "ok", 
            "snapshot_id": snap.id, 
            "session_id": session_id,
            "title": snap.title,
            "description": snap.description,
            "current_step": snap.current_step,
            "created_at": str(snap.created_at)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("❌ Failed to create save: %s", str(e))
        logger.exception("Full error details:")
        raise HTTPException(status_code=500, detail=f"Failed to create save: {str(e)}")

@app.post("/api/session/{session_id}/load", )
async def api_load(session_id: int, request: Request):
    await log_request(request)
    s = load_snapshot(session_id, snapshot_id=None)
    if not s:
        raise HTTPException(status_code=404, detail="no snapshot or session not found")
    return {"status": "ok", "session_id": s.id, "current_step": s.current_step, "world_state": s.get_world_state()}

@app.get("/api/session/{session_id}/history", )
async def api_history(session_id: int):
    steps = get_steps(session_id)
    return {"steps": [{"step_index": st.step_index, "prompt": st.prompt, "ai_output": st.ai_output, "user_input": st.user_input, "created_at": str(st.created_at)} for st in steps]}

@app.post("/api/session/{session_id}/refresh-memory", )
async def api_refresh_memory(session_id: int, req: StepRequest, request: Request):
    """
    🧠 NEW: Refresh Memory Endpoint
    Analyzes recent story narrations and extracts/updates ALL memory elements.
    This is the "Refresh Memory" button functionality.
    """
    await log_request(request)
    logger.info("🧠 API: Refreshing memory for session %d", session_id)
    logger.info("   Model: %s", req.model or "default")
    
    # Check if session is already processing
    if _session_processing.get(session_id, False):
        logger.warning("⚠️  Session %d is already processing a request", session_id)
        raise HTTPException(
            status_code=409, 
            detail="Session is already processing a request. Please wait for the current operation to complete."
        )
    
    # Use lock to prevent concurrent memory analysis
    lock = _session_locks.get(session_id)
    if lock is None:
        lock = asyncio.Lock()
        _session_locks[session_id] = lock
    
    async with lock:
        try:
            # Mark session as processing
            _session_processing[session_id] = True
            logger.info("🔒 Lock acquired for memory analysis on session %d", session_id)
            
            result = await analyze_and_refresh_memory(session_id, model=req.model)
            
            if result.get("success"):
                logger.info("✅ API: Memory refreshed successfully for session %d", session_id)
            else:
                logger.warning("⚠️ API: Memory refresh completed with issues for session %d", session_id)
            
            return result
        except Exception as e:
            logger.error("❌ API: Error refreshing memory for session %d", session_id)
            logger.exception("Full error details:")
            raise HTTPException(status_code=500, detail=f"Memory refresh failed: {str(e)}")
        finally:
            # Always clear processing flag
            _session_processing[session_id] = False
            logger.debug("🔓 Session %d processing flag cleared", session_id)

@app.get("/api/health")
async def api_health():
    return {"status": "ok"}

@app.get("/api/performance")
async def api_performance():
    """Get performance statistics and cache info"""
    try:
        from utils.performance import get_performance_stats, get_cache_stats
        stats = get_performance_stats()
        return {
            "status": "ok",
            "performance": stats
        }
    except Exception as e:
        logger.error(f"Failed to get performance stats: {e}")
        return {
            "status": "error",
            "error": str(e)
        }

@app.get("/api/admin/ping-lmstudio")
async def api_ping_lmstudio():
    logger.info("🔍 API: Pinging LM Studio...")
    if not LM_STUDIO_URL:
        logger.warning("⚠️  LM_STUDIO_URL not configured")
        return {"ok": False, "error": "LM_STUDIO_URL not configured"}
    base = LM_STUDIO_URL.rstrip('/')
    endpoints = ["/v1/models", "/v1/health", "/health"]
    results = {}
    logger.info("Testing endpoints: %s", endpoints)
    async with create_async_client(API_KEY) as client:
        for ep in endpoints:
            url = f"{base}{ep}"
            try:
                logger.info("   Testing: %s", url)
                r = await client.get(url)
                results[ep] = {"status": r.status_code, "ok": r.status_code in (200, 404)}
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
        status = response.status_code if response is not None else '?'
        logger.info("HTTP %s %s -> %s in %dms", request.method, request.url.path, status, duration_ms)

        
@app.get("/")
async def root():
    return {"message": "Story Maker Bot API is running!"}

@app.get("/api/admin/users")
async def api_get_all_users():
    users = get_all_users()
    return {"users": [{"id": u.id, "username": u.username, "created_at": str(u.created_at)} for u in users]}

@app.get("/api/admin/sessions")
async def api_get_all_sessions():
    sessions = get_all_sessions()
    return {"sessions": [{"id": s.id, "user_id": s.user_id, "title": s.title, "current_step": s.current_step, "created_at": str(s.created_at)} for s in sessions]}

@app.get("/api/admin/snapshots")
async def api_get_all_snapshots():
    try:
        logger.debug("Fetching all snapshots")
        snapshots = get_all_snapshots()
        logger.debug(f"Found {len(snapshots)} snapshots")
        return {"snapshots": [{"id": s.id, "session_id": s.session_id, "title": s.title, "created_at": str(s.created_at)} for s in snapshots]}
    except Exception as e:
        logger.error(f"Error fetching snapshots: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error fetching snapshots: {str(e)}")

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
        logger.info("ADMIN clear-all deleted: snapshots=%s steps=%s sessions=%s users=%s", len(snaps), len(steps), len(sessions), len(users))
    
    return {"status": "ok", "message": "All data cleared"}

@app.get("/api/session/{session_id}/snapshots", )
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
                "session_id": s.session_id
            }
            for s in snapshots
        ]
    }

@app.post("/api/session/{session_id}/load/{snapshot_id}", )
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
        logger.info("   Save: '%s' (Step %d, created %s)", snap.title, snap.current_step, snap.created_at)
    
    s = load_snapshot(session_id, snapshot_id=snapshot_id)
    if not s:
        raise HTTPException(status_code=404, detail="snapshot or session not found")
    
    logger.info("✅ Save loaded successfully: restored to step %d", s.current_step)
    return {
        "status": "ok", 
        "session_id": s.id, 
        "current_step": s.current_step, 
        "world_state": s.get_world_state(),
        "message": f"Game loaded from '{snap.title if snap else 'save'}'"
    }

@app.get("/api/session/{session_id}/export", )
async def api_export(session_id: int, fmt: str = "json"):
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
            lines.append(st.ai_output)
            if st.user_input:
                lines.append(f"\nUser: {st.user_input}")
        return PlainTextResponse("\n".join(lines))
    return JSONResponse(data)

@app.get("/api/snapshot/{snapshot_id}", )
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
        "world_state": json.loads(snap.world_state) if snap.world_state else {}
    }

@app.put("/api/snapshot/{snapshot_id}/rename", )
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

@app.put("/api/snapshot/{snapshot_id}/description", )
async def api_update_snapshot_description(snapshot_id: int, req: UpdateDescriptionRequest):
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

@app.delete("/api/snapshot/{snapshot_id}", )
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

@app.get("/api/session/{session_id}/memory", )
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
        "discoveries": memory.get("discoveries", [])
    }

@app.get("/api/session/{session_id}/story-full", )
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
                "narration": st.ai_output,
                "user_action": st.user_input,
                "timestamp": str(st.created_at)
            }
            for st in history
        ]
    }

class SummarizeRequest(BaseModel):
    text: str
    model: str | None = None

@app.post("/api/session/{session_id}/summarize", )
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
        raise HTTPException(status_code=500, detail=f"Failed to generate summary: {str(e)}")

if __name__ == "__main__":
    # Run with reload for development, log_level for debugging
    # Access API at http://{API_HOST}:{API_PORT}
    import webbrowser
    import threading
    
    def open_browser():
        """Open browser after a short delay to ensure server is ready"""
        import time
        time.sleep(2)
        webbrowser.open(f"http://{API_HOST}:{API_PORT}/docs")
    
    # Start browser opener in background thread
    threading.Thread(target=open_browser, daemon=True).start()
    
    uvicorn.run("api.main:app", host=API_HOST, port=API_PORT, reload=True, log_level="info")
