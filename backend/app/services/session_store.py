"""
Lightweight session persistence. Uses stdlib sqlite3 directly (a single
JSON blob column) rather than a full ORM -- this keeps the "local mode"
promise genuinely zero-dependency beyond Python's standard library, per
the spec's requirement to support SQLite/local mode without database
complexity. Swapping DATABASE_URL to a real Postgres/Supabase URL and
replacing this module's two functions is the only change needed to move
to a shared production database; the JSON-blob-per-session shape maps
directly onto the `research_sessions` table described in the spec.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from app.config import get_settings
from app.schemas.models import ResearchSession

_DB_PATH = Path(__file__).resolve().parents[2] / "data" / "researchpilot.db"


def _conn() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_DB_PATH)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS research_sessions ("
        "session_id TEXT PRIMARY KEY, created_at TEXT, status TEXT, data TEXT)"
    )
    return conn


def save_session(session: ResearchSession) -> None:
    with _conn() as conn:
        conn.execute(
            "INSERT INTO research_sessions (session_id, created_at, status, data) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(session_id) DO UPDATE SET status=excluded.status, data=excluded.data",
            (session.session_id, session.created_at, session.status, session.model_dump_json()),
        )


def load_session(session_id: str) -> ResearchSession | None:
    with _conn() as conn:
        row = conn.execute(
            "SELECT data FROM research_sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
    if not row:
        return None
    return ResearchSession(**json.loads(row[0]))


def list_sessions(limit: int = 50) -> list[ResearchSession]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT data FROM research_sessions ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [ResearchSession(**json.loads(r[0])) for r in rows]
