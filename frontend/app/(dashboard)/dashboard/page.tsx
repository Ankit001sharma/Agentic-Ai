"use client";

import { useQuery } from "@tanstack/react-query";
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
import { KpiTile } from "@/components/sentinel/kpi-tile";
import { RiskMeter } from "@/components/sentinel/risk-meter";
import { apiFetch } from "@/lib/api";
import { useApiHeaders } from "@/lib/hooks/use-api-headers";
import { useLiveEvents } from "@/lib/sse";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

type Summary = {
  total: number;
  blocked: number;
  masked: number;
  escalated: number;
  block_rate: number;
  mask_rate?: number;
  escalation_rate?: number;
  avg_risk: number;
  avg_latency_ms: number;
  fallback_rate?: number;
};

export default function DashboardPage() {
  const headers = useApiHeaders();
  const events = useLiveEvents(30);
  const last = events.find((e) => e.type === "request");

  const q = useQuery({
    queryKey: ["dash"],
    queryFn: async () => {
      const [summary, byHour, topThreats, models, risky] = await Promise.all([
        apiFetch<Summary>("/api/analytics/summary", { ...headers }),
        apiFetch<{ hour: string; ALLOW: number; MASK: number; ESCALATE: number; BLOCK: number }[]>(
          "/api/analytics/threats_by_hour",
          { ...headers }
        ),
        apiFetch<{ category: string; count: number }[]>("/api/analytics/top_threats", { ...headers }),
        apiFetch<{ model: string; count: number }[]>("/api/analytics/model_usage", { ...headers }),
        apiFetch<{ user_id: string; score: number }[]>("/api/analytics/top_risky_users", { ...headers }),
      ]);
      return { summary, byHour, topThreats, models, risky };
    },
    refetchInterval: 12_000,
  });

  if (q.isLoading || !q.data) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-10 w-64" />
        <div className="grid gap-3 md:grid-cols-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <Skeleton key={i} className="h-24" />
          ))}
        </div>
      </div>
    );
  }

  const { summary, byHour, topThreats, models, risky } = q.data;
  const pulseRisk = last?.risk ?? Math.round(summary.avg_risk);

  const COLORS = ["#FF7300", "#16a34a", "#f59e0b", "#dc2626", "#0ea5e9", "#a855f7"];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Dashboard</h1>
        <p className="text-sm text-muted-foreground">
          Real-time posture across the 14-stage SentinelGuard pipeline.
        </p>
      </div>

      <div className="grid gap-3 lg:grid-cols-6">
        <Card className="lg:col-span-1">
          <CardContent className="flex justify-center pt-4">
            <RiskMeter value={pulseRisk} label="live / avg risk" />
          </CardContent>
        </Card>
        <div className="contents lg:col-span-5 lg:grid lg:grid-cols-4 lg:gap-3">
          <KpiTile label="Total requests" value={summary.total} sub={`block ${summary.block_rate}%`} />
          <KpiTile
            label="Blocked"
            value={summary.blocked}
            valueClassName="text-destructive"
            sub={`mask ${summary.mask_rate ?? 0}%`}
          />
          <KpiTile
            label="Masked"
            value={summary.masked}
            valueClassName="text-warning"
            sub={`escalate ${summary.escalation_rate ?? 0}%`}
          />
          <KpiTile
            label="Escalated"
            value={summary.escalated}
            valueClassName="text-warning"
            sub={`fallback ${summary.fallback_rate ?? 0}%`}
          />
          <KpiTile label="Avg risk" value={summary.avg_risk} />
          <KpiTile label="Avg latency" value={`${Math.round(summary.avg_latency_ms)} ms`} />
          <KpiTile label="Pipeline errors" value="—" sub="see audit_log / incidents" />
          <KpiTile label="p95 latency" value="—" sub="enable metrics backend" />
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Verdicts (24h)</CardTitle>
          </CardHeader>
          <CardContent className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={byHour}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                <XAxis dataKey="hour" tickFormatter={(s) => s.slice(11, 16)} className="text-[10px]" />
                <YAxis className="text-[10px]" />
                <Tooltip />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Bar dataKey="ALLOW" stackId="v" fill="#16a34a" />
                <Bar dataKey="MASK" stackId="v" fill="#f59e0b" />
                <Bar dataKey="ESCALATE" stackId="v" fill="#fb923c" />
                <Bar dataKey="BLOCK" stackId="v" fill="#dc2626" />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Top threats</CardTitle>
          </CardHeader>
          <CardContent className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={topThreats} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                <XAxis type="number" className="text-[10px]" />
                <YAxis type="category" dataKey="category" width={120} className="text-[10px]" />
                <Tooltip />
                <Bar dataKey="count" fill="#FF7300" />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Model usage</CardTitle>
          </CardHeader>
          <CardContent className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={models} dataKey="count" nameKey="model" cx="50%" cy="50%" outerRadius={80} label>
                  {models.map((_, i) => (
                    <Cell key={i} fill={COLORS[i % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip />
                <Legend wrapperStyle={{ fontSize: 11 }} />
              </PieChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Top risky users</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2">
              {risky.length === 0 ? (
                <li className="text-sm text-muted-foreground">No risk graph data yet.</li>
              ) : (
                risky.map((u) => (
                  <li key={u.user_id} className="flex justify-between border-b border-border py-2 text-sm last:border-0">
                    <span className="font-mono text-xs">{u.user_id}</span>
                    <span className="font-bold text-destructive">{u.score.toFixed(1)}</span>
                  </li>
                ))
              )}
            </ul>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
