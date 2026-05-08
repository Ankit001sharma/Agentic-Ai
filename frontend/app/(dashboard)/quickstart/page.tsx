"use client";

import { useSession } from "next-auth/react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { defaultSentinelKey, API_URL } from "@/lib/api";

export default function QuickstartPage() {
  const { data } = useSession();
  const uid = data?.user?.email || "demo-user";
  const key = defaultSentinelKey;

  const v2 = `curl -sS -X POST "${API_URL}/api/v2/chat" \\
  -H "Content-Type: application/json" \\
  -H "X-Sentinel-Key: ${key}" \\
  -H "X-User-Id: ${uid}" \\
  -d '{"prompt":"Hello from curl","simulate":true}'`;

  const v1 = `curl -sS -X POST "${API_URL}/v1/chat/completions" \\
  -H "Content-Type: application/json" \\
  -H "X-Sentinel-Key: ${key}" \\
  -H "X-User-Id: ${uid}" \\
  -d '{"model":"gpt-4o-mini","messages":[{"role":"user","content":"Hello"}]}'`;

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold">Quickstart</h1>
        <p className="text-sm text-muted-foreground">Copy-paste integration snippets</p>
      </div>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">HTTP examples</CardTitle>
        </CardHeader>
        <CardContent>
          <Tabs defaultValue="v2">
            <TabsList>
              <TabsTrigger value="v2">Pipeline v2</TabsTrigger>
              <TabsTrigger value="v1">OpenAI-compatible</TabsTrigger>
            </TabsList>
            <TabsContent value="v2">
              <pre className="mt-2 overflow-x-auto rounded-lg bg-muted p-4 text-xs">{v2}</pre>
            </TabsContent>
            <TabsContent value="v1">
              <pre className="mt-2 overflow-x-auto rounded-lg bg-muted p-4 text-xs">{v1}</pre>
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>
    </div>
  );
}
