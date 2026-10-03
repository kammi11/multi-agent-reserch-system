"""
Source Quality agent.

Deliberately rule-based rather than routed through the LLM: source
quality signals here (recency from a parseable date, domain-type
heuristics, content length as an evidence-quality proxy) are things a
transparent, auditable scoring function is a better fit for than a
generative model, and it keeps this step fast and free regardless of
LLM_PROVIDER. Per the system's design goals, we deliberately avoid a
blanket "gov = always trustworthy" or "news = unreliable" rule -- every
score is a composite of several independent signals.
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.schemas.models import Source, SourceQuality, SourceType

_TYPE_AUTHORITY_PRIOR = {
    SourceType.academic: 0.80,
    SourceType.government: 0.75,
    SourceType.official_documentation: 0.75,
    SourceType.news: 0.60,
    SourceType.general_web: 0.50,
}

_DOMAIN_HINTS = {
    ".gov": SourceType.government,
    ".edu": SourceType.academic,
    "arxiv.org": SourceType.academic,
    "nature.com": SourceType.academic,
    "docs.": SourceType.official_documentation,
}


def _infer_type(source: Source) -> SourceType:
    domain = source.domain.lower()
    for hint, stype in _DOMAIN_HINTS.items():
        if hint in domain:
            return stype
    return source.source_type


def _recency_score(published_date: str | None) -> float:
    if not published_date:
        return 0.4  # unknown recency: neither penalized heavily nor assumed current
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S%z", "%Y"):
        try:
            dt = datetime.strptime(published_date[: len(fmt) if fmt != "%Y" else 4], fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            age_days = (datetime.now(timezone.utc) - dt).days
            if age_days < 0:
                return 0.5
            if age_days <= 180:
                return 0.95
            if age_days <= 365:
                return 0.8
            if age_days <= 365 * 2:
                return 0.6
            return 0.35
        except ValueError:
            continue
    return 0.4


def evaluate_source(source: Source, relevance: float) -> SourceQuality:
    inferred_type = _infer_type(source)
    authority = _TYPE_AUTHORITY_PRIOR.get(inferred_type, 0.5)
    recency = _recency_score(source.published_date)
    evidence_quality = min(1.0, 0.3 + len(source.content) / 4000)
    overall = round(0.35 * authority + 0.25 * relevance + 0.2 * recency + 0.2 * evidence_quality, 3)

    reasons = []
    reasons.append(f"inferred source type '{inferred_type.value}' (authority prior {authority:.2f})")
    reasons.append(f"recency score {recency:.2f} from published_date={source.published_date!r}")
    reasons.append(f"content length {len(source.content)} chars informs evidence-quality proxy")

    return SourceQuality(
        source_id=source.id,
        authority=round(authority, 3),
        relevance=round(relevance, 3),
        recency=round(recency, 3),
        evidence_quality=round(evidence_quality, 3),
        inferred_type=inferred_type,
        overall_confidence=overall,
        reason="; ".join(reasons),
    )
