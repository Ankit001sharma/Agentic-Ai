"use client";

import { Loader2, Send } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { DiffViewer } from "@/components/sentinel/diff-viewer";
import { JsonViewer } from "@/components/sentinel/json-viewer";
import { PipelineStepper } from "@/components/sentinel/pipeline-stepper";
import { RiskMeter } from "@/components/sentinel/risk-meter";
import { VerdictChip } from "@/components/sentinel/verdict-chip";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Textarea } from "@/components/ui/textarea";
import { chatV2, fetchChatCompletionsSandboxNormalized } from "@/lib/api";
import { useApiHeaders } from "@/lib/hooks/use-api-headers";
import { SANDBOX_SCENARIOS, type Scenario } from "@/lib/sandbox-scenarios";
import Link from "next/link";

export default function SandboxPage() {
  const headers = useApiHeaders();
  const [convId, setConvId] = useState<string | null>(null);
  const [customPrompt, setCustomPrompt] = useState("");
  const [attachmentFiles, setAttachmentFiles] = useState<File[]>([]);
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const canRunCustom =
    !!customPrompt.trim() || attachmentFiles.length > 0;

  async function runScenario(s: Scenario, id: string) {
    setBusy(id);
    setResult(null);
    try {
      const r = await chatV2(
        {
          prompt: s.prompt,
          conv_id: convId || undefined,
          simulate: false,
        },
        {
          ...headers,
          userId: s.user || `demo-${id}`,
          userTier: s.tier || "free",
          sensitivity: s.sensitivity,
          authType: s.authType,
          userRole: s.role,
          resource: s.resource,
        }
      );
      setResult(r);
      if (typeof r.conv_id === "string") setConvId(r.conv_id);
      toast.success("Pipeline completed");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Request failed");
    } finally {
      setBusy(null);
    }
  }

  async function runCustomV2() {
    if (!customPrompt.trim()) return;
    setBusy("custom-v2");
    setResult(null);
    try {
      const r = await chatV2(
        { prompt: customPrompt, conv_id: convId || undefined, simulate: false },
        { ...headers }
      );
      setResult(r);
      if (typeof r.conv_id === "string") setConvId(r.conv_id);
      toast.success("OK");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed");
    } finally {
      setBusy(null);
    }
  }

  async function runCustomAttachments() {
    if (!canRunCustom) return;
    setBusy("custom-v1");
    setResult(null);
    try {
      const r = await fetchChatCompletionsSandboxNormalized({
        prompt: customPrompt.trim() || "(attachment only)",
        files: attachmentFiles.length ? attachmentFiles : undefined,
        ...headers,
      });
      setResult(r);
      if (String(r.verdict || "").toUpperCase() === "BLOCK") {
        toast.message("OpenAI path: request blocked", {
          description: String(r.message || "").slice(0, 160),
        });
      } else {
        toast.success("OpenAI-compatible path OK");
      }
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed");
    } finally {
      setBusy(null);
    }
  }

  const agentSteps = (result?.agent_steps as { stage?: number }[] | undefined) || [];
  const lastStage =
    agentSteps.length > 0
      ? Math.max(...agentSteps.map((s) => s.stage || 0))
      : 12;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Sandbox</h1>
          <p className="text-sm text-muted-foreground">
            Multi-turn uses <code className="text-xs">conv_id</code>.{" "}
            <Link href="/conversations" className="text-primary underline">
              Conversations
            </Link>
          </p>
        </div>
        <Card className="w-full max-w-sm">
          <CardHeader className="py-3">
            <CardTitle className="text-sm">Session</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-xs">
            <div>
              <Label>conv_id</Label>
              <Input
                value={convId || ""}
                onChange={(e) => setConvId(e.target.value || null)}
                placeholder="auto from last response"
                className="font-mono"
              />
            </div>
            <p className="text-muted-foreground">
              Run STM turn A then B with the same conv_id to test memory.
            </p>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
        {SANDBOX_SCENARIOS.map((s) => (
          <button
            key={s.id}
            type="button"
            disabled={!!busy}
            onClick={() => runScenario(s, s.id)}
            className="rounded-xl border bg-card p-3 text-left shadow-sm transition hover:border-primary/40 disabled:opacity-50"
          >
            <div className="flex items-center justify-between gap-2">
              <span className="font-semibold text-sm">{s.title}</span>
              {busy === s.id ? (
                <Loader2 className="h-4 w-4 animate-spin text-primary" />
              ) : (
                <Send className="h-4 w-4 text-muted-foreground" />
              )}
            </div>
            <p className="mt-1 text-xs text-muted-foreground">{s.desc}</p>
            <p className="mt-2 text-[11px] font-mono text-primary">{s.expected}</p>
          </button>
        ))}
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Custom prompt</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <Textarea
            value={customPrompt}
            onChange={(e) => setCustomPrompt(e.target.value)}
            placeholder="Try your own prompt…"
            rows={4}
          />
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            <Label htmlFor="sandbox-files" className="text-xs text-muted-foreground shrink-0">
              Attachments (v1 only)
            </Label>
            <Input
              id="sandbox-files"
              type="file"
              multiple
              className="max-w-md cursor-pointer text-xs file:mr-2"
              onChange={(e) => setAttachmentFiles(Array.from(e.target.files || []))}
            />
            {attachmentFiles.length > 0 ? (
              <span className="text-[11px] text-muted-foreground">
                {attachmentFiles.map((f) => f.name).join(", ")}
              </span>
            ) : null}
          </div>
          <div className="flex flex-wrap gap-2">
            <Button disabled={!!busy || !customPrompt.trim()} onClick={runCustomV2}>
              Run pipeline (v2)
            </Button>
            <Button
              variant="secondary"
              disabled={!!busy || !canRunCustom}
              onClick={runCustomAttachments}
            >
              OpenAI path (v1) — attachments-capable
            </Button>
          </div>
          <p className="text-[11px] text-muted-foreground">
            v1 returns OpenAI-shaped JSON; results are normalized here so verdict, risk, and message match the v2
            panel. Use v1 for file attachments; v2 is multi-turn <code className="text-[10px]">conv_id</code>.
          </p>
        </CardContent>
      </Card>

      {result && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Last result</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex flex-wrap items-center gap-2">
              <VerdictChip verdict={String(result.verdict || "")} />
              {result.tool_id ? (
                <span className="rounded border px-2 py-0.5 font-mono text-[10px]">
                  tool: {String(result.tool_id)}
                </span>
              ) : null}
              <RiskMeter value={Number(result.risk || 0)} />
            </div>
            <PipelineStepper currentStage={Math.min(14, lastStage)} />
            <DiffViewer
              beforeLabel="Intent detail"
              before={JSON.stringify(result.intent_detail || {}, null, 2)}
              afterLabel="Assistant message"
              after={String(result.message || "")}
            />
            <Separator />
            <JsonViewer data={result} />
          </CardContent>
        </Card>
      )}
    </div>
  );
}
