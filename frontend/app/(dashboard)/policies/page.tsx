"use client";

import dynamic from "next/dynamic";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, X } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { apiFetch } from "@/lib/api";
import { useApiHeaders } from "@/lib/hooks/use-api-headers";

const Editor = dynamic(() => import("@monaco-editor/react"), { ssr: false });

type Policy = {
  id: number;
  name: string;
  rego: string;
  enabled: boolean;
  suggested: boolean;
  suggested_by: string | null;
  suggested_reason: string | null;
  approved: boolean;
};

export default function PoliciesPage() {
  const headers = useApiHeaders();
  const qc = useQueryClient();
  const [draft, setDraft] = useState<string | null>(null);

  const q = useQuery({
    queryKey: ["policies"],
    queryFn: () => apiFetch<Policy[]>("/api/policies", { ...headers }),
    refetchInterval: 8000,
  });

  const act = useMutation({
    mutationFn: async ({ id, action }: { id: number; action: "approve" | "reject" }) => {
      await apiFetch(`/api/policies/${id}/${action}`, { method: "POST", ...headers });
    },
    onSuccess: () => {
      toast.success("Updated");
      qc.invalidateQueries({ queryKey: ["policies"] });
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : "Failed"),
  });

  const items = q.data ?? [];
  const active = items.filter((p) => !p.suggested);
  const suggested = items.filter((p) => p.suggested);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Policies</h1>
        <p className="text-sm text-muted-foreground">OPA Rego bundle + AI-suggested rules.</p>
      </div>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Editor (scratch)</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="h-[240px] overflow-hidden rounded-md border">
            <Editor
              height="240px"
              defaultLanguage="plaintext"
              theme="vs-dark"
              value={draft ?? "package sentinel\n\n# Draft Rego here — dry-run against OPA is TODO.\n"}
              onChange={(v) => setDraft(v || "")}
            />
          </div>
          <p className="mt-2 text-xs text-muted-foreground">
            Version history & dry-run: wire to OPA CI in a follow-up.
          </p>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Active</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {active.length === 0 ? (
            <p className="text-sm text-muted-foreground">No rows in DB.</p>
          ) : (
            active.map((p) => (
              <div key={p.id} className="rounded-md border p-3">
                <div className="font-medium">{p.name}</div>
                <pre className="mt-2 max-h-40 overflow-auto text-[11px] text-muted-foreground">{p.rego}</pre>
              </div>
            ))
          )}
        </CardContent>
      </Card>
      <div>
        <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          AI-suggested
        </h2>
        {suggested.length === 0 ? (
          <Card>
            <CardContent className="py-8 text-center text-sm text-muted-foreground">
              No suggestions.
            </CardContent>
          </Card>
        ) : (
          <ul className="space-y-3">
            {suggested.map((p) => (
              <li key={p.id} className="rounded-xl border bg-card p-4 shadow-sm">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <div className="font-semibold">{p.name}</div>
                    <div className="text-xs text-muted-foreground">
                      {p.suggested_by} — {p.suggested_reason}
                    </div>
                  </div>
                  <div className="flex gap-2">
                    {!p.approved && (
                      <Button size="sm" onClick={() => act.mutate({ id: p.id, action: "approve" })}>
                        <Check className="mr-1 h-4 w-4" />
                        Approve
                      </Button>
                    )}
                    <Button size="sm" variant="outline" onClick={() => act.mutate({ id: p.id, action: "reject" })}>
                      <X className="mr-1 h-4 w-4" />
                      Reject
                    </Button>
                  </div>
                </div>
                <Separator className="my-3" />
                <pre className="max-h-48 overflow-auto text-[11px]">{p.rego}</pre>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
