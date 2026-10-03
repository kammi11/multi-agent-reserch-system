import type { ResearchDepth, ResearchSession } from "./types";

export interface AgentStepEvent {
  node: string;
  agent: string;
  status: string;
  duration_ms: number;
  output_summary: string;
  error?: string | null;
}

export interface StateSnapshotEvent {
  sources_count: number;
  evidence_count: number;
  iteration: number;
}

export type StreamCallbacks = {
  onSessionStarted?: (sessionId: string) => void;
  onAgentStep?: (evt: AgentStepEvent) => void;
  onSnapshot?: (evt: StateSnapshotEvent) => void;
  onComplete?: (session: ResearchSession) => void;
  onError?: (message: string) => void;
};

/**
 * Consumes the backend's Server-Sent Events stream by hand (rather than
 * the browser EventSource API) because EventSource only supports GET;
 * starting research needs a POST body. This parses the same
 * `event:`/`data:` framing SSE uses.
 */
export async function streamResearch(
  question: string,
  depth: ResearchDepth,
  callbacks: StreamCallbacks,
  signal?: AbortSignal
): Promise<void> {
  const resp = await fetch("/api/research/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, research_depth: depth, source_preferences: [] }),
    signal,
  });
  if (!resp.body) throw new Error("No response body from research stream");

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const events = buffer.split("\n\n");
    buffer = events.pop() || "";

    for (const raw of events) {
      const lines = raw.split("\n");
      let eventName = "message";
      let data = "";
      for (const line of lines) {
        if (line.startsWith("event:")) eventName = line.slice(6).trim();
        if (line.startsWith("data:")) data += line.slice(5).trim();
      }
      if (!data) continue;
      try {
        const parsed = JSON.parse(data);
        switch (eventName) {
          case "session_started":
            callbacks.onSessionStarted?.(parsed.session_id);
            break;
          case "agent_step":
            callbacks.onAgentStep?.(parsed);
            break;
          case "state_snapshot":
            callbacks.onSnapshot?.(parsed);
            break;
          case "research_complete":
            callbacks.onComplete?.(parsed as ResearchSession);
            break;
          case "error":
            callbacks.onError?.(parsed.error);
            break;
        }
      } catch {
        // ignore malformed partial frame
      }
    }
  }
}

export async function getSession(sessionId: string): Promise<ResearchSession> {
  const resp = await fetch(`/api/research/${sessionId}`);
  if (!resp.ok) throw new Error(`Failed to load session ${sessionId}`);
  return resp.json();
}

export async function listSessions(): Promise<ResearchSession[]> {
  const resp = await fetch(`/api/sessions`);
  if (!resp.ok) throw new Error("Failed to load session history");
  return resp.json();
}
