"use client";

import { Check, RefreshCw, X } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { ThreatChips } from "@/components/ThreatChips";
import { api } from "@/lib/api";

type Item = {
  id: string;
  request_id: string;
  user_id: string;
  prompt: string;
  risk: number;
  findings: any[];
  status: string;
  created_at: string;
};

export default function ReviewPage() {
  const [items, setItems] = useState<Item[]>([]);
  const [busy, setBusy] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const i = await api<Item[]>("/api/review/pending");
      setItems(i);
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 4000);
    return () => clearInterval(id);
  }, [refresh]);

  async function decide(rid: string, decision: "APPROVE" | "DENY") {
    setBusy(rid);
    try {
      await api(`/api/review/${rid}/decision`, {
        method: "POST",
        body: JSON.stringify({ decision, analyst: "demo-analyst" }),
      });
      await refresh();
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="space-y-6">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Review Queue</h1>
          <p className="text-muted text-sm">
            Borderline (70–90 risk) requests awaiting human analyst approval. Auto-allow after 30s timeout.
          </p>
        </div>
        <button onClick={refresh} className="btn">
          <RefreshCw className="w-4 h-4 inline mr-1" /> Refresh
        </button>
      </header>

      {items.length === 0 ? (
        <div className="panel-pad text-center text-muted py-12">
          No pending reviews. Trigger an ESCALATE-tier prompt in the{" "}
          <a className="text-primary" href="/sandbox">
            Sandbox
          </a>{" "}
          to populate this queue.
        </div>
      ) : (
        <ul className="space-y-3">
          {items.map((it) => (
            <li key={it.id} className="panel-pad">
              <div className="flex items-center justify-between gap-2 flex-wrap">
                <div className="flex items-center gap-2">
                  <span className="chip border-warning/50 text-warning bg-warning/10">
                    risk {it.risk}
                  </span>
                  <span className="text-xs text-muted font-mono">
                    {it.user_id} · {it.request_id.slice(-8)}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => decide(it.request_id, "APPROVE")}
                    disabled={busy === it.request_id}
                    className="btn-primary"
                  >
                    <Check className="w-4 h-4 inline mr-1" /> Approve
                  </button>
                  <button
                    onClick={() => decide(it.request_id, "DENY")}
                    disabled={busy === it.request_id}
                    className="btn-danger"
                  >
                    <X className="w-4 h-4 inline mr-1" /> Deny
                  </button>
                </div>
              </div>
              <div className="mt-3 text-sm text-text/80 whitespace-pre-wrap">
                {it.prompt}
              </div>
              <div className="mt-2">
                <ThreatChips
                  categories={(it.findings || []).map((f: any) => f.category)}
                />
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
