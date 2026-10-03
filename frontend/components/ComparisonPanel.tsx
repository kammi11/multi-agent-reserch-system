import type { ClaimVerification, ContradictionReport, Source } from "@/lib/types";

export default function ComparisonPanel({
  contradictions,
  verifications,
  sources,
}: {
  contradictions: ContradictionReport[];
  verifications: ClaimVerification[];
  sources: Source[];
}) {
  const titleBySource = Object.fromEntries(sources.map((s) => [s.id, s.title]));

  return (
    <div className="stack">
      <div className="stack">
        <h3 style={{ margin: "0 0 4px" }}>Source Agreement</h3>
        {contradictions.length === 0 && (
          <p className="muted small">
            No overlapping claim clusters across sources were found to compare in this session.
          </p>
        )}
        {contradictions.map((c, i) => (
          <div className="card" key={i}>
            <div className="row wrap" style={{ justifyContent: "space-between" }}>
              <strong>{c.claim}</strong>
              <span className={`badge ${c.agreement_level}`}>{c.agreement_level.replace("_", " ")}</span>
            </div>
            <p className="small muted" style={{ marginBottom: 4 }}>{c.explanation}</p>
            {c.remaining_uncertainty && (
              <p className="small" style={{ color: "var(--warn)" }}>{c.remaining_uncertainty}</p>
            )}
            <div className="small muted">
              {c.supporting_sources.length > 0 && (
                <div>Supporting: {c.supporting_sources.map((id) => titleBySource[id] || id).join(", ")}</div>
              )}
              {c.contradicting_sources.length > 0 && (
                <div>Contradicting: {c.contradicting_sources.map((id) => titleBySource[id] || id).join(", ")}</div>
              )}
            </div>
          </div>
        ))}
      </div>

      <div className="stack">
        <h3 style={{ margin: "0 0 4px" }}>Claim Verification</h3>
        {verifications.map((v, i) => (
          <div className="card" key={i}>
            <div className="row wrap" style={{ justifyContent: "space-between" }}>
              <span className="small">{v.claim}</span>
              <span className={`badge ${v.verdict === "pass" ? "pass" : "fail"}`}>{v.verdict}</span>
            </div>
            <p className="small muted" style={{ margin: "6px 0 0" }}>{v.notes}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
