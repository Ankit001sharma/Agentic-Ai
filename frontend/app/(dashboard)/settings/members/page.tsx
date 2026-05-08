"use client";

import { useQuery } from "@tanstack/react-query";
import { Card, CardContent } from "@/components/ui/card";
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

export default function SettingsMembersPage() {
  const headers = useApiHeaders();
  const q = useQuery({
    queryKey: ["admin-members"],
    queryFn: () => apiFetch<{ id: string; email: string; role: string; status: string }[]>("/api/admin/members", { ...headers }),
  });
  const rows = q.data ?? [];
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Members</h1>
      <Card>
        <CardContent className="pt-6">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Email</TableHead>
                <TableHead>Role</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((r) => (
                <TableRow key={r.id}>
                  <TableCell>{r.email}</TableCell>
                  <TableCell>{r.role}</TableCell>
                  <TableCell>{r.status}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
