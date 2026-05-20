"use client";

import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { apiFetch, API_URL } from "@/lib/api";
import { useApiHeaders } from "@/lib/hooks/use-api-headers";
import { EmptyState } from "@/components/sentinel/empty-state";

type HealthResponse = {
  overall: string;
  checks: Record<string, { status: string; note?: string }>;
};

export default function HealthPage() {
  const headers = useApiHeaders();
  const q = useQuery({
    queryKey: ["health-detailed"],
    queryFn: () => apiFetch<HealthResponse>("/api/system/health", { ...headers }),
    refetchInterval: 15_000,
    retry: 1,
  });

  const data = q.data;

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold">System health</h1>
        <p className="text-sm text-muted-foreground">Dependency probes from the API</p>
      </div>

      {q.isLoading && !data ? (
        <div className="space-y-3">
          <Skeleton className="h-8 w-40" />
          <div className="grid gap-3 md:grid-cols-2">
            <Skeleton className="h-24 w-full" />
            <Skeleton className="h-24 w-full" />
            <Skeleton className="h-24 w-full" />
            <Skeleton className="h-24 w-full" />
          </div>
        </div>
      ) : null}

      {q.isError ? (
        <EmptyState
          title="Cannot reach the API"
          description={
            q.error instanceof Error
              ? q.error.message
              : "Check that the backend is running and NEXT_PUBLIC_API_URL points to it."
          }
        >
          <p className="text-xs text-muted-foreground">
            Expected backend: <code className="rounded bg-muted px-1">{API_URL}</code>
            <br />
            Quick test: <code className="rounded bg-muted px-1">curl {API_URL}/health</code>
          </p>
        </EmptyState>
      ) : null}

      {!q.isError && data ? (
        <>
          <div className="flex items-center gap-2">
            Overall:{" "}
            <Badge variant={data.overall === "healthy" ? "success" : "warning"}>{data.overall}</Badge>
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            {Object.entries(data.checks).map(([name, v]) => (
              <Card key={name}>
                <CardHeader className="py-3">
                  <CardTitle className="flex items-center justify-between text-sm capitalize">
                    {name}
                    <Badge variant={String(v.status).startsWith("ok") ? "success" : "outline"}>
                      {v.status}
                    </Badge>
                  </CardTitle>
                </CardHeader>
                {v.note ? (
                  <CardContent className="text-xs text-muted-foreground">{v.note}</CardContent>
                ) : null}
              </Card>
            ))}
          </div>
        </>
      ) : null}
    </div>
  );
}