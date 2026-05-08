"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";
import { DiffViewer } from "@/components/sentinel/diff-viewer";
import { JsonViewer } from "@/components/sentinel/json-viewer";
import { ModelBadge } from "@/components/sentinel/model-badge";
import { PipelineStepper } from "@/components/sentinel/pipeline-stepper";
import { ThreatChips } from "@/components/sentinel/threat-chips";
import { VerdictChip } from "@/components/sentinel/verdict-chip";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { apiFetch } from "@/lib/api";
import { useApiHeaders } from "@/lib/hooks/use-api-headers";

type InspectPayload = {
  request_id: string;
  user_id: string;
  conv_id?: string | null;
  prompt: string;
  redacted_prompt?: string | null;
  final_response?: string | null;
  verdict: string;
  output_verdict: string;
  risk: number;
  output_risk: number;
  block_reason?: string | null;
  risk_breakdown: Record<string, number>;
  selected_model?: string | null;
  fallback_used: boolean;
  findings_input: { category: string; scanner: string; severity: number }[];
  findings_output: { category: string; scanner: string; severity: number }[];
  agent_trace?: {
    agent_steps: { stage?: number; name?: string; phase?: string; tool?: string; observation?: string }[];
    explanation?: Record<string, unknown>;
  } | null;
  audit?: {
    tool_id?: string | null;
    tool_executed?: boolean;
    simulated?: boolean;
    tool_args?: unknown;
    tool_result?: unknown;
    pipeline_error?: unknown;
  } | null;
};

export default function InspectPage() {
  const params = useParams();
  const requestId = String(params.requestId || "");
  const headers = useApiHeaders();

  const q = useQuery({
    queryKey: ["inspect", requestId],
    queryFn: () => apiFetch<InspectPayload>(`/api/inspect/${requestId}`, { ...headers }),
    enabled: !!requestId,
  });

  if (q.isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (q.isError || !q.data) {
    return (
      <div className="rounded-lg border border-destructive/50 p-6 text-destructive">
        Failed to load request.{" "}
        <Link href="/live" className="underline">
          Back to live
        </Link>
      </div>
    );
  }

  const d = q.data;
  const stage = d.agent_trace?.agent_steps?.length || 12;
  const inCats = d.findings_input.map((f) => f.category);
  const outCats = d.findings_output.map((f) => f.category);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="font-mono text-xl font-bold">{d.request_id}</h1>
          <p className="text-sm text-muted-foreground">
            User {d.user_id}
            {d.conv_id ? ` · conv ${d.conv_id}` : ""}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <VerdictChip verdict={d.verdict} />
          <VerdictChip verdict={d.output_verdict} />
          <Badge variant="outline">risk {d.risk} / out {d.output_risk}</Badge>
          <ModelBadge model={d.selected_model} fallback={d.fallback_used} />
          <Button variant="outline" size="sm" asChild>
            <Link href="/sandbox">Re-run in Sandbox</Link>
          </Button>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Pipeline progress</CardTitle>
        </CardHeader>
        <CardContent>
          <PipelineStepper currentStage={Math.min(14, stage)} />
        </CardContent>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Prompt hygiene</CardTitle>
          </CardHeader>
          <CardContent>
            <DiffViewer
              before={d.prompt}
              after={d.redacted_prompt || d.prompt}
              beforeLabel="Original"
              afterLabel="Redacted / sent"
            />
            <div className="mt-3">
              <ThreatChips categories={[...inCats, ...outCats]} />
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Response</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="whitespace-pre-wrap text-sm">{d.final_response || "—"}</p>
            {d.block_reason ? (
              <p className="mt-2 text-sm text-destructive">block_reason: {d.block_reason}</p>
            ) : null}
          </CardContent>
        </Card>
      </div>

      <Accordion type="multiple" className="w-full" defaultValue={["risk", "audit", "trace"]}>
        <AccordionItem value="risk">
          <AccordionTrigger>Risk breakdown</AccordionTrigger>
          <AccordionContent>
            <JsonViewer data={d.risk_breakdown} />
          </AccordionContent>
        </AccordionItem>
        <AccordionItem value="findings">
          <AccordionTrigger>Findings (input / output)</AccordionTrigger>
          <AccordionContent>
            <JsonViewer data={{ input: d.findings_input, output: d.findings_output }} />
          </AccordionContent>
        </AccordionItem>
        <AccordionItem value="audit">
          <AccordionTrigger>Audit log blob</AccordionTrigger>
          <AccordionContent>
            <JsonViewer data={d.audit ?? {}} />
          </AccordionContent>
        </AccordionItem>
        <AccordionItem value="trace">
          <AccordionTrigger>Agent trace</AccordionTrigger>
          <AccordionContent>
            <JsonViewer data={d.agent_trace ?? {}} />
          </AccordionContent>
        </AccordionItem>
      </Accordion>

      <Separator />
      <Button variant="ghost" asChild>
        <Link href="/live">← Back to live stream</Link>
      </Button>
    </div>
  );
}
