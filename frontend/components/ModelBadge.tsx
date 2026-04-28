"use client";

import { Bot, Cpu } from "lucide-react";

export function ModelBadge({
  model,
  fallback,
}: {
  model?: string;
  fallback?: boolean;
}) {
  if (!model) return null;
  const isLocal = model.startsWith("ollama") || model === "stub";
  return (
    <span className="chip border-line text-muted">
      {isLocal ? <Cpu className="w-3 h-3" /> : <Bot className="w-3 h-3" />}
      {model}
      {fallback ? <span className="text-warning ml-1">(fallback)</span> : null}
    </span>
  );
}
