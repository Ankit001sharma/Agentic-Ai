"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export function JsonViewer({
  data,
  className,
}: {
  data: unknown;
  className?: string;
}) {
  const [open, setOpen] = useState(false);
  const text = JSON.stringify(data, null, 2);
  return (
    <div className={cn("rounded-md border bg-muted/30", className)}>
      <div className="flex items-center justify-between border-b px-2 py-1">
        <span className="text-xs text-muted-foreground">JSON</span>
        <Button variant="ghost" size="sm" className="h-7 text-xs" onClick={() => setOpen(!open)}>
          {open ? "Collapse" : "Expand"}
        </Button>
      </div>
      {open ? (
        <pre className="max-h-80 overflow-auto p-3 text-[11px] font-mono">{text}</pre>
      ) : (
        <pre className="truncate p-3 text-[11px] font-mono text-muted-foreground">{text.slice(0, 200)}…</pre>
      )}
    </div>
  );
}
