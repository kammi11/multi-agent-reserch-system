import type { EvidenceItem, Source, SourceQuality } from "@/lib/types";

export default function SourcesPanel({
  sources,
  sourceQuality,
  evidence,
}: {
  sources: Source[];
  sourceQuality: SourceQuality[];
  evidence: EvidenceItem[];
}) {
  const qualityBySource = Object.fromEntries(sourceQuality.map((q) => [q.source_id, q]));
  const evidenceBySource: Record<string, EvidenceItem[]> = {};
  for (const e of evidence) {
    (evidenceBySource[e.source_id] ||= []).push(e);
  }

  if (sources.length === 0) return <p className="muted">No sources retrieved yet.</p>;

  return (
    <div className="stack">
      {sources.map((s) => {
        const q = qualityBySource[s.id];
        const ev = evidenceBySource[s.id] || [];
        return (
          <div className="card" key={s.id}>
            <div className="row wrap" style={{ justifyContent: "space-between" }}>
              <div>
                <div style={{ fontWeight: 600 }}>{s.title}</div>
                <div className="small muted">
                  {s.publisher || s.domain} · {s.published_date || "date unknown"} ·{" "}
                  <span style={{ textTransform: "capitalize" }}>{s.source_type.replace("_", " ")}</span>
                </div>
              </div>
              {q && (
                <div className="small" style={{ textAlign: "right" }}>
                  <div>
                    confidence <strong>{Math.round(q.overall_confidence * 100)}%</strong>
                  </div>
                  <div className="muted">
                    authority {Math.round(q.authority * 100)}% · recency {Math.round(q.recency * 100)}%
                  </div>
                </div>
              )}
            </div>
            <a className="source-link small" href={s.url} target="_blank" rel="noreferrer">
              {s.url}
            </a>
            {ev.length > 0 && (
              <div className="stack" style={{ marginTop: 12, gap: 6 }}>
                <span className="small muted">Extracted evidence ({ev.length})</span>
                {ev.map((e) => (
                  <div key={e.id} className="small" style={{ paddingLeft: 12, borderLeft: "2px solid var(--border)" }}>
                    {e.evidence}
                  </div>
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
