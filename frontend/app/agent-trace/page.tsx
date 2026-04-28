"use client";

import { useLiveEvents } from "@/lib/sse";
import { motion } from "framer-motion";
import { useMemo } from "react";

type AgentStep = {
  phase?: string;
  tool?: string;
  observation?: string;
};

type Sentinel = {
  agent_steps?: AgentStep[];
  agent_findings?: { agent?: string; claim?: string; confidence?: number }[];
  explanation?: {
    headline?: string;
    user_facing_message?: string;
    confidence?: number;
  };
  agentic_trace_version?: string;
};

export default function AgentTracePage() {
  const events = useLiveEvents(50);
  const s = useMemo((): Sentinel | undefined => {
    for (const ev of events) {
      const e = ev as { sentinel?: Sentinel };
      if (e.sentinel?.agent_steps?.length || e.sentinel?.explanation) {
        return e.sentinel;
      }
    }
    return (events[0] as { sentinel?: Sentinel } | undefined)?.sentinel;
  }, [events]);

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold">Agent trace</h1>
        <p className="text-muted text-sm">
          Live SSE view of specialist steps (Sentinel-X v2). Use Sandbox to send a request, then
          check the latest event or API <code>sentinel</code> block.
        </p>
      </header>
      {s?.explanation && (
        <motion.div
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          className="panel-pad space-y-2"
        >
          <div className="text-xs uppercase text-muted">Explanation card</div>
          <div className="text-lg font-medium">{s.explanation.headline}</div>
          <p className="text-sm text-muted">{s.explanation.user_facing_message}</p>
          <div className="text-xs text-muted">
            confidence: {s.explanation.confidence?.toFixed?.(2) ?? "—"} · trace v
            {s.agentic_trace_version ?? "?"}
          </div>
        </motion.div>
      )}
      <div className="panel-pad">
        <div className="text-xs uppercase text-muted mb-2">Agent steps (last event)</div>
        <ul className="space-y-2">
          {(s?.agent_steps ?? []).map((st, i) => (
            <li
              key={i}
              className="border border-border rounded-md p-2 text-sm font-mono bg-card/50"
            >
              <span className="text-accent">[{st.phase ?? "?"}]</span> {st.tool ?? "—"}:{" "}
              <span className="text-muted">{(st.observation ?? "").slice(0, 200)}</span>
            </li>
          ))}
          {!(s?.agent_steps?.length) && (
            <li className="text-muted text-sm">No agent steps in the last event yet.</li>
          )}
        </ul>
      </div>
      <div className="panel-pad">
        <div className="text-xs uppercase text-muted mb-2">Agent findings (blackboard)</div>
        <ul className="space-y-1 text-sm">
          {(s?.agent_findings ?? []).map((f, i) => (
            <li key={i}>
              <strong>{f.agent}</strong>: {f.claim}{" "}
              <span className="text-muted">(c={f.confidence?.toFixed?.(2) ?? "—"})</span>
            </li>
          ))}
          {!(s?.agent_findings?.length) && (
            <li className="text-muted">No findings on last event.</li>
          )}
        </ul>
      </div>
    </div>
  );
}
