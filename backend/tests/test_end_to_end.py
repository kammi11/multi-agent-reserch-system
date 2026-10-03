import pytest

from app.graph.research_graph import RESEARCH_GRAPH
from app.routes.research import _initial_state, _state_to_session
from app.schemas.models import ResearchDepth, ResearchRequest


@pytest.mark.asyncio
async def test_end_to_end_research_pipeline():
    req = ResearchRequest(
        question="What are the benefits and limitations of RAG?",
        research_depth=ResearchDepth.quick,
    )
    state = _initial_state(req, "e2e_test_session")
    final_state = state
    async for step in RESEARCH_GRAPH.astream(state):
        for node_state in step.values():
            final_state = node_state
    final_state["status"] = "completed"
    session = _state_to_session(final_state)

    # Sources exist
    assert len(session.sources) > 0
    # Evidence exists
    assert len(session.evidence) > 0
    # Citations exist and every one maps to a retrieved source
    assert len(session.citations) > 0
    source_ids = {s.id for s in session.sources}
    assert all(c.source_id in source_ids for c in session.citations)
    # Final answer generated and contains at least one citation marker
    assert session.final_answer.strip()
    assert "[1]" in session.final_answer
    # Evaluation generated with computed (not null-by-default-except-flagged) metrics
    assert session.evaluation is not None
    assert 0.0 <= session.evaluation.citation_completeness <= 1.0
    assert session.evaluation.sources_analyzed == len(session.sources)


@pytest.mark.asyncio
async def test_no_citation_without_a_retrieved_source():
    """Never allow a citation to a source_id that wasn't actually in
    the session's retrieved sources -- this is the hard requirement
    from spec section 17/47 (never fabricate citations)."""
    req = ResearchRequest(question="Compare PostgreSQL vector search with dedicated vector databases.")
    state = _initial_state(req, "citation_integrity_test")
    final_state = state
    async for step in RESEARCH_GRAPH.astream(state):
        for node_state in step.values():
            final_state = node_state
    session = _state_to_session(final_state)
    retrieved_ids = {s.id for s in session.sources}
    for citation in session.citations:
        assert citation.source_id in retrieved_ids
