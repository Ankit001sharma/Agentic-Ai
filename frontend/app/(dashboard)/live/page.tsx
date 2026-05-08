"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { ModelBadge } from "@/components/sentinel/model-badge";
import { PipelineStepper } from "@/components/sentinel/pipeline-stepper";
import { ThreatChips } from "@/components/sentinel/threat-chips";
import { VerdictChip } from "@/components/sentinel/verdict-chip";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useLiveEvents, type LiveEvent } from "@/lib/sse";

export default function LivePage() {
  const events = useLiveEvents(100);
  const requests = events.filter((e) => e.type === "request");
  const [verdict, setVerdict] = useState("");
  const [user, setUser] = useState("");
  const [threat, setThreat] = useState("");

  const filtered = useMemo(() => {
    return requests.filter((e) => {
      if (verdict && (e.verdict || "").toUpperCase() !== verdict.toUpperCase()) return false;
      if (user && !(e.user || "").toLowerCase().includes(user.toLowerCase())) return false;
      if (threat) {
        const cats = [...(e.categories_in || []), ...(e.categories_out || [])];
        if (!cats.some((c) => c.toLowerCase().includes(threat.toLowerCase()))) return false;
      }
      return true;
    });
  }, [requests, verdict, user, threat]);

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold">Live stream</h1>
        <p className="text-sm text-muted-foreground">SSE from Redis — click a row to open the inspector.</p>
      </div>
      <div className="flex flex-wrap gap-4">
        <div>
          <Label className="text-xs">Verdict</Label>
          <Input placeholder="ALLOW, BLOCK…" value={verdict} onChange={(e) => setVerdict(e.target.value)} className="w-40" />
        </div>
        <div>
          <Label className="text-xs">User contains</Label>
          <Input placeholder="user id" value={user} onChange={(e) => setUser(e.target.value)} className="w-40" />
        </div>
        <div>
          <Label className="text-xs">Threat contains</Label>
          <Input placeholder="PII…" value={threat} onChange={(e) => setThreat(e.target.value)} className="w-40" />
        </div>
      </div>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Requests ({filtered.length})</CardTitle>
        </CardHeader>
        <CardContent>
          <ScrollArea className="h-[640px] pr-3">
            {filtered.length === 0 ? (
              <p className="py-12 text-center text-sm text-muted-foreground">
                No events. Run the <Link href="/sandbox" className="text-primary underline">Sandbox</Link>.
              </p>
            ) : (
              <ul className="space-y-2">
                {filtered.map((e) => (
                  <LiveRow key={`${e.request_id}-${e.ts}`} e={e} />
                ))}
              </ul>
            )}
          </ScrollArea>
        </CardContent>
      </Card>
    </div>
  );
}

function LiveRow({ e }: { e: LiveEvent }) {
  return (
    <li className="rounded-lg border bg-muted/20 p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <Link href={`/inspect/${e.request_id}`} className="font-mono text-xs text-primary hover:underline">
            {e.request_id}
          </Link>
          <VerdictChip verdict={e.verdict} />
          <VerdictChip verdict={e.output_verdict} />
          <span className="text-xs text-muted-foreground">
            risk {e.risk} / out {e.output_risk}
          </span>
          <ModelBadge model={e.model_used} fallback={e.fallback} />
        </div>
        <span className="text-[10px] text-muted-foreground">
          {e.user} · {e.latency_ms}ms
        </span>
      </div>
      {e.pipeline_stage ? (
        <div className="mt-2">
          <PipelineStepper currentStage={e.pipeline_stage} />
        </div>
      ) : null}
      <p className="mt-2 truncate text-xs text-muted-foreground">{e.prompt_preview}</p>
      <div className="mt-2">
        <ThreatChips categories={[...(e.categories_in || []), ...(e.categories_out || [])]} />
      </div>
    </li>
  );
}
