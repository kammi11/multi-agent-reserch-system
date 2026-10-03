"""
offline_reasoner: a genuine, deterministic, zero-network reasoning engine.

This is what LLM_PROVIDER=offline routes to. It is used for two reasons:
1. So ResearchPilot AI runs with literally zero paid/network services.
2. So this sandboxed build environment (no route to Ollama/OpenRouter)
   can actually execute the full agent graph end-to-end and print real,
   computed numbers instead of only shipping unrun code.

Every function here does real work on the actual input text (TF-IDF
similarity, sentence scoring, template construction from real fields) —
none of it is canned/hard-coded per question. Swap LLM_PROVIDER to
"ollama" or "openrouter" for fluent generative prose; the rest of the
pipeline (state, tools, evaluation, citation verification) is identical
either way.
"""
from __future__ import annotations

import json
import re

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def _task_of(system: str) -> str:
    m = re.search(r"TASK:\s*(\w+)", system)
    return m.group(1) if m else "generic"


def _split_sentences(text: str) -> list[str]:
    sents = re.split(r"(?<=[.!?])\s+", text.strip())
    return [s.strip() for s in sents if len(s.strip()) > 20]


def _top_sentences_by_query(query: str, text: str, k: int = 3) -> list[tuple[str, float]]:
    sentences = _split_sentences(text)
    if not sentences:
        return []
    corpus = [query] + sentences
    try:
        vec = TfidfVectorizer(stop_words="english").fit_transform(corpus)
    except ValueError:
        return [(s, 0.0) for s in sentences[:k]]
    sims = cosine_similarity(vec[0:1], vec[1:]).flatten()
    ranked = sorted(zip(sentences, sims), key=lambda x: x[1], reverse=True)
    return ranked[:k]


def _keywords(text: str, k: int = 6) -> list[str]:
    words = re.findall(r"[A-Za-z][A-Za-z\-]{3,}", text.lower())
    stop = {
        "what", "about", "which", "with", "from", "that", "this", "into",
        "have", "does", "current", "their", "these", "those", "your",
    }
    freq: dict[str, int] = {}
    for w in words:
        if w in stop:
            continue
        freq[w] = freq.get(w, 0) + 1
    return [w for w, _ in sorted(freq.items(), key=lambda x: -x[1])[:k]]


def _plan(user: str) -> str:
    payload = json.loads(user)
    question = payload["question"]
    depth = payload.get("depth", "standard")
    kws = _keywords(question, 8)
    n_sub = {"quick": 2, "standard": 3, "deep": 5}.get(depth, 3)
    subquestions = []
    angles = [
        "current evidence and data on {}",
        "expert or institutional perspectives on {}",
        "risks, limitations, or criticisms related to {}",
        "recent (last 1-2 years) developments in {}",
        "quantitative studies or statistics about {}",
    ]
    topic = " ".join(kws[:4]) or question
    for i in range(n_sub):
        subquestions.append(angles[i % len(angles)].format(topic))
    plan = {
        "research_question": question,
        "objectives": [
            f"Establish what is currently known about: {topic}",
            "Surface areas of consensus and disagreement across sources",
        ],
        "subquestions": subquestions,
        "search_strategy": [f"{topic} {kw}" for kw in kws[:3]] or [topic],
        "required_source_types": ["general_web", "news"] if depth == "quick" else
                                  ["academic", "news", "government", "general_web"],
        "research_depth": depth,
    }
    return json.dumps(plan)


def _query_generation(user: str) -> str:
    payload = json.loads(user)
    question = payload["question"]
    subquestions = payload.get("subquestions", [])
    max_queries = payload.get("max_queries", 4)
    kws = _keywords(question, 6)
    base = " ".join(kws[:3]) if kws else question
    queries = [question]
    for sq in subquestions:
        sub_kws = _keywords(sq, 4)
        q = " ".join(sub_kws[:4]) if sub_kws else sq
        if q not in queries:
            queries.append(q)
    # Deduplicate while preserving order, cap length.
    seen = set()
    deduped = []
    for q in queries:
        key = q.lower().strip()
        if key not in seen and key:
            seen.add(key)
            deduped.append(q)
    return json.dumps({"queries": deduped[:max_queries]})


def _evidence_extraction(user: str) -> str:
    payload = json.loads(user)
    question = payload["question"]
    content = payload["content"]
    top = _top_sentences_by_query(question, content, k=3)
    items = []
    for sent, score in top:
        if score <= 0:
            continue
        items.append({
            "claim": sent[:180],
            "evidence": sent,
            "confidence": round(min(0.95, 0.4 + float(score)), 2),
        })
    return json.dumps({"evidence": items})


def _source_comparison(user: str) -> str:
    payload = json.loads(user)
    a, b = payload["statement_a"], payload["statement_b"]
    vec = TfidfVectorizer(stop_words="english").fit_transform([a, b])
    sim = float(cosine_similarity(vec[0:1], vec[1:2])[0][0])
    negation_words = {"not", "no", "never", "isn't", "doesn't", "cannot", "can't", "lack", "lacks", "without"}
    a_neg = bool(negation_words & set(a.lower().split()))
    b_neg = bool(negation_words & set(b.lower().split()))
    if sim > 0.55 and a_neg == b_neg:
        level, explanation = "agreement", "The two statements share substantial overlapping content and the same polarity."
    elif sim > 0.55 and a_neg != b_neg:
        level, explanation = "contradiction", "The statements overlap in topic but differ in polarity (one affirms, one negates)."
    elif sim > 0.25:
        level, explanation = "partial_agreement", "The statements relate to the same topic but emphasize different aspects."
    else:
        level, explanation = "different_scope", "The statements address related but sufficiently distinct scopes to compare directly."
    return json.dumps({"agreement_level": level, "explanation": explanation, "similarity": round(sim, 3)})


def _fact_check(user: str) -> str:
    payload = json.loads(user)
    claim = payload["claim"]
    evidence_texts = payload.get("evidence_texts", [])
    if not evidence_texts:
        return json.dumps({"has_supporting_evidence": False, "is_overstated": True,
                            "verdict": "fail", "notes": "No retrieved evidence maps to this claim."})
    corpus = [claim] + evidence_texts
    vec = TfidfVectorizer(stop_words="english").fit_transform(corpus)
    sims = cosine_similarity(vec[0:1], vec[1:]).flatten()
    best = float(sims.max())
    if best > 0.35:
        return json.dumps({"has_supporting_evidence": True, "is_overstated": False,
                            "verdict": "pass", "notes": f"Best-matching evidence similarity: {best:.2f}"})
    return json.dumps({"has_supporting_evidence": best > 0.15, "is_overstated": True,
                        "verdict": "fail", "notes": f"Weak evidence match (similarity {best:.2f}); claim may be overstated."})


def _synthesis(user: str) -> str:
    payload = json.loads(user)
    question = payload["question"]
    evidence = payload["evidence"]  # list of {claim, evidence, source_id, marker}
    contradictions = payload.get("contradictions", [])

    lines = []
    lines.append("## Executive Summary\n")
    lines.append(
        f"This report synthesizes evidence gathered on: *{question}*. "
        f"{len(evidence)} evidence items were extracted across the retrieved sources "
        f"{'and ' + str(len(contradictions)) + ' point(s) of disagreement were identified.' if contradictions else 'with no major contradictions detected.'}\n"
    )
    lines.append("## Key Findings\n")
    for i, ev in enumerate(evidence[:8], start=1):
        lines.append(f"### Finding {i}\n{ev['evidence']} {ev['marker']}\n")
    if contradictions:
        lines.append("## Conflicting Evidence\n")
        for c in contradictions:
            lines.append(f"- **{c['claim']}** — {c['agreement_level']}: {c['explanation']}\n")
    lines.append("## Limitations\n")
    lines.append(
        "- This synthesis was produced by the offline extractive provider (LLM_PROVIDER=offline); "
        "prose is templated from retrieved evidence rather than freely generated.\n"
        "- Source coverage is limited to what the configured search provider returned within the "
        "configured research-iteration budget.\n"
    )
    lines.append("## Conclusion\n")
    lines.append(
        "The evidence above represents what the system could retrieve and verify; claims without "
        "a citation marker were excluded rather than asserted without support.\n"
    )
    return "\n".join(lines)


def offline_reasoner(*, system: str, user: str) -> str:
    task = _task_of(system)
    dispatch = {
        "research_plan": _plan,
        "query_generation": _query_generation,
        "evidence_extraction": _evidence_extraction,
        "source_comparison": _source_comparison,
        "fact_check": _fact_check,
        "synthesis": _synthesis,
    }
    fn = dispatch.get(task)
    if fn is None:
        return json.dumps({"note": f"offline provider has no handler for task '{task}'"})
    return fn(user)
