"use client";

import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
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

const COLORS = ["#FF7300", "#16a34a", "#f59e0b", "#dc2626", "#06b6d4", "#a855f7", "#84cc16"];

const tooltipContentStyle = {
  background: "#ffffff",
  border: "1px solid #e5e7eb",
  borderRadius: 8,
  fontSize: 12,
  color: "#1f2937",
} as const;

export default function AnalyticsPage() {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [byHour, setByHour] = useState<any[]>([]);
  const [topThreats, setTopThreats] = useState<any[]>([]);
  const [models, setModels] = useState<any[]>([]);
  const [topUsers, setTopUsers] = useState<any[]>([]);

  useEffect(() => {
    const tick = async () => {
      try {
        const [s, h, t, m, u] = await Promise.all([
          api<Summary>("/api/analytics/summary"),
          api<any[]>("/api/analytics/threats_by_hour"),
          api<any[]>("/api/analytics/top_threats"),
          api<any[]>("/api/analytics/model_usage"),
          api<any[]>("/api/analytics/top_risky_users"),
        ]);
        setSummary(s);
        setByHour(h);
        setTopThreats(t);
        setModels(m);
        setTopUsers(u);
      } catch {
        /* ignore */
      }
    };
    tick();
    const id = setInterval(tick, 8000);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold">Analytics</h1>
        <p className="text-muted text-sm">
          Aggregated security telemetry across all requests.
        </p>
      </header>

      <section className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          { label: "Total", value: summary?.total ?? 0, color: "text-text" },
          { label: "Blocked", value: summary?.blocked ?? 0, color: "text-danger" },
          { label: "Masked", value: summary?.masked ?? 0, color: "text-warning" },
          { label: "Escalated", value: summary?.escalated ?? 0, color: "text-warning" },
        ].map((c) => (
          <div key={c.label} className="panel-pad">
            <div className="text-[11px] uppercase tracking-widest text-muted">
              {c.label}
            </div>
            <div className={`mt-1 text-2xl font-bold ${c.color}`}>{c.value}</div>
          </div>
        ))}
      </section>

      <section className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="panel-pad">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-muted mb-3">
            Verdicts (last 24h)
          </h3>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={byHour}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
              <XAxis
                dataKey="hour"
                tickFormatter={(s: string) => s.slice(11, 16)}
                stroke="#6b7280"
                style={{ fontSize: 10 }}
              />
              <YAxis stroke="#6b7280" style={{ fontSize: 10 }} />
              <Tooltip contentStyle={tooltipContentStyle} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              <Bar dataKey="ALLOW" stackId="v" fill="#16a34a" />
              <Bar dataKey="MASK" stackId="v" fill="#f59e0b" />
              <Bar dataKey="ESCALATE" stackId="v" fill="#fb923c" />
              <Bar dataKey="BLOCK" stackId="v" fill="#dc2626" />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="panel-pad">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-muted mb-3">
            Top Threats
          </h3>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={topThreats} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
              <XAxis type="number" stroke="#6b7280" style={{ fontSize: 10 }} />
              <YAxis
                type="category"
                dataKey="category"
                stroke="#6b7280"
                style={{ fontSize: 10 }}
                width={140}
              />
              <Tooltip contentStyle={tooltipContentStyle} />
              <Bar dataKey="count" fill="#FF7300" />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="panel-pad">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-muted mb-3">
            Model Usage
          </h3>
          <ResponsiveContainer width="100%" height={240}>
            <PieChart>
              <Pie
                data={models}
                dataKey="count"
                nameKey="model"
                cx="50%"
                cy="50%"
                outerRadius={80}
                label
              >
                {models.map((_, i) => (
                  <Cell key={i} fill={COLORS[i % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip contentStyle={tooltipContentStyle} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
            </PieChart>
          </ResponsiveContainer>
        </div>

        <div className="panel-pad">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-muted mb-3">
            Top Risky Users (Risk Graph)
          </h3>
          {topUsers.length === 0 ? (
            <div className="text-sm text-muted text-center py-12">
              No users yet
            </div>
          ) : (
            <ul className="space-y-2">
              {topUsers.map((u) => (
                <li
                  key={u.user_id}
                  className="flex items-center justify-between text-sm border-b border-line pb-2 last:border-0"
                >
                  <span className="font-mono text-text/90">{u.user_id}</span>
                  <span className="font-bold text-danger">
                    {u.score.toFixed(1)}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>
    </div>
  );
}
