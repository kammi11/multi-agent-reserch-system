from __future__ import annotations

import json

from app.schemas.models import Citation, ClaimVerification, ContradictionReport, EvidenceItem, Source
from app.services import llm

SYSTEM = """TASK: synthesis
You are the Synthesis agent for a research system. Given the research
question, a list of VERIFIED evidence items (each already mapped to a
citation marker like [1]), and any contradiction reports, write a
structured Markdown research report with these sections: Executive
Summary, Key Findings (each finding must cite its marker inline, e.g.
[1]), Conflicting Evidence (if any), Limitations, Conclusion. Do not
introduce any claim that isn't backed by the provided evidence. Do not
include a Sources section (it is appended separately)."""


async def synthesize(
    question: str,
    evidence: list[EvidenceItem],
    verifications: list[ClaimVerification],
    citations: list[Citation],
    contradictions: list[ContradictionReport],
) -> str:
    marker_by_claim = {v.claim: v.citation_markers[0] for v in verifications if v.citation_markers}
    verified_evidence = [
        {"claim": e.claim, "evidence": e.evidence, "marker": marker_by_claim[e.claim]}
        for e in evidence if e.claim in marker_by_claim
    ]

    if not verified_evidence:
        return (
            "## Executive Summary\n\nThe available evidence was insufficient to establish "
            "confident, citable claims for this question within the current research budget. "
            "No unsupported claims have been included.\n"
        )

    user = json.dumps({
        "question": question,
        "evidence": verified_evidence,
        "contradictions": [c.model_dump() for c in contradictions],
    })
    return await llm.complete(SYSTEM, user, expect_json=False)


def build_sources_section(citations: list[Citation], sources: list[Source]) -> str:
    by_id = {s.id: s for s in sources}
    used_ids = list(dict.fromkeys(c.source_id for c in citations))
    marker_by_source = {c.source_id: c.marker for c in citations}
    lines = ["## Sources\n"]
    for sid in used_ids:
        s = by_id.get(sid)
        if not s:
            continue
        lines.append(
            f"{marker_by_source[sid]} {s.title} — {s.publisher or s.domain} — "
            f"{s.published_date or 'date unknown'} — {s.url}\n"
        )
    return "\n".join(lines)
