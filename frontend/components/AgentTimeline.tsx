"use client";

import type { AgentStepEvent } from "@/lib/api";

const LABELS: Record<string, string> = {
  research_planner: "Understanding research question & creating plan",
  query_generator: "Generating search queries",
  web_search_agent: "Searching & collecting sources",
  source_quality_agent: "Evaluating source credibility",
  evidence_extraction_agent: "Extracting evidence",
  source_comparison_agent: "Comparing sources / detecting conflicts",
  fact_checking_agent: "Fact-checking claims",
  iteration_controller: "Insufficient evidence — running follow-up research",
  synthesis_agent: "Synthesizing findings & citations",
  evaluation_agent: "Evaluating final answer",
};

function icon(status: string) {
  if (status === "ok") return "✓";
  if (status === "partial_failure") return "!";
  return "✕";
}

export default function AgentTimeline({ steps, running }: { steps: AgentStepEvent[]; running: boolean }) {
  return (
    <div className="timeline">
      {steps.map((s, i) => (
        <div key={i} className={`timeline-item ${s.status}`}>
          <span className="status-icon">{icon(s.status)}</span>
          <span className="agent-name">{LABELS[s.agent] || s.agent}</span>
          <span className="detail">
            {s.output_summary} · {Math.round(s.duration_ms)}ms
          </span>
        </div>
      ))}
      {running && (
        <div className="timeline-item">
          <span className="status-icon">⋯</span>
          <span className="muted">Working…</span>
        </div>
      )}
    </div>
  );
}
