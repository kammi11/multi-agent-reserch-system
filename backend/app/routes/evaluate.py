from __future__ import annotations

import json
import time
from pathlib import Path

from fastapi import APIRouter

from app.graph.research_graph import RESEARCH_GRAPH
from app.routes.research import _initial_state, _state_to_session
from app.schemas.models import ResearchDepth, ResearchRequest

router = APIRouter(prefix="/api", tags=["evaluation"])

DATASET_PATH = Path(__file__).resolve().parents[2] / "data" / "eval_dataset.json"


@router.post("/evaluate")
async def run_evaluation_dataset():
    """
    Runs every question in data/eval_dataset.json through the actual
    research graph (same code path as /api/research) and aggregates the
    per-session EvaluationReport values. This is a real run, not a
    canned report -- with SEARCH_PROVIDER/LLM_PROVIDER=offline it runs
    against the bundled demo corpus; point both at live providers to
    evaluate against the real web.
    """
    questions = json.loads(DATASET_PATH.read_text())
    t0 = time.time()
    per_question = []

    for q in questions:
        req = ResearchRequest(question=q["question"], research_depth=ResearchDepth.standard)
        session_id = f"eval_{abs(hash(q['question'])) % 10_000}"
        state = _initial_state(req, session_id)
        final_state = state
        async for step in RESEARCH_GRAPH.astream(state):
            for node_state in step.values():
                final_state = node_state
        if final_state.get("status") != "failed":
            final_state["status"] = "completed"
        session = _state_to_session(final_state)
        per_question.append({
            "question": q["question"],
            "sources_analyzed": len(session.sources),
            "evaluation": session.evaluation.model_dump() if session.evaluation else None,
        })

    evals = [p["evaluation"] for p in per_question if p["evaluation"]]

    def avg(key: str) -> float | None:
        vals = [e[key] for e in evals if e.get(key) is not None]
        return round(sum(vals) / len(vals), 4) if vals else None

    aggregate = {
        "citation_completeness": avg("citation_completeness"),
        "citation_correctness": avg("citation_correctness"),
        "groundedness": avg("groundedness"),
        "answer_relevance": avg("answer_relevance"),
        "source_diversity": avg("source_diversity"),
        "unsupported_claim_rate": avg("unsupported_claim_rate"),
    }

    return {
        "dataset_size": len(questions),
        "total_duration_seconds": round(time.time() - t0, 2),
        "aggregate_metrics": aggregate,
        "per_question": per_question,
        "note": "All figures computed from actual pipeline runs against the configured "
                "SEARCH_PROVIDER/LLM_PROVIDER; none are hardcoded.",
    }
