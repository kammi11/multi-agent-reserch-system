"""
The actual agent graph, built with LangGraph's StateGraph.

This is genuine node/edge orchestration over a shared, typed state --
not a single prompt pretending to be multiple agents. Two conditional
edges implement the two loops the spec calls for:

  1. research_sufficiency: after fact-checking, if evidence coverage is
     thin and we haven't hit MAX_RESEARCH_ITERATIONS, loop back to
     query generation with follow-up queries instead of proceeding.
  2. quality_gate: after evaluation, if citation completeness is below
     threshold and we still have iteration budget, loop back to
     additional research rather than returning a weak report.

Callers drive the graph with `astream(state)`, which yields the state
after every node executes -- the FastAPI route turns each yield into an
SSE event, so the frontend sees real per-node progress, not a synthetic
progress bar.
"""
from __future__ import annotations

import time
import uuid
import asyncio
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from app.agents import comparator, evidence as evidence_agent, fact_checker, planner, query_generator, source_evaluator, synthesizer
from app.config import get_settings
from app.evaluation.evaluator import evaluate_session
from app.schemas.models import (
    AgentTrace,
    Citation,
    ClaimVerification,
    ContradictionReport,
    EvaluationReport,
    EvidenceItem,
    ResearchDepth,
    ResearchPlan,
    Source,
    SourceQuality,
)
from app.tools import web_fetch, web_search
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


class GraphState(TypedDict, total=False):
    session_id: str
    question: str
    depth: str
    plan: dict
    queries: list[str]
    pending_queries: list[str]
    sources: list[dict]
    source_quality: list[dict]
    evidence: list[dict]
    contradictions: list[dict]
    verifications: list[dict]
    citations: list[dict]
    final_answer: str
    evaluation: dict
    trace: list[dict]
    iteration: int
    started_at: float
    status: str


def _trace(state: GraphState, agent: str, start: float, tool: str | None, in_s: str, out_s: str, status="ok", error=None):
    end = time.time()
    state.setdefault("trace", []).append(AgentTrace(
        agent=agent,
        start_time=time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(start)),
        end_time=time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(end)),
        duration_ms=round((end - start) * 1000, 1),
        tool=tool, input_summary=in_s[:200], output_summary=out_s[:200],
        status=status, error=error,
    ).model_dump())


async def node_plan(state: GraphState) -> GraphState:
    t0 = time.time()
    plan = await planner.plan_research(state["question"], ResearchDepth(state["depth"]))
    state["plan"] = plan.model_dump()
    _trace(state, "research_planner", t0, None, state["question"], f"{len(plan.subquestions)} subquestions")
    return state


async def node_generate_queries(state: GraphState) -> GraphState:
    t0 = time.time()
    settings = get_settings()
    plan = state["plan"]
    queries = await query_generator.generate_queries(
        state["question"], plan.get("subquestions", []), settings.max_queries_per_iteration,
    )
    state["queries"] = list(dict.fromkeys(state.get("queries", []) + queries))
    state["pending_queries"] = queries
    _trace(state, "query_generator", t0, None, str(plan.get("subquestions")), f"{len(queries)} queries")
    return state


async def node_search_and_fetch(state: GraphState) -> GraphState:
    t0 = time.time()
    settings = get_settings()
    existing_urls = {s["url"] for s in state.get("sources", [])}
    new_sources: list[dict] = []
    errors: list[str] = []

    async def search_one(q: str) -> tuple[str, list[dict], str | None]:
        try:
            return q, await web_search.web_search(q), None
        except web_search.SearchError as exc:
            return q, [], str(exc)

    query_results = await asyncio.gather(*(search_one(q) for q in state.get("pending_queries", [])))
    candidates: list[tuple[str, dict]] = []
    for q, results, error in query_results:
        if error:
            errors.append(error)
        for result in results:
            url = result.get("url", "").strip()
            if url and url not in existing_urls:
                existing_urls.add(url)
                candidates.append((q, result))

    semaphore = asyncio.Semaphore(8)

    async def fetch_one(q: str, result: dict):
        async with semaphore:
            try:
                doc = await web_fetch.fetch_webpage(result["url"], offline_doc=result.get("_offline_doc"))
            except web_fetch.FetchError as exc:
                return None, f"{result['url']}: {exc}"
            source = Source(
                id=f"source_{uuid.uuid4().hex[:8]}",
                title=doc["title"],
                url=result["url"],
                domain=doc["domain"],
                publisher=doc.get("domain"),
                author=doc.get("author"),
                published_date=doc.get("published_date"),
                content=doc["content"],
                query_used=q,
            )
            return source.model_dump(), None

    fetched = await asyncio.gather(*(fetch_one(q, result) for q, result in candidates))
    for source, error in fetched:
        if error:
            errors.append(error)
        elif source:
            new_sources.append(source)

    state["sources"] = state.get("sources", []) + new_sources
    status = "ok" if new_sources or not errors else "partial_failure"
    _trace(state, "web_search_agent", t0, "web_search+fetch_webpage",
           str(state.get("pending_queries")), f"{len(new_sources)} new sources, {len(errors)} errors",
           status=status, error="; ".join(errors[:3]) or None)
    return state


async def node_evaluate_sources(state: GraphState) -> GraphState:
    t0 = time.time()
    scored_ids = {sq["source_id"] for sq in state.get("source_quality", [])}
    new_quality = []
    unscored = [s for s in state["sources"] if s["id"] not in scored_ids]
    try:
        relevance_vectors = TfidfVectorizer(stop_words="english").fit_transform(
            [state["question"]] + [f"{s['title']} {s['content'][:5000]}" for s in unscored]
        ) if unscored else None
    except ValueError:
        relevance_vectors = None
    for index, s in enumerate(unscored, start=1):
        source = Source(**s)
        try:
            relevance = float(cosine_similarity(relevance_vectors[0:1], relevance_vectors[index:index + 1])[0][0])
        except (ValueError, TypeError):
            relevance = 0.0
        sq = source_evaluator.evaluate_source(source, relevance)
        new_quality.append(sq.model_dump())
    state["source_quality"] = state.get("source_quality", []) + new_quality
    _trace(state, "source_quality_agent", t0, None, f"{len(state['sources'])} sources", f"{len(new_quality)} newly scored")
    return state


async def node_extract_evidence(state: GraphState) -> GraphState:
    t0 = time.time()
    have_evidence_for = {e["source_id"] for e in state.get("evidence", [])}
    new_evidence: list[dict] = []
    semaphore = asyncio.Semaphore(6)

    async def extract(source_data: dict):
        async with semaphore:
            return await evidence_agent.extract_evidence(state["question"], Source(**source_data))

    pending = [s for s in state["sources"] if s["id"] not in have_evidence_for]
    batches = await asyncio.gather(*(extract(s) for s in pending))
    new_evidence.extend(item.model_dump() for batch in batches for item in batch)
    state["evidence"] = state.get("evidence", []) + new_evidence
    _trace(state, "evidence_extraction_agent", t0, None, f"{len(state['sources'])} sources", f"{len(new_evidence)} evidence items")
    return state


async def node_compare_sources(state: GraphState) -> GraphState:
    t0 = time.time()
    evidence_items = [EvidenceItem(**e) for e in state.get("evidence", [])]
    reports = await comparator.detect_contradictions(evidence_items)
    state["contradictions"] = [r.model_dump() for r in reports]
    _trace(state, "source_comparison_agent", t0, None, f"{len(evidence_items)} evidence items", f"{len(reports)} clusters compared")
    return state


async def node_fact_check(state: GraphState) -> GraphState:
    t0 = time.time()
    evidence_items = [EvidenceItem(**e) for e in state.get("evidence", [])]
    sources = [Source(**s) for s in state["sources"]]
    verifications, citations = await fact_checker.verify_claims(evidence_items, sources)
    state["verifications"] = [v.model_dump() for v in verifications]
    state["citations"] = [c.model_dump() for c in citations]
    passed = sum(1 for v in verifications if v.verdict == "pass")
    _trace(state, "fact_checking_agent", t0, None, f"{len(evidence_items)} claims", f"{passed}/{len(verifications)} passed")
    return state


def research_sufficiency(state: GraphState) -> str:
    settings = get_settings()
    verifications = state.get("verifications", [])
    passed = sum(1 for v in verifications if v.get("verdict") == "pass")
    coverage_ok = len(verifications) > 0 and (passed / len(verifications)) >= 0.5
    budget_left = state.get("iteration", 0) < settings.max_research_iterations
    if coverage_ok or not budget_left:
        return "synthesize"
    return "follow_up"


async def node_follow_up(state: GraphState) -> GraphState:
    t0 = time.time()
    state["iteration"] = state.get("iteration", 0) + 1
    plan = state["plan"]
    # Generate a narrower follow-up query set targeting subquestions that
    # don't yet have a passing verification, i.e. genuine gap-directed
    # search rather than re-running the same queries.
    covered_claims = {v["claim"] for v in state.get("verifications", []) if v.get("verdict") == "pass"}
    gap_subquestions = [sq for sq in plan.get("subquestions", []) if sq not in covered_claims] or plan.get("subquestions", [])
    settings = get_settings()
    follow_up_queries = await query_generator.generate_queries(
        state["question"], gap_subquestions, settings.max_queries_per_iteration,
    )
    state["pending_queries"] = [q for q in follow_up_queries if q not in state.get("queries", [])] or follow_up_queries
    state["queries"] = list(dict.fromkeys(state.get("queries", []) + state["pending_queries"]))
    _trace(state, "iteration_controller", t0, None, f"iteration {state['iteration']}", f"{len(state['pending_queries'])} follow-up queries")
    return state


async def node_synthesize(state: GraphState) -> GraphState:
    t0 = time.time()
    evidence_items = [EvidenceItem(**e) for e in state.get("evidence", [])]
    verifications = [ClaimVerification(**v) for v in state.get("verifications", [])]
    citations = [Citation(**c) for c in state.get("citations", [])]
    contradictions = [ContradictionReport(**c) for c in state.get("contradictions", [])]
    sources = [Source(**s) for s in state["sources"]]

    body = await synthesizer.synthesize(state["question"], evidence_items, verifications, citations, contradictions)
    sources_section = synthesizer.build_sources_section(citations, sources)
    state["final_answer"] = f"{body}\n\n{sources_section}"
    _trace(state, "synthesis_agent", t0, None, f"{len(citations)} citations", f"{len(state['final_answer'])} chars")
    return state


async def node_evaluate(state: GraphState) -> GraphState:
    t0 = time.time()
    sources = [Source(**s) for s in state["sources"]]
    source_quality = [SourceQuality(**q) for q in state.get("source_quality", [])]
    verifications = [ClaimVerification(**v) for v in state.get("verifications", [])]
    citations = [Citation(**c) for c in state.get("citations", [])]
    contradictions = [ContradictionReport(**c) for c in state.get("contradictions", [])]

    report = evaluate_session(
        sources=sources, source_quality=source_quality, verifications=verifications,
        citations=citations, contradictions=contradictions,
        research_iterations=state.get("iteration", 0),
        duration_seconds=time.time() - state["started_at"],
    )
    state["evaluation"] = report.model_dump()
    _trace(state, "evaluation_agent", t0, None, "final state", f"citation_completeness={report.citation_completeness}")
    return state


def quality_gate(state: GraphState) -> str:
    settings = get_settings()
    evaluation = state.get("evaluation", {})
    budget_left = state.get("iteration", 0) < settings.max_research_iterations
    if evaluation.get("citation_completeness", 0) < 0.34 and budget_left:
        return "follow_up"
    state["status"] = "completed"
    return "end"


def build_graph():
    graph = StateGraph(GraphState)
    graph.add_node("plan", node_plan)
    graph.add_node("generate_queries", node_generate_queries)
    graph.add_node("search_and_fetch", node_search_and_fetch)
    graph.add_node("evaluate_sources", node_evaluate_sources)
    graph.add_node("extract_evidence", node_extract_evidence)
    graph.add_node("compare_sources", node_compare_sources)
    graph.add_node("fact_check", node_fact_check)
    graph.add_node("follow_up", node_follow_up)
    graph.add_node("synthesize", node_synthesize)
    graph.add_node("evaluate", node_evaluate)

    graph.set_entry_point("plan")
    graph.add_edge("plan", "generate_queries")
    graph.add_edge("generate_queries", "search_and_fetch")
    graph.add_edge("search_and_fetch", "evaluate_sources")
    graph.add_edge("evaluate_sources", "extract_evidence")
    graph.add_edge("extract_evidence", "compare_sources")
    graph.add_edge("compare_sources", "fact_check")
    graph.add_conditional_edges("fact_check", research_sufficiency, {
        "follow_up": "follow_up", "synthesize": "synthesize",
    })
    graph.add_edge("follow_up", "search_and_fetch")
    graph.add_edge("synthesize", "evaluate")
    graph.add_conditional_edges("evaluate", quality_gate, {
        "follow_up": "follow_up", "end": END,
    })
    return graph.compile()


RESEARCH_GRAPH = build_graph()
