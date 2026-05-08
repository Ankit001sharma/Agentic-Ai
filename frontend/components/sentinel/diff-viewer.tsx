"use client";

import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";

export function DiffViewer({
  before,
  after,
  beforeLabel = "Before",
  afterLabel = "After",
  className,
}: {
  before?: string;
  after: string;
  beforeLabel?: string;
  afterLabel?: string;
  className?: string;
}) {
  return (
    <div className={cn("grid gap-3 md:grid-cols-2", className)}>
      {before !== undefined && (
        <div>
          <div className="mb-1 text-xs font-medium text-muted-foreground">{beforeLabel}</div>
          <ScrollArea className="h-40 rounded-md border bg-muted/20 p-2">
            <pre className="whitespace-pre-wrap text-xs font-mono">{before}</pre>
          </ScrollArea>
        </div>
      )}
      <div>
        <div className="mb-1 text-xs font-medium text-muted-foreground">{afterLabel}</div>
        <ScrollArea className="h-40 rounded-md border bg-muted/20 p-2">
          <pre className="whitespace-pre-wrap text-xs font-mono">{after}</pre>
        </ScrollArea>
      </div>
    </div>
  );
}
