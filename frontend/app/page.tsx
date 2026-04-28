"use client";

import { motion } from "framer-motion";
import { useEffect, useMemo, useState } from "react";
import { LiveFeed } from "@/components/LiveFeed";
import { RiskMeter } from "@/components/RiskMeter";
import { useLiveEvents } from "@/lib/sse";
import { api } from "@/lib/api";

type Summary = {
  total: number;
  blocked: number;
  masked: number;
  escalated: number;
  block_rate: number;
  avg_risk: number;
  avg_latency_ms: number;
};

export default function HomePage() {
  const events = useLiveEvents(40);
  const last = events.find((e) => e.type === "request");
  const [summary, setSummary] = useState<Summary | null>(null);

  useEffect(() => {
    let mounted = true;
    const tick = async () => {
      try {
        const s = await api<Summary>("/api/analytics/summary");
        if (mounted) setSummary(s);
      } catch {
        /* ignore */
      }
    };
    tick();
    const id = setInterval(tick, 6000);
    return () => {
      mounted = false;
      clearInterval(id);
    };
  }, [events.length]);

  const pulseRisk = useMemo(() => {
    if (last?.risk !== undefined) return last.risk;
    return Math.round(summary?.avg_risk ?? 0);
  }, [last, summary]);

  return (
    <div className="space-y-6">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Live Defense</h1>
          <p className="text-muted text-sm">
            Real-time agentic scanning of every LLM request flowing through SentinelGuard.
          </p>
        </div>
      </header>

      <section className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        <div className="panel-pad lg:col-span-1 flex flex-col items-center justify-center">
          <RiskMeter value={pulseRisk} label="latest risk" />
        </div>
        {[
          { label: "Total Requests", value: summary?.total ?? 0, color: "text-text" },
          { label: "Blocked", value: summary?.blocked ?? 0, color: "text-danger" },
          { label: "Masked", value: summary?.masked ?? 0, color: "text-warning" },
        ].map((card) => (
          <motion.div
            key={card.label}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="panel-pad flex flex-col justify-center"
          >
            <div className="text-[11px] uppercase tracking-widest text-muted">
              {card.label}
            </div>
            <div className={`mt-2 text-3xl font-bold ${card.color}`}>
              {card.value}
            </div>
            <div className="text-[11px] text-muted mt-1">
              block rate {summary?.block_rate ?? 0}% · avg latency{" "}
              {Math.round(summary?.avg_latency_ms ?? 0)}ms
            </div>
          </motion.div>
        ))}
      </section>

      <section className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2">
          <LiveFeed limit={25} />
        </div>
        <div className="space-y-4">
          <div className="panel-pad">
            <h3 className="text-sm font-semibold uppercase tracking-wide text-muted mb-3">
              Pipeline
            </h3>
            <ol className="space-y-2 text-xs">
              {[
                "1. Context Builder",
                "2. Threat Detection (5 parallel scanners)",
                "3. Risk Aggregator (0–100)",
                "4. Decision Gate (4 tiers)",
                "5. Review Queue (HITL)",
                "6. OPA Policy",
                "7. Model Router (+fallback)",
                "8. LLM Invocation",
                "9. Response Sanitizer (5 parallel)",
                "10. Output Decision",
                "11. Reporting + Adaptive Risk",
              ].map((s) => (
                <li key={s} className="flex items-center gap-2 text-text/80">
                  <span className="w-1.5 h-1.5 rounded-full bg-primary"></span>
                  {s}
                </li>
              ))}
            </ol>
          </div>
          <div className="panel-pad">
            <h3 className="text-sm font-semibold uppercase tracking-wide text-muted mb-3">
              Quick Actions
            </h3>
            <div className="grid grid-cols-2 gap-2 text-xs">
              <a href="/sandbox" className="btn-primary text-center">
                Run a demo attack
              </a>
              <a href="/review" className="btn text-center">
                Open Review Queue
              </a>
              <a href="/analytics" className="btn text-center">
                Analytics
              </a>
              <a href="/policies" className="btn text-center">
                Policies
              </a>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
