"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { apiFetch } from "@/lib/api";
import { useApiHeaders } from "@/lib/hooks/use-api-headers";

type KeyRow = { id: string; name: string; prefix: string; scopes: string[] };

export default function ApiKeysPage() {
  const headers = useApiHeaders();
  const qc = useQueryClient();
  const [name, setName] = useState("dashboard-key");
  const [revealed, setRevealed] = useState<string | null>(null);

  const q = useQuery({
    queryKey: ["api-keys"],
    queryFn: () => apiFetch<KeyRow[]>("/api/keys", { ...headers }),
  });

  const create = useMutation({
    mutationFn: () =>
      apiFetch<{ id: string; key: string; warning?: string }>("/api/keys", {
        method: "POST",
        body: JSON.stringify({ name, scopes: ["read", "write"] }),
        ...headers,
      }),
    onSuccess: (data) => {
      setRevealed(data.key);
      toast.message(data.warning || "Key created");
      qc.invalidateQueries({ queryKey: ["api-keys"] });
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : "Error"),
  });

  const revoke = useMutation({
    mutationFn: (id: string) => apiFetch(`/api/keys/${id}`, { method: "DELETE", ...headers }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["api-keys"] }),
  });

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold">API keys</h1>
        <p className="text-sm text-muted-foreground">In-memory stub — replace with persisted keys in production.</p>
      </div>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Create</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-wrap items-end gap-2">
          <div>
            <Label>Name</Label>
            <Input value={name} onChange={(e) => setName(e.target.value)} className="w-56" />
          </div>
          <Button onClick={() => create.mutate()} disabled={create.isPending}>
            Generate
          </Button>
        </CardContent>
        {revealed ? (
          <CardContent>
            <p className="text-xs font-medium text-destructive">Copy now:</p>
            <code className="mt-1 block break-all rounded bg-muted p-2 text-xs">{revealed}</code>
          </CardContent>
        ) : null}
      </Card>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Active</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {(q.data || []).map((k) => (
            <div key={k.id} className="flex items-center justify-between rounded border p-2 text-sm">
              <div>
                <div className="font-medium">{k.name}</div>
                <div className="font-mono text-xs text-muted-foreground">{k.prefix}…</div>
              </div>
              <Button size="sm" variant="destructive" onClick={() => revoke.mutate(k.id)}>
                Revoke
              </Button>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
