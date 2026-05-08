"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, X } from "lucide-react";
import { ThreatChips } from "@/components/sentinel/threat-chips";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { apiFetch } from "@/lib/api";
import { useApiHeaders } from "@/lib/hooks/use-api-headers";
import Link from "next/link";
import { useEffect, useState } from "react";

type Item = {
  id: string;
  request_id: string;
  user_id: string;
  prompt: string;
  risk: number;
  findings: { category?: string }[];
  status: string;
  created_at: string | null;
};

export default function ReviewPage() {
  const headers = useApiHeaders();
  const qc = useQueryClient();
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);

  const q = useQuery({
    queryKey: ["review-pending"],
    queryFn: () => apiFetch<Item[]>("/api/review/pending", { ...headers }),
    refetchInterval: 4000,
  });

  const decide = useMutation({
    mutationFn: async ({ rid, decision }: { rid: string; decision: "APPROVE" | "DENY" }) => {
      await apiFetch(`/api/review/${rid}/decision`, {
        method: "POST",
        body: JSON.stringify({ decision, analyst: headers.userId || "dashboard" }),
        ...headers,
      });
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["review-pending"] }),
  });

  const items = q.data ?? [];

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold">Review queue</h1>
        <p className="text-sm text-muted-foreground">Human-in-the-loop decisions (Redis-backed).</p>
      </div>
      {items.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center text-sm text-muted-foreground">
            No pending reviews. Trigger an ESCALATE scenario in{" "}
            <Link href="/sandbox" className="text-primary underline">
              Sandbox
            </Link>
            .
          </CardContent>
        </Card>
      ) : (
        <ul className="space-y-3">
          {items.map((it) => {
            const created = it.created_at ? new Date(it.created_at).getTime() : now;
            const elapsed = Math.max(0, Math.floor((now - created) / 1000));
            const sla = 30;
            const pct = Math.min(100, (elapsed / sla) * 100);
            return (
              <li key={it.id} className="rounded-xl border bg-card p-4 shadow-sm">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant="warning">risk {it.risk}</Badge>
                    <span className="text-xs text-muted-foreground">
                      {it.user_id} · {it.request_id.slice(-8)}
                    </span>
                  </div>
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      onClick={() => decide.mutate({ rid: it.request_id, decision: "APPROVE" })}
                      disabled={decide.isPending}
                    >
                      <Check className="mr-1 h-4 w-4" />
                      Approve
                    </Button>
                    <Button
                      size="sm"
                      variant="destructive"
                      onClick={() => decide.mutate({ rid: it.request_id, decision: "DENY" })}
                      disabled={decide.isPending}
                    >
                      <X className="mr-1 h-4 w-4" />
                      Deny
                    </Button>
                  </div>
                </div>
                <div className="mt-2 h-2 overflow-hidden rounded-full bg-muted">
                  <div
                    className="h-full bg-warning transition-all"
                    style={{ width: `${pct}%` }}
                    title={`${elapsed}s / ${sla}s`}
                  />
                </div>
                <p className="mt-3 whitespace-pre-wrap text-sm">{it.prompt}</p>
                <div className="mt-2">
                  <ThreatChips categories={(it.findings || []).map((f) => f.category || "").filter(Boolean)} />
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
