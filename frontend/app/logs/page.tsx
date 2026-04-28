"use client";

import { useEffect, useState } from "react";
import { ModelBadge } from "@/components/ModelBadge";
import { ThreatChips, VerdictChip } from "@/components/ThreatChips";
import { api } from "@/lib/api";

type Row = {
  id: string;
  user_id: string;
  verdict: string;
  output_verdict: string;
  risk: number;
  output_risk: number;
  model_used: string;
  fallback: boolean;
  latency_ms: number;
  prompt_preview: string;
  response_preview: string;
  created_at: string;
};

export default function LogsPage() {
  const [rows, setRows] = useState<Row[]>([]);

  useEffect(() => {
    const tick = async () => {
      try {
        const r = await api<Row[]>("/api/analytics/recent?limit=80");
        setRows(r);
      } catch {
        /* ignore */
      }
    };
    tick();
    const id = setInterval(tick, 6000);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold">Logs Timeline</h1>
        <p className="text-muted text-sm">Most recent {rows.length} requests.</p>
      </header>

      <ol className="space-y-2">
        {rows.map((r) => (
          <li key={r.id} className="panel-pad">
            <div className="flex items-center justify-between gap-2 flex-wrap">
              <div className="flex items-center gap-2 flex-wrap">
                <VerdictChip verdict={r.verdict} />
                <VerdictChip verdict={r.output_verdict} />
                <span className="text-xs text-muted">
                  risk <span className="text-text font-mono">{r.risk}</span> /
                  out <span className="text-text font-mono">{r.output_risk}</span>
                </span>
                <ModelBadge model={r.model_used} fallback={r.fallback} />
              </div>
              <span className="text-[11px] font-mono text-muted">
                {r.user_id} · {r.latency_ms}ms · {new Date(r.created_at).toLocaleTimeString()}
              </span>
            </div>
            <div className="mt-2 text-xs text-text/80">
              <div className="text-muted">prompt:</div>
              <div className="whitespace-pre-wrap">{r.prompt_preview}</div>
            </div>
            {r.response_preview && (
              <div className="mt-2 text-xs text-text/80">
                <div className="text-muted">response:</div>
                <div className="whitespace-pre-wrap">{r.response_preview}</div>
              </div>
            )}
          </li>
        ))}
      </ol>
    </div>
  );
}
