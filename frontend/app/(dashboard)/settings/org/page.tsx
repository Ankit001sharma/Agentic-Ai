"use client";

import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { JsonViewer } from "@/components/sentinel/json-viewer";
import { apiFetch } from "@/lib/api";
import { useApiHeaders } from "@/lib/hooks/use-api-headers";

export default function SettingsOrgPage() {
  const headers = useApiHeaders();
  const q = useQuery({
    queryKey: ["admin-org"],
    queryFn: () => apiFetch<Record<string, unknown>>("/api/admin/organization", { ...headers }),
  });
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Organization</h1>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Profile (stub)</CardTitle>
        </CardHeader>
        <CardContent>
          <JsonViewer data={q.data ?? {}} />
        </CardContent>
      </Card>
    </div>
  );
}
