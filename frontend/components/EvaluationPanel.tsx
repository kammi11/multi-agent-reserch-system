import type { EvaluationReport } from "@/lib/types";

function pct(n: number | null | undefined): string {
  if (n === null || n === undefined) return "—";
  return `${Math.round(n * 100)}%`;
}

export default function EvaluationPanel({ evaluation }: { evaluation: EvaluationReport }) {
  const metrics: { label: string; value: string }[] = [
    { label: "Citation Completeness", value: pct(evaluation.citation_completeness) },
    { label: "Citation Correctness", value: pct(evaluation.citation_correctness) },
    { label: "Groundedness", value: pct(evaluation.groundedness) },
    { label: "Answer Relevance", value: pct(evaluation.answer_relevance) },
    { label: "Source Diversity", value: pct(evaluation.source_diversity) },
    { label: "Unsupported Claim Rate", value: pct(evaluation.unsupported_claim_rate) },
    { label: "Retrieval Hit Rate", value: pct(evaluation.retrieval_hit_rate) },
  ];

  return (
    <div className="stack">
      <div className="grid-metrics">
        {metrics.map((m) => (
          <div className="metric-box" key={m.label}>
            <div className="metric-value">{m.value}</div>
            <div className="metric-label">{m.label}</div>
          </div>
        ))}
      </div>

      <div className="grid-2">
        <div className="metric-box">
          <div className="metric-value">{evaluation.sources_analyzed}</div>
          <div className="metric-label">Sources Analyzed</div>
        </div>
        <div className="metric-box">
          <div className="metric-value">{evaluation.sources_used}</div>
          <div className="metric-label">Sources Cited</div>
        </div>
        <div className="metric-box">
          <div className="metric-value">{evaluation.research_iterations}</div>
          <div className="metric-label">Research Iterations</div>
        </div>
        <div className="metric-box">
          <div className="metric-value">{evaluation.contradictions_detected}</div>
          <div className="metric-label">
            Contradictions ({evaluation.contradictions_unresolved} unresolved)
          </div>
        </div>
        <div className="metric-box">
          <div className="metric-value">{evaluation.research_duration_seconds}s</div>
          <div className="metric-label">Research Duration</div>
        </div>
      </div>

      {evaluation.notes.length > 0 && (
        <div className="card small muted">
          <strong style={{ display: "block", marginBottom: 6, color: "var(--text)" }}>
            Evaluation notes
          </strong>
          <ul style={{ margin: 0, paddingLeft: 18 }}>
            {evaluation.notes.map((n, i) => (
              <li key={i}>{n}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
