export type ResearchDepth = "quick" | "standard" | "deep";

export interface ResearchPlan {
  research_question: string;
  objectives: string[];
  subquestions: string[];
  search_strategy: string[];
  required_source_types: string[];
  research_depth: ResearchDepth;
}

export interface Source {
  id: string;
  title: string;
  url: string;
  domain: string;
  publisher?: string | null;
  author?: string | null;
  published_date?: string | null;
  retrieved_at: string;
  content: string;
  source_type: string;
  query_used?: string | null;
}

export interface SourceQuality {
  source_id: string;
  authority: number;
  relevance: number;
  recency: number;
  evidence_quality: number;
  inferred_type: string;
  overall_confidence: number;
  reason: string;
}

export interface EvidenceItem {
  id: string;
  claim: string;
  evidence: string;
  source_id: string;
  source_location: string;
  confidence: number;
}

export interface ContradictionReport {
  claim: string;
  supporting_sources: string[];
  contradicting_sources: string[];
  agreement_level: string;
  explanation: string;
  remaining_uncertainty: string;
}

export interface Citation {
  marker: string;
  source_id: string;
  claim_snippet: string;
}

export interface ClaimVerification {
  claim: string;
  citation_markers: string[];
  has_supporting_evidence: boolean;
  is_overstated: boolean;
  verdict: "pass" | "fail" | "revised";
  notes: string;
}

export interface EvaluationReport {
  retrieval_hit_rate: number | null;
  citation_completeness: number;
  citation_correctness: number;
  groundedness: number;
  answer_relevance: number;
  source_diversity: number;
  unsupported_claim_rate: number;
  contradictions_detected: number;
  contradictions_unresolved: number;
  research_iterations: number;
  sources_analyzed: number;
  sources_used: number;
  research_duration_seconds: number;
  notes: string[];
}

export interface AgentTrace {
  agent: string;
  start_time: string;
  end_time: string;
  duration_ms: number;
  tool?: string | null;
  input_summary: string;
  output_summary: string;
  status: string;
  error?: string | null;
}

export interface ResearchSession {
  session_id: string;
  user_question: string;
  created_at: string;
  status: "pending" | "running" | "completed" | "failed";
  research_depth: ResearchDepth;
  research_plan?: ResearchPlan | null;
  sources: Source[];
  source_quality: SourceQuality[];
  evidence: EvidenceItem[];
  contradictions: ContradictionReport[];
  claim_verifications: ClaimVerification[];
  citations: Citation[];
  final_answer: string;
  evaluation?: EvaluationReport | null;
  execution_trace: AgentTrace[];
  research_iterations: number;
}
