import { Badge } from "@/components/ui/badge";
import { Bot, Cpu } from "lucide-react";

export function ModelBadge({
  model,
  fallback,
}: {
  model?: string | null;
  fallback?: boolean;
}) {
  if (!model) return null;
  const isLocal = model.startsWith("openai/") || model === "stub";
  return (
    <Badge variant="outline" className="gap-1 font-mono text-[10px]">
      {isLocal ? <Cpu className="h-3 w-3" /> : <Bot className="h-3 w-3" />}
      {model}
      {fallback ? <span className="text-warning">(fallback)</span> : null}
    </Badge>
  );
}
