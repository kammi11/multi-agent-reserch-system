from __future__ import annotations

import json
import time
import uuid

from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse

from app.graph.research_graph import RESEARCH_GRAPH, GraphState
from app.schemas.models import (
    AgentTrace,
    Citation,
    ClaimVerification,
    ContradictionReport,
    EvaluationReport,
    EvidenceItem,
    ResearchPlan,
    ResearchRequest,
    ResearchSession,
    Source,
    SourceQuality,
)
from app.services import session_store

router = APIRouter(prefix="/api", tags=["research"])


def _state_to_session(state: GraphState) -> ResearchSession:
    return ResearchSession(
        session_id=state["session_id"],
        user_question=state["question"],
        status=state.get("status", "running"),
        research_depth=state["depth"],
        research_plan=ResearchPlan(**state["plan"]) if state.get("plan") else None,
        sources=[Source(**s) for s in state.get("sources", [])],
        source_quality=[SourceQuality(**q) for q in state.get("source_quality", [])],
        evidence=[EvidenceItem(**e) for e in state.get("evidence", [])],
        contradictions=[ContradictionReport(**c) for c in state.get("contradictions", [])],
        claim_verifications=[ClaimVerification(**v) for v in state.get("verifications", [])],
        citations=[Citation(**c) for c in state.get("citations", [])],
        final_answer=state.get("final_answer", ""),
        evaluation=EvaluationReport(**state["evaluation"]) if state.get("evaluation") else None,
        execution_trace=[AgentTrace(**t) for t in state.get("trace", [])],
        research_iterations=state.get("iteration", 0),
    )


def _initial_state(req: ResearchRequest, session_id: str) -> GraphState:
    return GraphState(
        session_id=session_id, question=req.question, depth=req.research_depth.value,
        sources=[], source_quality=[], evidence=[], contradictions=[], verifications=[],
        citations=[], trace=[], iteration=0, started_at=time.time(), status="running",
    )


@router.post("/research/stream")
async def start_research_stream(req: ResearchRequest):
    session_id = f"session_{uuid.uuid4().hex[:10]}"
    state = _initial_state(req, session_id)

    async def event_gen():
        yield {"event": "session_started", "data": json.dumps({"session_id": session_id})}
        last_trace_len = 0
        final_state = state
        try:
            async for step in RESEARCH_GRAPH.astream(state):
                for node_name, node_state in step.items():
                    final_state = node_state
                    trace = node_state.get("trace", [])
                    for t in trace[last_trace_len:]:
                        yield {"event": "agent_step", "data": json.dumps({"node": node_name, **t})}
                    last_trace_len = len(trace)
                    yield {"event": "state_snapshot", "data": json.dumps({
                        "sources_count": len(node_state.get("sources", [])),
                        "evidence_count": len(node_state.get("evidence", [])),
                        "iteration": node_state.get("iteration", 0),
                    })}
        except Exception as exc:  # noqa: BLE001
            yield {"event": "error", "data": json.dumps({"error": str(exc)})}
            final_state["status"] = "failed"

        if final_state.get("status") != "failed":
            final_state["status"] = "completed"
        session = _state_to_session(final_state)
        session_store.save_session(session)
        yield {"event": "research_complete", "data": session.model_dump_json()}

    return EventSourceResponse(event_gen())


@router.post("/research", response_model=ResearchSession)
async def run_research_sync(req: ResearchRequest):
    """Non-streaming convenience endpoint: runs the full graph to
    completion and returns the final session. Used by tests, the
    evaluation harness, and any client that doesn't need live progress.
    """
    session_id = f"session_{uuid.uuid4().hex[:10]}"
    state = _initial_state(req, session_id)
    final_state = state
    async for step in RESEARCH_GRAPH.astream(state):
        for node_state in step.values():
            final_state = node_state
    if final_state.get("status") != "failed":
        final_state["status"] = "completed"
    session = _state_to_session(final_state)
    session_store.save_session(session)
    return session


@router.get("/research/{session_id}", response_model=ResearchSession)
async def get_research(session_id: str):
    session = session_store.load_session(session_id)
    if not session:
        raise HTTPException(404, "session not found")
    return session


def _field_or_404(session_id: str, field: str):
    session = session_store.load_session(session_id)
    if not session:
        raise HTTPException(404, "session not found")
    return getattr(session, field)


@router.get("/research/{session_id}/sources")
async def get_sources(session_id: str):
    return _field_or_404(session_id, "sources")


@router.get("/research/{session_id}/evidence")
async def get_evidence(session_id: str):
    return _field_or_404(session_id, "evidence")


@router.get("/research/{session_id}/claims")
async def get_claims(session_id: str):
    return _field_or_404(session_id, "claim_verifications")


@router.get("/research/{session_id}/trace")
async def get_trace(session_id: str):
    return _field_or_404(session_id, "execution_trace")


@router.get("/research/{session_id}/evaluation")
async def get_evaluation(session_id: str):
    return _field_or_404(session_id, "evaluation")


@router.get("/sessions")
async def list_sessions():
    return session_store.list_sessions()


@router.get("/health")
async def health():
    from app.config import get_settings

    s = get_settings()
    return {
        "status": "ok", "app_name": s.app_name,
        "llm_provider": s.llm_provider, "search_provider": s.search_provider,
        "embedding_provider": s.embedding_provider,
    }
