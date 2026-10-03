"""
Structured schemas shared across agents, tools, the graph state, and the
API layer. Nothing in the system passes unstructured strings between
agents where a structured object is possible — this is what makes the
comparator / fact-checker / citation-verifier actually able to reason
about claims and sources rather than re-parsing prose.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ResearchDepth(str, Enum):
    quick = "quick"
    standard = "standard"
    deep = "deep"


class SourceType(str, Enum):
    academic = "academic"
    news = "news"
    government = "government"
    official_documentation = "official_documentation"
    general_web = "general_web"


class AgreementLevel(str, Enum):
    agreement = "agreement"
    partial_agreement = "partial_agreement"
    contradiction = "contradiction"
    different_scope = "different_scope"
    insufficient_data = "insufficient_data"


class ResearchPlan(BaseModel):
    research_question: str
    objectives: list[str] = Field(default_factory=list)
    subquestions: list[str] = Field(default_factory=list)
    search_strategy: list[str] = Field(default_factory=list)
    required_source_types: list[SourceType] = Field(default_factory=list)
    research_depth: ResearchDepth = ResearchDepth.standard


class Source(BaseModel):
    id: str
    title: str
    url: str
    domain: str
    publisher: Optional[str] = None
    author: Optional[str] = None
    published_date: Optional[str] = None
    retrieved_at: str = Field(default_factory=_now)
    content: str = ""
    source_type: SourceType = SourceType.general_web
    query_used: Optional[str] = None


class SourceQuality(BaseModel):
    source_id: str
    authority: float
    relevance: float
    recency: float
    evidence_quality: float
    inferred_type: SourceType
    overall_confidence: float
    reason: str


class EvidenceItem(BaseModel):
    id: str
    claim: str
    evidence: str
    source_id: str
    source_location: str = "full text"
    confidence: float


class ContradictionReport(BaseModel):
    claim: str
    supporting_sources: list[str] = Field(default_factory=list)
    contradicting_sources: list[str] = Field(default_factory=list)
    agreement_level: AgreementLevel
    explanation: str
    remaining_uncertainty: str = ""


class Citation(BaseModel):
    marker: str  # e.g. "[1]"
    source_id: str
    claim_snippet: str


class ClaimVerification(BaseModel):
    claim: str
    citation_markers: list[str]
    has_supporting_evidence: bool
    is_overstated: bool
    verdict: str  # "pass" | "fail" | "revised"
    notes: str = ""


class SourceQualitySummary(BaseModel):
    authority: float
    recency: float
    diversity: float
    primary_source_ratio: float


class EvaluationReport(BaseModel):
    retrieval_hit_rate: Optional[float] = None
    citation_completeness: float
    citation_correctness: float
    groundedness: float
    answer_relevance: float
    source_diversity: float
    unsupported_claim_rate: float
    contradictions_detected: int
    contradictions_unresolved: int
    research_iterations: int
    sources_analyzed: int
    sources_used: int
    research_duration_seconds: float
    notes: list[str] = Field(default_factory=list)


class AgentTrace(BaseModel):
    agent: str
    start_time: str
    end_time: str
    duration_ms: float
    tool: Optional[str] = None
    input_summary: str = ""
    output_summary: str = ""
    status: str = "ok"
    error: Optional[str] = None


class ResearchRequest(BaseModel):
    question: str
    research_depth: ResearchDepth = ResearchDepth.standard
    source_preferences: list[SourceType] = Field(default_factory=list)


class ResearchSession(BaseModel):
    session_id: str
    user_question: str
    created_at: str = Field(default_factory=_now)
    status: str = "pending"  # pending | running | completed | failed
    research_depth: ResearchDepth = ResearchDepth.standard
    research_plan: Optional[ResearchPlan] = None
    sources: list[Source] = Field(default_factory=list)
    source_quality: list[SourceQuality] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    contradictions: list[ContradictionReport] = Field(default_factory=list)
    claim_verifications: list[ClaimVerification] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    final_answer: str = ""
    evaluation: Optional[EvaluationReport] = None
    execution_trace: list[AgentTrace] = Field(default_factory=list)
    research_iterations: int = 0
