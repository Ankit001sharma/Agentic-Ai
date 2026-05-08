"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useMemo, useState } from "react";
import { VerdictChip } from "@/components/sentinel/verdict-chip";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { apiFetch } from "@/lib/api";
import { useApiHeaders } from "@/lib/hooks/use-api-headers";

type Row = {
  id: string;
  user_id: string;
  verdict: string;
  output_verdict: string;
  risk: number;
  prompt_preview: string;
  created_at: string | null;
};

export default function IncidentsPage() {
  const headers = useApiHeaders();
  const q = useQuery({
    queryKey: ["incidents"],
    queryFn: () => apiFetch<Row[]>("/api/analytics/recent/incidents?limit=100", { ...headers }),
    refetchInterval: 10_000,
  });
  const [sel, setSel] = useState<Record<string, boolean>>({});

  const rows = q.data ?? [];
  const selectedIds = useMemo(() => Object.keys(sel).filter((k) => sel[k]), [sel]);

  function exportJson() {
    const subset = rows.filter((r) => selectedIds.includes(r.id));
    const blob = new Blob([JSON.stringify(subset, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "incidents.json";
    a.click();
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-2xl font-bold">Incidents</h1>
          <p className="text-sm text-muted-foreground">BLOCK / ESCALATE / high-risk from analytics.</p>
        </div>
        <Button variant="outline" size="sm" disabled={!selectedIds.length} onClick={exportJson}>
          Export selected JSON
        </Button>
      </div>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Queue</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-10" />
                <TableHead>Request</TableHead>
                <TableHead>User</TableHead>
                <TableHead>Verdict</TableHead>
                <TableHead>Risk</TableHead>
                <TableHead>Preview</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((r) => (
                <TableRow key={r.id}>
                  <TableCell>
                    <Checkbox
                      checked={!!sel[r.id]}
                      onCheckedChange={(c) => setSel((s) => ({ ...s, [r.id]: !!c }))}
                    />
                  </TableCell>
                  <TableCell>
                    <Link href={`/inspect/${r.id}`} className="font-mono text-xs text-primary hover:underline">
                      {r.id.slice(-12)}
                    </Link>
                  </TableCell>
                  <TableCell className="font-mono text-xs">{r.user_id}</TableCell>
                  <TableCell>
                    <VerdictChip verdict={r.verdict} />
                  </TableCell>
                  <TableCell>{r.risk}</TableCell>
                  <TableCell className="max-w-md truncate text-xs text-muted-foreground">
                    {r.prompt_preview}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          {!rows.length && !q.isLoading ? (
            <p className="py-8 text-center text-sm text-muted-foreground">No incidents yet.</p>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}
