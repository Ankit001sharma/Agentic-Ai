"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { apiFetch } from "@/lib/api";
import { useApiHeaders } from "@/lib/hooks/use-api-headers";

export default function ThreatIntelPage() {
  const headers = useApiHeaders();
  const q = useQuery({
    queryKey: ["threat-intel"],
    queryFn: async () => {
      const [hourly, top, users] = await Promise.all([
        apiFetch<{ hour: string }[] & Record<string, number>[]>(
          "/api/analytics/threats_by_hour",
          { ...headers }
        ),
        apiFetch<{ category: string; count: number }[]>("/api/analytics/top_threats", { ...headers }),
        apiFetch<{ user_id: string; score: number }[]>("/api/analytics/top_risky_users", { ...headers }),
      ]);
      return { hourly, top, users };
    },
    refetchInterval: 20_000,
  });

  const data = q.data;

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold">Threat intelligence</h1>
        <p className="text-sm text-muted-foreground">Category volume and risk graph users.</p>
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Top categories</CardTitle>
          </CardHeader>
          <CardContent className="h-72">
            {data?.top?.length ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={data.top} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                  <XAxis type="number" />
                  <YAxis dataKey="category" type="category" width={120} tick={{ fontSize: 10 }} />
                  <Tooltip />
                  <Bar dataKey="count" fill="#FF7300" />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <p className="text-sm text-muted-foreground">No data.</p>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Risk graph users</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2">
              {(data?.users || []).map((u) => (
                <li key={u.user_id} className="flex justify-between text-sm">
                  <Link href={`/audit?user_id=${encodeURIComponent(u.user_id)}`} className="font-mono text-primary hover:underline">
                    {u.user_id}
                  </Link>
                  <span className="font-bold text-destructive">{u.score.toFixed(1)}</span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      </div>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Verdict timeline (24h)</CardTitle>
        </CardHeader>
        <CardContent className="h-64 text-xs text-muted-foreground">
          Use Dashboard chart for full stacked view. Raw buckets: {data?.hourly?.length ?? 0}
        </CardContent>
      </Card>
    </div>
  );
}
