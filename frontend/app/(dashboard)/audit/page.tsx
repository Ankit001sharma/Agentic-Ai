"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useState } from "react";
import { VerdictChip } from "@/components/sentinel/verdict-chip";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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
  risk: number;
  prompt_preview: string;
  created_at: string | null;
};

export default function AuditPage() {
  const headers = useApiHeaders();
  const sp = useSearchParams();
  const [verdict, setVerdict] = useState(sp.get("verdict") || "");
  const [userId, setUserId] = useState(sp.get("user_id") || "");
  const [qstr, setQstr] = useState("");

  const q = useQuery({
    queryKey: ["audit", verdict, userId, qstr],
    queryFn: () => {
      const p = new URLSearchParams();
      p.set("limit", "100");
      if (verdict) p.set("verdict", verdict);
      if (userId) p.set("user_id", userId);
      if (qstr) p.set("q", qstr);
      return apiFetch<Row[]>(`/api/analytics/recent?${p.toString()}`, { ...headers });
    },
    refetchInterval: 12_000,
  });

  const rows = q.data ?? [];

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold">Audit log</h1>
        <p className="text-sm text-muted-foreground">Filtered recent requests</p>
      </div>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Filters</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-4">
          <div>
            <Label className="text-xs">Verdict</Label>
            <Input value={verdict} onChange={(e) => setVerdict(e.target.value)} placeholder="BLOCK" className="w-32" />
          </div>
          <div>
            <Label className="text-xs">User id</Label>
            <Input value={userId} onChange={(e) => setUserId(e.target.value)} className="w-48" />
          </div>
          <div>
            <Label className="text-xs">Prompt contains</Label>
            <Input value={qstr} onChange={(e) => setQstr(e.target.value)} className="w-48" />
          </div>
          <Button variant="secondary" onClick={() => q.refetch()}>
            Refresh
          </Button>
        </CardContent>
      </Card>
      <Card>
        <CardContent className="pt-6">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Id</TableHead>
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
                    <Link href={`/inspect/${r.id}`} className="font-mono text-xs text-primary hover:underline">
                      {r.id.slice(-12)}
                    </Link>
                  </TableCell>
                  <TableCell className="font-mono text-xs">{r.user_id}</TableCell>
                  <TableCell>
                    <VerdictChip verdict={r.verdict} />
                  </TableCell>
                  <TableCell>{r.risk}</TableCell>
                  <TableCell className="max-w-md truncate text-xs">{r.prompt_preview}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
