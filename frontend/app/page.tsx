"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import type { ResearchDepth } from "@/lib/types";

const DEPTHS: { value: ResearchDepth; label: string; hint: string; time: string }[] = [
  { value: "quick", label: "Quick scan", hint: "A focused overview", time: "~1 min" },
  { value: "standard", label: "Balanced", hint: "A wider evidence review", time: "~3 min" },
  { value: "deep", label: "Deep research", hint: "More angles and source checks", time: "~5 min" },
];
const EXAMPLES = [
  "What does the evidence say about sleep and memory?",
  "How effective are heat pumps in cold climates?",
  "What are the tradeoffs of retrieval-augmented generation?",
];

export default function HomePage() {
  const router = useRouter();
  const [question, setQuestion] = useState("");
  const [depth, setDepth] = useState<ResearchDepth>("standard");
  const [provider, setProvider] = useState<{ llm_provider: string; search_provider: string } | null>(null);

  useEffect(() => {
    fetch("/api/health").then((r) => r.json()).then(setProvider).catch(() => setProvider(null));
  }, []);

  function startResearch() {
    if (question.trim()) router.push(`/research/new?${new URLSearchParams({ q: question.trim(), depth })}`);
  }

  const offline = provider?.llm_provider === "offline" || provider?.search_provider === "offline";

  return (
    <div className="home-page">
      <section className="hero-grid">
        <div className="hero-copy">
          <div className="eyebrow"><span className="eyebrow-dot" /> Research, with receipts</div>
          <h1>Good questions<br /><em>deserve better answers.</em></h1>
          <p className="hero-subtitle">Turn a question into a clear, source-backed briefing. ResearchPilot gathers evidence, checks claims, and shows you where sources agree.</p>
          <div className="trust-row">
            <span><b>01</b> Find credible sources</span>
            <span><b>02</b> Check the evidence</span>
            <span><b>03</b> Cite every finding</span>
          </div>
        </div>

        <div className="research-card">
          <div className="card-heading">
            <div><span className="eyebrow muted-eyebrow">YOUR NEXT BRIEFING</span><h2>What would you like to know?</h2></div>
            <span className="sparkle" aria-hidden="true">✳</span>
          </div>
          <label className="sr-only" htmlFor="question">Research question</label>
          <textarea id="question" rows={4} maxLength={1000} placeholder="Ask a specific question. For example, ‘How does remote work affect team productivity?’" value={question} onChange={(e) => setQuestion(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) startResearch(); }} />
          <div className="examples-label">NEED A STARTING POINT?</div>
          <div className="example-list">{EXAMPLES.map((q) => <button className="example-chip" key={q} onClick={() => setQuestion(q)} type="button">{q}<span>↗</span></button>)}</div>
          <div className="depth-header"><span className="examples-label">RESEARCH DEPTH</span><span className="small muted">Choose your level of detail</span></div>
          <div className="depth-options">
            {DEPTHS.map((d, i) => <button type="button" key={d.value} className={`depth-option ${depth === d.value ? "selected" : ""}`} onClick={() => setDepth(d.value)} aria-pressed={depth === d.value}>
              <span className="depth-radio">{depth === d.value && <i />}</span><span className="depth-copy"><strong>{d.label}</strong><small>{d.hint}</small></span><span className="depth-time">{d.time}</span>
            </button>)}
          </div>
          <button className="primary launch-button" disabled={!question.trim()} onClick={startResearch}>Start researching <span>→</span></button>
          <div className="card-footnote"><span>⌘ Enter</span> to start <span className="footnote-divider">·</span> Sources linked in every report</div>
        </div>
      </section>

      <section className="below-hero">
        <div className="feature-intro"><span className="eyebrow muted-eyebrow">BUILT FOR CLARITY</span><h2>See how the answer<br />comes together.</h2></div>
        <div className="feature-card"><span className="feature-icon">⌕</span><h3>Evidence first</h3><p>Search across sources and extract the details that answer your question.</p></div>
        <div className="feature-card"><span className="feature-icon">✓</span><h3>Claims checked</h3><p>Keep findings grounded in what their cited source actually says.</p></div>
        <div className="feature-card"><span className="feature-icon">↗</span><h3>Traceable results</h3><p>Follow citations back to the original sources and compare perspectives.</p></div>
      </section>
      <div className={`provider-note ${offline ? "demo-note" : ""}`}><span className="provider-indicator" />{offline ? "Demo mode · using local sample research and extractive summaries" : provider ? `Configured · ${provider.search_provider} search with ${provider.llm_provider} reasoning` : "Checking research providers…"}</div>
    </div>
  );
}
