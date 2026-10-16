# db/db.py
from sqlmodel import SQLModel, Field, create_engine, Session, select
from typing import Optional, List
from datetime import datetime
from pydantic import NaiveDatetime
import json
from config import DATABASE_URL
import logging
import threading
from sqlalchemy import inspect, text, update

# Create engine
connect_args = (
    {"check_same_thread": False, "timeout": 30}
    if DATABASE_URL.startswith("sqlite")
    else {}
)
engine = create_engine(DATABASE_URL, connect_args=connect_args)
logger = logging.getLogger(__name__)


# Models
class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str
    created_at: NaiveDatetime = Field(default_factory=datetime.utcnow)


class SessionModel(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int
    title: str = "Untitled"
    world_state: str = Field(default="{}")  # JSON serialized dict
    current_step: int = 0
    created_at: NaiveDatetime = Field(default_factory=datetime.utcnow)
    updated_at: NaiveDatetime = Field(default_factory=datetime.utcnow)

    def get_world_state(self):
        try:
            return json.loads(self.world_state or "{}")
        except Exception:
            return {}

    def set_world_state(self, obj: dict):
        self.world_state = json.dumps(obj)


class Step(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: int
    step_index: int
    prompt: str
    ai_output: str
    user_input: Optional[str] = None
    created_at: NaiveDatetime = Field(default_factory=datetime.utcnow)


class Snapshot(SQLModel, table=True):
    """
    Game-like save snapshot system.
    Each snapshot represents a save point that can be loaded later.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: int
    created_at: NaiveDatetime = Field(default_factory=datetime.utcnow)
    title: str = (
        "autosave"  # User-friendly save name (e.g., "Before entering the castle")
    )
    description: str = Field(
        default=""
    )  # Preview text showing what's happening at this point
    world_state: str = Field(default="{}")  # Full game state (JSON)
    current_step: int = 0  # Step number at save point
    history: str = Field(default="[]")  # Independent timeline for branching saves


# Initialize DB once safely
_db_init_lock = threading.Lock()
_initialized_engine = None


def init_db():
    global _initialized_engine
    with _db_init_lock:
        if _initialized_engine is engine:
            return
        logger.info("Initializing database at %s", DATABASE_URL)
        SQLModel.metadata.create_all(engine)
        # Additive migration: existing story databases and saves remain intact.
        columns = {column["name"] for column in inspect(engine).get_columns("snapshot")}
        if "history" not in columns:
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "ALTER TABLE snapshot ADD COLUMN history TEXT NOT NULL DEFAULT '[]'"
                    )
                )
        _initialized_engine = engine
        logger.info("Database initialized")


# CRUD helpers
def _delete_session_rows(connection, session):
    for model in (Step, Snapshot):
        for row in connection.exec(
            select(model).where(model.session_id == session.id)
        ).all():
            connection.delete(row)
    connection.delete(session)


def commit_story_step(
    session_id, step_index, world_state, prompt, ai_output, user_input=None
):
    """Commit the scene and its world state together; reject stale generations."""
    with Session(engine) as connection:
        result = connection.execute(
            update(SessionModel)
            .where(
                SessionModel.id == session_id,
                SessionModel.current_step == step_index - 1,
            )
            .values(
                world_state=json.dumps(world_state),
                current_step=step_index,
                updated_at=datetime.utcnow(),
            )
        )
        if result.rowcount != 1:
            raise ValueError(
                "Story changed while generating. Reload the current scene."
            )
        connection.add(
            Step(
                session_id=session_id,
                step_index=step_index,
                prompt=prompt,
                ai_output=ai_output,
                user_input=user_input,
            )
        )
        connection.commit()


def create_user(username: str) -> User:
    logger.debug("create_user username=%s", username)
    with Session(engine) as s:
        username = username.strip()
        if not username:
            raise ValueError("Username is required")
        existing = s.exec(select(User).where(User.username == username)).first()
        if existing:
            return existing
        user = User(username=username)
        s.add(user)
        s.commit()
        s.refresh(user)
        logger.info("User created id=%s username=%s", user.id, user.username)
        return user


def get_user(user_id: int) -> Optional[User]:
    logger.debug("get_user id=%s", user_id)
    with Session(engine) as s:
        return s.get(User, user_id)


def get_all_users() -> List[User]:
    with Session(engine) as s:
        users = s.exec(select(User)).all()
        logger.debug("get_all_users count=%s", len(users))
        return users


def get_all_sessions() -> List[SessionModel]:
    with Session(engine) as s:
        rows = s.exec(select(SessionModel)).all()
        logger.debug("get_all_sessions count=%s", len(rows))
        return rows


def get_all_snapshots() -> List[Snapshot]:
    try:
        with Session(engine) as s:
            rows = s.exec(select(Snapshot)).all()
            logger.debug("get_all_snapshots count=%s", len(rows))
            return rows
    except Exception as e:
        logger.error(f"Error in get_all_snapshots: {e}", exc_info=True)
        raise


def delete_user(user_id: int) -> bool:
    logger.warning("delete_user id=%s", user_id)
    with Session(engine) as s:
        user = s.get(User, user_id)
        if not user:
            return False
        sessions = s.exec(
            select(SessionModel).where(SessionModel.user_id == user_id)
        ).all()
        for session in sessions:
            _delete_session_rows(s, session)
        s.delete(user)
        s.commit()
        logger.info("User deleted id=%s", user_id)
        return True


def delete_session(session_id: int) -> bool:
    logger.warning("delete_session id=%s", session_id)
    with Session(engine) as s:
        session = s.get(SessionModel, session_id)
        if not session:
            return False
        _delete_session_rows(s, session)
        s.commit()
        logger.info("Session deleted id=%s", session_id)
        return True


def delete_snapshot(snapshot_id: int) -> bool:
    logger.warning("delete_snapshot id=%s", snapshot_id)
    with Session(engine) as s:
        snapshot = s.get(Snapshot, snapshot_id)
        if not snapshot:
            return False
        s.delete(snapshot)
        s.commit()
        logger.info("Snapshot deleted id=%s", snapshot_id)
        return True


def create_session(
    user_id: int, title: str = "Untitled", world_state: dict | None = None
) -> SessionModel:
    logger.info("create_session user_id=%s title=%s", user_id, title)
    with Session(engine) as s:
        if not s.get(User, user_id):
            raise ValueError("User not found")
        sess = SessionModel(user_id=user_id, title=title)
        if world_state:
            sess.set_world_state(world_state)
        s.add(sess)
        s.commit()
        s.refresh(sess)
        logger.info("Session created id=%s for user_id=%s", sess.id, user_id)
        return sess


def get_session(session_id: int) -> Optional[SessionModel]:
    logger.debug("get_session id=%s", session_id)
    with Session(engine) as s:
        return s.get(SessionModel, session_id)


def update_session(
    session_id: int, world_state: dict | None = None, current_step: int | None = None
):
    logger.debug(
        "update_session id=%s current_step=%s ws_keys=%s",
        session_id,
        current_step,
        list((world_state or {}).keys()),
    )
    with Session(engine) as s:
        sess = s.get(SessionModel, session_id)
        if not sess:
            return None
        if world_state is not None:
            sess.set_world_state(world_state)
        if current_step is not None:
            sess.current_step = current_step
        sess.updated_at = datetime.utcnow()
        s.add(sess)
        s.commit()
        s.refresh(sess)
        logger.debug("update_session saved id=%s step=%s", sess.id, sess.current_step)
        return sess


def save_step(
    session_id: int,
    step_index: int,
    prompt: str,
    ai_output: str,
    user_input: str | None = None,
) -> Step:
    logger.info("save_step session_id=%s step_index=%s", session_id, step_index)
    with Session(engine) as s:
        st = Step(
            session_id=session_id,
            step_index=step_index,
            prompt=prompt,
            ai_output=ai_output,
            user_input=user_input,
        )
        s.add(st)
        s.commit()
        s.refresh(st)
        logger.debug("step saved id=%s", st.id)
        return st


def get_steps(session_id: int) -> List[Step]:
    with Session(engine) as s:
        q = select(Step).where(Step.session_id == session_id).order_by(Step.step_index)
        rows = s.exec(q).all()
        logger.debug("get_steps session_id=%s count=%s", session_id, len(rows))
        return rows


def reset_session(session_id: int):
    logger.info("reset_session id=%s", session_id)
    with Session(engine) as s:
        sess = s.get(SessionModel, session_id)
        if not sess:
            return None
        sess.set_world_state({})
        sess.current_step = 0
        s.add(sess)
        # delete steps
        q = select(Step).where(Step.session_id == session_id)
        steps = s.exec(q).all()
        for st in steps:
            s.delete(st)
        s.commit()
        logger.info("session reset id=%s deleted_steps=%s", session_id, len(steps))
        return sess


def create_snapshot(
    session_id: int, title: str = "autosave", description: str = ""
) -> Snapshot | None:
    """
    Create a game save snapshot.

    Args:
        session_id: The session to save
        title: User-friendly save name (e.g., "Save Slot 1", "Before boss fight")
        description: Preview text (auto-generated from recent narration if empty)

    Returns:
        Created snapshot, or None if session not found
    """
    logger.info("create_snapshot session_id=%s title=%s", session_id, title)
    try:
        with Session(engine) as s:
            sess = s.get(SessionModel, session_id)
            if not sess:
                logger.warning("Session %s not found", session_id)
                return None

            # Auto-generate description from last narration if not provided
            if not description:
                q = (
                    select(Step)
                    .where(Step.session_id == session_id)
                    .order_by(Step.step_index.desc())
                )
                last_step = s.exec(q).first()
                if last_step and last_step.ai_output:
                    # Take first 150 characters as preview
                    description = last_step.ai_output[:150].strip()
                    if len(last_step.ai_output) > 150:
                        description += "..."

            snap = Snapshot(
                session_id=session_id,
                title=title,
                description=description,
                world_state=sess.world_state or "{}",
                current_step=sess.current_step,
                history=json.dumps(
                    [
                        {
                            "step_index": row.step_index,
                            "prompt": row.prompt,
                            "ai_output": row.ai_output,
                            "user_input": row.user_input,
                            "created_at": row.created_at.isoformat(),
                        }
                        for row in s.exec(
                            select(Step)
                            .where(Step.session_id == session_id)
                            .order_by(Step.step_index)
                        ).all()
                    ]
                ),
            )
            s.add(snap)
            s.commit()
            s.refresh(snap)
            logger.info(
                "💾 Snapshot created: id=%s session=%s step=%s title='%s'",
                snap.id,
                session_id,
                snap.current_step,
                title,
            )
            return snap
    except Exception as e:
        logger.error("❌ Failed to create snapshot: %s", str(e))
        logger.exception("Full error details:")
        raise


def load_snapshot(
    session_id: int, snapshot_id: int | None = None
) -> SessionModel | None:
    """Restore the saved decision point and its independent story timeline."""
    with Session(engine) as connection:
        if snapshot_id is None:
            snapshot = connection.exec(
                select(Snapshot)
                .where(Snapshot.session_id == session_id)
                .order_by(Snapshot.id.desc())
            ).first()
        else:
            snapshot = connection.get(Snapshot, snapshot_id)
        session = connection.get(SessionModel, session_id)
        if not snapshot or snapshot.session_id != session_id or not session:
            return None
        saved_history = json.loads(snapshot.history or "[]")
        existing = connection.exec(
            select(Step).where(Step.session_id == session_id)
        ).all()
        for row in existing:
            if saved_history or row.step_index > snapshot.current_step:
                connection.delete(row)
        if saved_history:
            connection.flush()
            for row in saved_history:
                row["created_at"] = datetime.fromisoformat(row["created_at"])
                connection.add(Step(session_id=session_id, **row))
        session.world_state = snapshot.world_state
        session.current_step = snapshot.current_step
        session.updated_at = datetime.utcnow()
        connection.add(session)
        connection.commit()
        connection.refresh(session)
        return session


def get_session_snapshots(session_id: int) -> List[Snapshot]:
    """
    Get all save snapshots for a session, ordered by creation time (newest first).
    Like viewing all save slots in a game.

    Args:
        session_id: The session to get saves for

    Returns:
        List of snapshots with full details
    """
    with Session(engine) as s:
        q = (
            select(Snapshot)
            .where(Snapshot.session_id == session_id)
            .order_by(Snapshot.created_at.desc())
        )
        snapshots = s.exec(q).all()
        logger.debug(
            "get_session_snapshots session_id=%s count=%s", session_id, len(snapshots)
        )
        return snapshots


def get_snapshot_details(snapshot_id: int) -> Optional[Snapshot]:
    """
    Get detailed information about a specific save.

    Args:
        snapshot_id: The snapshot to retrieve

    Returns:
        Snapshot with all details, or None if not found
    """
    with Session(engine) as s:
        snap = s.get(Snapshot, snapshot_id)
        return snap


def rename_snapshot(snapshot_id: int, new_title: str) -> bool:
    """
    Rename a save slot (like renaming "Save 1" to "Before Dragon Fight").

    Args:
        snapshot_id: The snapshot to rename
        new_title: New name for the save

    Returns:
        True if successful, False if snapshot not found
    """
    logger.info("rename_snapshot id=%s new_title='%s'", snapshot_id, new_title)
    with Session(engine) as s:
        snap = s.get(Snapshot, snapshot_id)
        if not snap:
            logger.warning("Snapshot not found for rename: id=%s", snapshot_id)
            return False
        snap.title = new_title
        s.add(snap)
        s.commit()
        logger.info("✏️ Snapshot renamed: id=%s title='%s'", snapshot_id, new_title)
        return True


def update_snapshot_description(snapshot_id: int, new_description: str) -> bool:
    """
    Update the description/preview text of a save.

    Args:
        snapshot_id: The snapshot to update
        new_description: New description text

    Returns:
        True if successful, False if snapshot not found
    """
    logger.info("update_snapshot_description id=%s", snapshot_id)
    with Session(engine) as s:
        snap = s.get(Snapshot, snapshot_id)
        if not snap:
            return False
        snap.description = new_description
        s.add(snap)
        s.commit()
        logger.info("📝 Snapshot description updated: id=%s", snapshot_id)
        return True
