"use client";

import { cn } from "@/lib/utils";

const STAGES = [
  "Context",
  "Scanners",
  "Risk",
  "Early gate",
  "Intent",
  "Tools",
  "OPA",
  "Fn-call",
  "Sanitize",
  "HI gate",
  "Execute",
  "Out scan",
  "Report",
  "Adaptive",
  "Response",
] as const;

export function PipelineStepper({
  currentStage,
  className,
}: {
  /** 1–14 while running; 12+ typical completion */
  currentStage: number;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-wrap gap-1", className)}>
      {STAGES.map((name, i) => {
        const n = i + 1;
        const done = currentStage >= n;
        const active = currentStage === n;
        return (
          <div
            key={name}
            title={`Stage ${n}: ${name}`}
            className={cn(
              "rounded border px-1.5 py-0.5 text-[9px] font-medium",
              done && "border-primary/50 bg-primary/10 text-primary",
              active && "ring-2 ring-primary",
              !done && !active && "border-border text-muted-foreground opacity-60"
            )}
          >
            {n}
          </div>
        );
      })}
    </div>
  );
}
