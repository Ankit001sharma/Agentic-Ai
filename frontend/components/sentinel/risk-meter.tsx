"use client";

import { motion } from "framer-motion";

export function RiskMeter({ value, label }: { value: number; label?: string }) {
  const v = Math.max(0, Math.min(100, value || 0));
  const color =
    v >= 90 ? "#dc2626" : v >= 70 ? "#f97316" : v >= 30 ? "#f59e0b" : "#16a34a";
  const angle = (v / 100) * 180;

  return (
    <div className="flex flex-col items-center justify-center">
      <div className="relative h-28 w-48 overflow-hidden">
        <svg viewBox="0 0 200 110" className="h-full w-full">
          <path
            d="M 10 100 A 90 90 0 0 1 190 100"
            stroke="hsl(var(--border))"
            strokeWidth="14"
            fill="none"
            strokeLinecap="round"
          />
          <motion.path
            d="M 10 100 A 90 90 0 0 1 190 100"
            stroke={color}
            strokeWidth="14"
            fill="none"
            strokeLinecap="round"
            strokeDasharray={Math.PI * 90}
            initial={{ strokeDashoffset: Math.PI * 90 }}
            animate={{ strokeDashoffset: Math.PI * 90 - (Math.PI * 90 * angle) / 180 }}
            transition={{ type: "spring", stiffness: 80, damping: 15 }}
          />
        </svg>
      </div>
      <div className="-mt-6 text-center">
        <div className="text-3xl font-bold tabular-nums" style={{ color }}>
          {v}
        </div>
        <div className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
          {label || "risk"}
        </div>
      </div>
    </div>
  );
}
