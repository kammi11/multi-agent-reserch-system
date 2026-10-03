import pytest

from app.agents.source_evaluator import evaluate_source
from app.schemas.models import Source
from app.tools.embeddings import chunk_text


def test_chunking_produces_overlapping_windows():
    text = " ".join(f"word{i}" for i in range(500))
    chunks = chunk_text("src1", text, chunk_size=100, overlap=20)
    assert len(chunks) > 1
    # consecutive chunks should overlap
    first_words = chunks[0].text.split()
    second_words = chunks[1].text.split()
    assert set(first_words[-20:]) & set(second_words[:20])


def test_chunking_empty_text():
    assert chunk_text("src1", "") == []


def test_source_quality_academic_domain_gets_authority_boost():
    s = Source(id="s1", title="t", url="https://arxiv.org/abs/123", domain="arxiv.org",
               content="x" * 2000, published_date="2025-01-01")
    q = evaluate_source(s, relevance=0.8)
    assert q.inferred_type.value == "academic"
    assert q.authority >= 0.7


def test_source_quality_not_blanket_gov_trust():
    """A .gov source with no content and an old date should not
    automatically score maximally -- overall_confidence must reflect
    the composite, not the domain alone."""
    s = Source(id="s2", title="t", url="https://example.gov/old", domain="example.gov",
               content="short", published_date="2015-01-01")
    q = evaluate_source(s, relevance=0.3)
    assert q.overall_confidence < 0.75


def test_recency_scoring_prefers_newer_dates():
    recent = Source(id="s3", title="t", url="https://x.com/a", domain="x.com",
                     content="x" * 1000, published_date="2026-08-01")
    old = Source(id="s4", title="t", url="https://x.com/b", domain="x.com",
                 content="x" * 1000, published_date="2018-01-01")
    q_recent = evaluate_source(recent, relevance=0.5)
    q_old = evaluate_source(old, relevance=0.5)
    assert q_recent.recency > q_old.recency
