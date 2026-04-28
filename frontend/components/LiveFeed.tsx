"use client";

import { AnimatePresence, motion } from "framer-motion";
import { useLiveEvents } from "@/lib/sse";
import { ModelBadge } from "./ModelBadge";
import { ThreatChips, VerdictChip } from "./ThreatChips";

export function LiveFeed({ limit = 20 }: { limit?: number }) {
  const events = useLiveEvents(limit);
  const requests = events.filter((e) => e.type === "request");

  return (
    <div className="panel-pad max-h-[700px] overflow-y-auto">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-semibold tracking-wide uppercase text-muted">
          Live Requests
        </h2>
        <div className="flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full bg-success animate-pulse"></span>
          <span className="text-[11px] text-muted">streaming</span>
        </div>
      </div>
      {requests.length === 0 ? (
        <div className="text-sm text-muted py-12 text-center">
          No requests yet. Try the <a href="/sandbox" className="text-primary">Sandbox</a>.
        </div>
      ) : (
        <ul className="space-y-2">
          <AnimatePresence initial={false}>
            {requests.map((e) => (
              <motion.li
                key={e.request_id}
                initial={{ opacity: 0, y: -8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                className="border border-line rounded-lg p-3 bg-panel2"
              >
                <div className="flex items-center justify-between gap-2 flex-wrap">
                  <div className="flex items-center gap-2 flex-wrap">
                    <VerdictChip verdict={e.verdict} />
                    <VerdictChip verdict={e.output_verdict} />
                    <span className="text-xs text-muted">
                      risk <span className="text-text font-mono">{e.risk}</span> /
                      out <span className="text-text font-mono">{e.output_risk}</span>
                    </span>
                    <ModelBadge model={e.model_used} fallback={e.fallback} />
                  </div>
                  <span className="text-[11px] text-muted font-mono">
                    {e.user} · {e.latency_ms}ms
                  </span>
                </div>
                <div className="mt-1 text-xs text-text/80 truncate">
                  {e.prompt_preview}
                </div>
                <div className="mt-2">
                  <ThreatChips categories={[...(e.categories_in || []), ...(e.categories_out || [])]} />
                </div>
              </motion.li>
            ))}
          </AnimatePresence>
        </ul>
      )}
    </div>
  );
}
