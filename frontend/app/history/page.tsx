"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { listSessions } from "@/lib/api";
import type { ResearchSession } from "@/lib/types";

export default function HistoryPage() {
  const [sessions, setSessions] = useState<ResearchSession[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listSessions().then(setSessions).catch((e) => setError(String(e)));
  }, []);

  return (
    <div className="stack">
      <h1 style={{ margin: 0, fontSize: 24 }}>Research History</h1>
      {error && <p style={{ color: "var(--fail)" }}>{error}</p>}
      {sessions === null && !error && <p className="muted">Loading…</p>}
      {sessions?.length === 0 && <p className="muted">No research sessions yet.</p>}
      <div className="stack">
        {sessions?.map((s) => (
          <Link key={s.session_id} href={`/research/${s.session_id}`} className="card" style={{ textDecoration: "none", color: "inherit" }}>
            <div style={{ fontWeight: 600 }}>{s.user_question}</div>
            <div className="small muted">
              {s.created_at} · {s.status} · {s.sources.length} sources ·{" "}
              {s.evaluation ? `${Math.round(s.evaluation.citation_completeness * 100)}% citation completeness` : ""}
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
