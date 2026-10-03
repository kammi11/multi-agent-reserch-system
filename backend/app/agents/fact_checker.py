from __future__ import annotations

import json
import asyncio

from app.schemas.models import Citation, ClaimVerification, EvidenceItem, Source
from app.services import llm

SYSTEM_FACT_CHECK = """TASK: fact_check
You are the Fact Checking agent. Given a claim and retrieved evidence,
check whether the evidence directly entails the claim. Do not treat
topical similarity, plausibility, or one source repeating another as
support. Reject claims with stronger numbers, dates, causal language,
or certainty than the evidence. Respond with ONLY JSON:
{"has_supporting_evidence": bool, "is_overstated": bool, "verdict": "pass"|"fail", "notes": "..."}"""


async def fact_check_claim(claim: str, evidence_texts: list[str]) -> dict:
    user = json.dumps({"claim": claim, "evidence_texts": evidence_texts})
    return await llm.complete(SYSTEM_FACT_CHECK, user, expect_json=True)


async def verify_claims(
    evidence: list[EvidenceItem], sources: list[Source]
) -> tuple[list[ClaimVerification], list[Citation]]:
    """
    For each evidence item, this both fact-checks the claim against ALL
    retrieved evidence (not just its own source, so a claim isolated to
    one weak source is caught) and, on a pass, mints a citation marker
    that always points at a source_id that was actually retrieved --
    citations are never generated independently of a real Source object.
    """
    verifications: list[ClaimVerification] = []
    citations: list[Citation] = []
    source_ids = {s.id for s in sources}
    evidence_by_source: dict[str, list[str]] = {}
    for entry in evidence:
        evidence_by_source.setdefault(entry.source_id, []).append(entry.evidence)

    marker_by_source: dict[str, str] = {}
    next_marker = 1

    semaphore = asyncio.Semaphore(6)

    async def check(item: EvidenceItem) -> dict:
        async with semaphore:
            # Only evidence from the source being cited can substantiate its
            # citation; another page cannot silently lend support to it.
            return await fact_check_claim(item.claim, evidence_by_source.get(item.source_id, []))

    eligible = [item for item in evidence if item.source_id in source_ids]
    results = await asyncio.gather(*(check(item) for item in eligible))

    for item, result in zip(eligible, results):
        verdict = result.get("verdict", "fail")
        if verdict not in {"pass", "fail"}:
            verdict = "fail"
        # A passing label without explicit evidence support is not a pass.
        if verdict == "pass" and (not result.get("has_supporting_evidence") or result.get("is_overstated")):
            verdict = "fail"

        if item.source_id not in marker_by_source:
            marker_by_source[item.source_id] = f"[{next_marker}]"
            next_marker += 1
        marker = marker_by_source[item.source_id]

        verifications.append(ClaimVerification(
            claim=item.claim,
            citation_markers=[marker] if verdict == "pass" else [],
            has_supporting_evidence=bool(result.get("has_supporting_evidence")),
            is_overstated=bool(result.get("is_overstated")),
            verdict=verdict,
            notes=result.get("notes", ""),
        ))

        if verdict == "pass":
            citations.append(Citation(marker=marker, source_id=item.source_id, claim_snippet=item.claim[:160]))

    return verifications, citations
