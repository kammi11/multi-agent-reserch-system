"use client";

import { useState } from "react";
import ReactMarkdown from "react-markdown";
import type { ResearchSession } from "@/lib/types";
import SourcesPanel from "./SourcesPanel";
import ComparisonPanel from "./ComparisonPanel";
import EvaluationPanel from "./EvaluationPanel";

const TABS = ["Report", "Sources", "Comparison", "Evaluation", "Trace"] as const;
type Tab = (typeof TABS)[number];

export default function SessionDashboard({ session }: { session: ResearchSession }) {
  const [tab, setTab] = useState<Tab>("Report");

  return (
    <div className="stack">
      <div className="stack" style={{ gap: 4 }}>
        <h1 style={{ margin: 0, fontSize: 24 }}>{session.user_question}</h1>
        <div className="small muted row wrap">
          <span>Depth: {session.research_depth}</span>
          <span>·</span>
          <span>{session.sources.length} sources</span>
          <span>·</span>
          <span>{session.citations.length} citations</span>
          <span>·</span>
          <span>Status: {session.status}</span>
          <span>·</span>
          <a className="source-link" href={`/api/research/${session.session_id}/export.md`}>
            export markdown
          </a>
          <span>·</span>
          <a className="source-link" href={`/api/research/${session.session_id}/export.json`}>
            export json
          </a>
        </div>
      </div>

      <div className="tabs">
        {TABS.map((t) => (
          <button key={t} className={`tab ${tab === t ? "active" : ""}`} onClick={() => setTab(t)}>
            {t}
          </button>
        ))}
      </div>

      {tab === "Report" && (
        <div className="report-body">
          <ReactMarkdown>{session.final_answer || "_No report generated._"}</ReactMarkdown>
        </div>
      )}

      {tab === "Sources" && (
        <SourcesPanel sources={session.sources} sourceQuality={session.source_quality} evidence={session.evidence} />
      )}

      {tab === "Comparison" && (
        <ComparisonPanel
          contradictions={session.contradictions}
          verifications={session.claim_verifications}
          sources={session.sources}
        />
      )}

      {tab === "Evaluation" &&
        (session.evaluation ? (
          <EvaluationPanel evaluation={session.evaluation} />
        ) : (
          <p className="muted">Evaluation not yet available.</p>
        ))}

      {tab === "Trace" && (
        <div className="stack">
          {session.execution_trace.map((t, i) => (
            <div className="card small" key={i}>
              <div className="row wrap" style={{ justifyContent: "space-between" }}>
                <strong>{t.agent}</strong>
                <span className="muted">{Math.round(t.duration_ms)}ms</span>
              </div>
              <div className="muted">in: {t.input_summary}</div>
              <div className="muted">out: {t.output_summary}</div>
              {t.error && <div style={{ color: "var(--fail)" }}>error: {t.error}</div>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
