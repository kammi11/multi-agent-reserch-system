from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse

from app.services import session_store

router = APIRouter(prefix="/api", tags=["export"])


@router.get("/research/{session_id}/export.md")
async def export_markdown(session_id: str):
    session = session_store.load_session(session_id)
    if not session:
        raise HTTPException(404, "session not found")
    header = f"# Research Report: {session.user_question}\n\n_Session {session.session_id} — {session.created_at}_\n\n"
    return PlainTextResponse(header + session.final_answer, media_type="text/markdown")


@router.get("/research/{session_id}/export.json")
async def export_json(session_id: str):
    session = session_store.load_session(session_id)
    if not session:
        raise HTTPException(404, "session not found")
    return JSONResponse(content=session.model_dump())
