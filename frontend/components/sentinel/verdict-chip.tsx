import { Badge } from "@/components/ui/badge";

const MAP: Record<string, "default" | "secondary" | "destructive" | "outline" | "success" | "warning"> =
  {
    ALLOW: "success",
    MASK: "warning",
    ESCALATE: "warning",
    BLOCK: "destructive",
    CLEAN: "success",
    REDACT: "warning",
  };

export function VerdictChip({ verdict }: { verdict?: string | null }) {
  if (!verdict) return null;
  const v = verdict.toUpperCase();
  return (
    <Badge variant={MAP[v] || "secondary"} className="font-mono text-[10px]">
      {v}
    </Badge>
  );
}
