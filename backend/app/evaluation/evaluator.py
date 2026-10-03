"""
Evaluation agent.

Every value in EvaluationReport is computed from the actual research
session's data (sources retrieved, evidence extracted, claims verified,
citations minted). Nothing here is a placeholder constant. Where a
metric genuinely requires external ground truth we don't have (e.g.
retrieval recall against a labeled relevant-document set), we report
None and say so explicitly in `notes` rather than inventing a number.
"""
from __future__ import annotations

from app.schemas.models import (
    Citation,
    ClaimVerification,
    ContradictionReport,
    EvaluationReport,
    Source,
    SourceQuality,
)


def evaluate_session(
    *,
    sources: list[Source],
    source_quality: list[SourceQuality],
    verifications: list[ClaimVerification],
    citations: list[Citation],
    contradictions: list[ContradictionReport],
    research_iterations: int,
    duration_seconds: float,
    ground_truth_relevant_domains: list[str] | None = None,
) -> EvaluationReport:
    notes: list[str] = []

    total_claims = len(verifications)
    passed = [v for v in verifications if v.verdict == "pass"]
    citation_completeness = (len(passed) / total_claims) if total_claims else 0.0
    unsupported_rate = 1 - citation_completeness if total_claims else 0.0

    # Citation correctness: of the citations minted, what fraction point to
    # a source that was actually retrieved (should always be 100% given
    # the fact_checker's defensive filtering, but we verify rather than
    # assume, which is the point of this metric).
    retrieved_ids = {s.id for s in sources}
    correct_citations = [c for c in citations if c.source_id in retrieved_ids]
    citation_correctness = (len(correct_citations) / len(citations)) if citations else 0.0

    # Groundedness: fraction of verified claims that had supporting
    # evidence per the fact-checker (distinct from "passed", since a
    # claim can have weak support and still not be overstated).
    grounded = [v for v in verifications if v.has_supporting_evidence]
    groundedness = (len(grounded) / total_claims) if total_claims else 0.0

    # Answer relevance: approximated as the fraction of extracted claims
    # that survived into the final, cited report (a claim that never
    # became citable did not contribute to answering the question).
    answer_relevance = citation_completeness

    # Source diversity: distinct domains / total sources.
    domains = {s.domain for s in sources}
    source_diversity = (len(domains) / len(sources)) if sources else 0.0

    unresolved = [c for c in contradictions if c.agreement_level.value == "contradiction"]

    retrieval_hit_rate = None
    if ground_truth_relevant_domains:
        hits = sum(1 for s in sources if s.domain in ground_truth_relevant_domains)
        retrieval_hit_rate = hits / len(sources) if sources else 0.0
    else:
        notes.append(
            "retrieval_hit_rate requires a labeled set of relevant domains for this "
            "question; none was supplied, so it is reported as null rather than guessed."
        )

    notes.append(
        "source_diversity is computed as distinct domains / total sources retrieved "
        "in this session, not against an external benchmark."
    )
    if not contradictions:
        notes.append("No claim clusters with overlapping topics across sources were found to compare.")

    return EvaluationReport(
        retrieval_hit_rate=retrieval_hit_rate,
        citation_completeness=round(citation_completeness, 4),
        citation_correctness=round(citation_correctness, 4),
        groundedness=round(groundedness, 4),
        answer_relevance=round(answer_relevance, 4),
        source_diversity=round(source_diversity, 4),
        unsupported_claim_rate=round(unsupported_rate, 4),
        contradictions_detected=len(contradictions),
        contradictions_unresolved=len(unresolved),
        research_iterations=research_iterations,
        sources_analyzed=len(sources),
        sources_used=len({c.source_id for c in citations}),
        research_duration_seconds=round(duration_seconds, 2),
        notes=notes,
    )
