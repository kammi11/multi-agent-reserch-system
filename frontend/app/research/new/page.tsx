"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
import AgentTimeline from "@/components/AgentTimeline";
import SessionDashboard from "@/components/SessionDashboard";
import { streamResearch, type AgentStepEvent } from "@/lib/api";
import type { ResearchDepth, ResearchSession } from "@/lib/types";

export default function NewResearchPage() {
  return (
    <Suspense fallback={<p className="muted">Loading…</p>}>
      <NewResearchInner />
    </Suspense>
  );
}

function NewResearchInner() {
  const params = useSearchParams();
  const question = params.get("q") || "";
  const depth = (params.get("depth") as ResearchDepth) || "standard";

  const [steps, setSteps] = useState<AgentStepEvent[]>([]);
  const [snapshot, setSnapshot] = useState({ sources_count: 0, evidence_count: 0, iteration: 0 });
  const [session, setSession] = useState<ResearchSession | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState(true);
  const started = useRef(false);

  useEffect(() => {
    if (started.current || !question) return;
    started.current = true;

    const controller = new AbortController();
    streamResearch(
      question,
      depth,
      {
        onAgentStep: (evt) => setSteps((prev) => [...prev, evt]),
        onSnapshot: (evt) => setSnapshot(evt),
        onComplete: (s) => {
          setSession(s);
          setRunning(false);
        },
        onError: (msg) => {
          setError(msg);
          setRunning(false);
        },
      },
      controller.signal
    ).catch((err) => {
      if (err.name !== "AbortError") {
        setError(String(err));
        setRunning(false);
      }
    });

    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [question, depth]);

  if (!question) {
    return <p className="muted">No research question provided.</p>;
  }

  if (session) {
    return <SessionDashboard session={session} />;
  }

  return (
    <div className="stack">
      <div className="stack" style={{ gap: 4 }}>
        <h1 style={{ margin: 0, fontSize: 22 }}>{question}</h1>
        <p className="small muted" style={{ margin: 0 }}>
          Depth: {depth} · {snapshot.sources_count} sources found · {snapshot.evidence_count} evidence items ·
          iteration {snapshot.iteration}
        </p>
      </div>

      <div className="card">
        <AgentTimeline steps={steps} running={running} />
        {error && (
          <p className="small" style={{ color: "var(--fail)", marginTop: 12 }}>
            {error}
          </p>
        )}
      </div>
    </div>
  );
}
