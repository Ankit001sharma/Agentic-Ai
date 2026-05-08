"use client";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

const INTEGRATIONS = [
  { name: "Resend", env: "RESEND_API_KEY", desc: "Outbound email (Stage 11)" },
  { name: "Slack", env: "SLACK_BOT_TOKEN", desc: "Slack messages" },
  { name: "GitHub", env: "GITHUB_TOKEN", desc: "Issues & workflows" },
  { name: "Tavily", env: "TAVILY_API_KEY", desc: "Web search" },
  { name: "SIEM webhook", env: "SIEM_WEBHOOK_URL", desc: "Stage 12 forwarding" },
];

export default function IntegrationsPage() {
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold">Integrations</h1>
        <p className="text-sm text-muted-foreground">
          Configure via backend .env. Status probing can be extended in /api/system/health.
        </p>
      </div>
      <div className="grid gap-3 md:grid-cols-2">
        {INTEGRATIONS.map((i) => (
          <Card key={i.name}>
            <CardHeader>
              <CardTitle className="text-base">{i.name}</CardTitle>
              <CardDescription>{i.desc}</CardDescription>
            </CardHeader>
            <CardContent>
              <Badge variant="outline" className="font-mono text-[10px]">
                {i.env}
              </Badge>
              <p className="mt-2 text-xs text-muted-foreground">Set in backend environment; never commit secrets.</p>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
