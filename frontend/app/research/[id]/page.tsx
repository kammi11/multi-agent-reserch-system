"use client";

import { useEffect, useState } from "react";
import SessionDashboard from "@/components/SessionDashboard";
import { getSession } from "@/lib/api";
import type { ResearchSession } from "@/lib/types";

export default function SessionByIdPage({ params }: { params: { id: string } }) {
  const [session, setSession] = useState<ResearchSession | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getSession(params.id).then(setSession).catch((e) => setError(String(e)));
  }, [params.id]);

  if (error) return <p style={{ color: "var(--fail)" }}>{error}</p>;
  if (!session) return <p className="muted">Loading…</p>;
  return <SessionDashboard session={session} />;
}
