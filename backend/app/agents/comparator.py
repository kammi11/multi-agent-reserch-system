from __future__ import annotations

import json
from itertools import combinations

from app.schemas.models import AgreementLevel, ContradictionReport, EvidenceItem
from app.services import llm

SYSTEM = """TASK: source_comparison
You are the Source Comparison agent. Given two evidence statements
about a related topic, classify their relationship. Respond with ONLY
JSON: {"agreement_level": "agreement"|"partial_agreement"|"contradiction"|"different_scope",
"explanation": "..."}"""


def _cluster_by_claim_prefix(evidence: list[EvidenceItem]) -> dict[str, list[EvidenceItem]]:
    """Groups evidence items that plausibly discuss the same sub-topic.
    A lightweight lexical clustering (shared significant words) is used
    so we only run the (agent) comparison on pairs worth comparing,
    rather than an O(n^2) sweep over every unrelated evidence pair.
    """
    import re

    def sig_words(text: str) -> set[str]:
        return {w for w in re.findall(r"[a-z]{5,}", text.lower())}

    clusters: dict[str, list[EvidenceItem]] = {}
    used: set[str] = set()
    items = list(evidence)
    for i, item in enumerate(items):
        if item.id in used:
            continue
        bucket = [item]
        used.add(item.id)
        words_i = sig_words(item.claim + " " + item.evidence)
        for other in items[i + 1:]:
            if other.id in used or other.source_id == item.source_id:
                continue
            words_o = sig_words(other.claim + " " + other.evidence)
            overlap = words_i & words_o
            if len(overlap) >= 2:
                bucket.append(other)
                used.add(other.id)
        if len(bucket) > 1:
            clusters[item.id] = bucket
    return clusters


async def detect_contradictions(evidence: list[EvidenceItem]) -> list[ContradictionReport]:
    clusters = _cluster_by_claim_prefix(evidence)
    reports: list[ContradictionReport] = []
    for _, items in clusters.items():
        # Compare the first pair in the cluster (representative); a fuller
        # implementation would compare all pairs, but one representative
        # comparison per cluster keeps LLM/compute cost bounded per run.
        a, b = items[0], items[1]
        user = json.dumps({"statement_a": a.evidence, "statement_b": b.evidence})
        data = await llm.complete(SYSTEM, user, expect_json=True)
        level_raw = data.get("agreement_level", "different_scope")
        try:
            level = AgreementLevel(level_raw)
        except ValueError:
            level = AgreementLevel.insufficient_data

        supporting = [x.source_id for x in items if level in (AgreementLevel.agreement, AgreementLevel.partial_agreement)]
        contradicting = [x.source_id for x in items] if level == AgreementLevel.contradiction else []

        reports.append(ContradictionReport(
            claim=a.claim,
            supporting_sources=list(dict.fromkeys(supporting)) or [a.source_id],
            contradicting_sources=list(dict.fromkeys(contradicting)),
            agreement_level=level,
            explanation=data.get("explanation", ""),
            remaining_uncertainty="" if level != AgreementLevel.contradiction else
                "Sources disagree; both are retained in the report rather than forcing consensus.",
        ))
    return reports
