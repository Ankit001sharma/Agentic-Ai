"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { JsonViewer } from "@/components/sentinel/json-viewer";
import { apiFetch, endSession } from "@/lib/api";
import { useApiHeaders } from "@/lib/hooks/use-api-headers";

type SessionRow = { conv_id: string; ttl_seconds: number; context_preview: Record<string, unknown> };

export default function ConversationsPage() {
  const headers = useApiHeaders();
  const qc = useQueryClient();
  const q = useQuery({
    queryKey: ["sessions", headers.userId],
    queryFn: () => apiFetch<SessionRow[]>("/api/v2/sessions", { ...headers }),
    refetchInterval: 10_000,
  });

  const kill = useMutation({
    mutationFn: (convId: string) => endSession(convId, headers),
    onSuccess: () => {
      toast.success("Session ended");
      qc.invalidateQueries({ queryKey: ["sessions"] });
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : "Error"),
  });

  const rows = q.data ?? [];

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold">Conversations</h1>
        <p className="text-sm text-muted-foreground">Active STM keys in Redis for your user id.</p>
      </div>
      {rows.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center text-sm text-muted-foreground">
            No active conversations. Use the Sandbox with your signed-in user id.
          </CardContent>
        </Card>
      ) : (
        <ul className="space-y-3">
          {rows.map((r) => (
            <li key={r.conv_id}>
              <Card>
                <CardHeader className="flex flex-row items-center justify-between py-3">
                  <CardTitle className="font-mono text-sm">{r.conv_id}</CardTitle>
                  <Button
                    size="sm"
                    variant="destructive"
                    disabled={kill.isPending}
                    onClick={() => kill.mutate(r.conv_id)}
                  >
                    End session
                  </Button>
                </CardHeader>
                <CardContent>
                  <p className="text-xs text-muted-foreground">TTL {r.ttl_seconds}s</p>
                  <JsonViewer data={r.context_preview} className="mt-2" />
                </CardContent>
              </Card>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
