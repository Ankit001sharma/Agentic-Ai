"use client";

import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { JsonViewer } from "@/components/sentinel/json-viewer";
import { Skeleton } from "@/components/ui/skeleton";
import { apiFetch } from "@/lib/api";
import { useApiHeaders } from "@/lib/hooks/use-api-headers";
import { Badge } from "@/components/ui/badge";

export default function ToolsCatalogPage() {
  const headers = useApiHeaders();
  const q = useQuery({
    queryKey: ["catalog-tools"],
    queryFn: () => apiFetch<Record<string, unknown>>("/api/catalog/tools", { ...headers }),
  });

  if (q.isLoading) return <Skeleton className="h-96 w-full" />;
  if (q.isError) return <p className="text-destructive">Failed to load tools.yaml</p>;

  const doc = q.data as { tools?: Record<string, unknown>[] };
  const tools = doc?.tools || [];

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold">Tools catalog</h1>
        <p className="text-sm text-muted-foreground">From backend tools.yaml</p>
      </div>
      <div className="grid gap-3 md:grid-cols-2">
        {tools.map((t, i) => (
          <Card key={i}>
            <CardHeader className="py-3">
              <CardTitle className="flex flex-wrap items-center gap-2 text-sm">
                {String((t as { id?: string }).id || `tool-${i}`)}
                {(t as { high_impact?: boolean }).high_impact ? (
                  <Badge variant="destructive">high impact</Badge>
                ) : null}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <JsonViewer data={t} />
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
