"use client";

import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { apiFetch } from "@/lib/api";
import { useApiHeaders } from "@/lib/hooks/use-api-headers";

export default function HealthPage() {
  const headers = useApiHeaders();
  const q = useQuery({
    queryKey: ["health-detailed"],
    queryFn: () =>
      apiFetch<{ overall: string; checks: Record<string, { status: string; note?: string }> }>(
        "/api/system/health",
        { ...headers }
      ),
    refetchInterval: 15_000,
  });

  const data = q.data;

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold">System health</h1>
        <p className="text-sm text-muted-foreground">Dependency probes from the API</p>
      </div>
      <div className="flex items-center gap-2">
        Overall:{" "}
        <Badge variant={data?.overall === "healthy" ? "success" : "warning"}>{data?.overall ?? "…"}</Badge>
      </div>
      <div className="grid gap-3 md:grid-cols-2">
        {data &&
          Object.entries(data.checks).map(([name, v]) => (
            <Card key={name}>
              <CardHeader className="py-3">
                <CardTitle className="flex items-center justify-between text-sm capitalize">
                  {name}
                  <Badge variant={String(v.status).startsWith("ok") ? "success" : "outline"}>{v.status}</Badge>
                </CardTitle>
              </CardHeader>
              {v.note ? (
                <CardContent className="text-xs text-muted-foreground">{v.note}</CardContent>
              ) : null}
            </Card>
          ))}
      </div>
    </div>
  );
}
