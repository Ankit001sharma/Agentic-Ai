"use client";

import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { apiFetch } from "@/lib/api";
import { useApiHeaders } from "@/lib/hooks/use-api-headers";

type HourRow = {
  hour: string;
  ALLOW: number;
  MASK: number;
  ESCALATE: number;
  BLOCK: number;
};

export default function AnalyticsPage() {
  const headers = useApiHeaders();
  const [since, setSince] = useState("");
  const q = useQuery({
    queryKey: ["analytics-full"],
    queryFn: async () => {
      const [summary, byHour, top, models] = await Promise.all([
        apiFetch<Record<string, unknown>>("/api/analytics/summary", { ...headers }),
        apiFetch<HourRow[]>("/api/analytics/threats_by_hour", { ...headers }),
        apiFetch<{ category: string; count: number }[]>("/api/analytics/top_threats", { ...headers }),
        apiFetch<{ model: string; count: number }[]>("/api/analytics/model_usage", { ...headers }),
      ]);
      return { summary, byHour, top, models };
    },
    refetchInterval: 15_000,
  });

  const filteredHourly = useMemo(() => {
    const rows = q.data?.byHour || [];
    if (!since) return rows;
    const t = new Date(since).getTime();
    return rows.filter((row) => {
      if (!row.hour) return true;
      return new Date(row.hour).getTime() >= t;
    });
  }, [q.data?.byHour, since]);

  function exportCsv() {
    const rows = q.data?.top || [];
    const lines = ["category,count", ...rows.map((r) => `${r.category},${r.count}`)];
    const blob = new Blob([lines.join("\n")], { type: "text/csv" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "top_threats.csv";
    a.click();
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Analytics</h1>
          <p className="text-sm text-muted-foreground">Extended charts + CSV export</p>
        </div>
        <div className="flex flex-wrap items-end gap-2">
          <div>
            <Label className="text-xs">Since (ISO date)</Label>
            <Input type="date" value={since} onChange={(e) => setSince(e.target.value)} className="w-40" />
          </div>
          <Button variant="outline" size="sm" onClick={exportCsv}>
            Export threats CSV
          </Button>
        </div>
      </div>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Summary</CardTitle>
        </CardHeader>
        <CardContent>
          <pre className="text-xs">{JSON.stringify(q.data?.summary, null, 2)}</pre>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Verdicts (filtered)</CardTitle>
        </CardHeader>
        <CardContent className="h-80">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={filteredHourly}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="hour" tickFormatter={(s) => String(s).slice(0, 16)} />
              <YAxis />
              <Tooltip />
              <Legend />
              <Bar dataKey="ALLOW" stackId="a" fill="#16a34a" />
              <Bar dataKey="MASK" stackId="a" fill="#f59e0b" />
              <Bar dataKey="ESCALATE" stackId="a" fill="#fb923c" />
              <Bar dataKey="BLOCK" stackId="a" fill="#dc2626" />
            </BarChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>
    </div>
  );
}
