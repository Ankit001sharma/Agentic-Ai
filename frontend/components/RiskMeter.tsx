"use client";

import { motion } from "framer-motion";

export function RiskMeter({ value, label }: { value: number; label?: string }) {
  const v = Math.max(0, Math.min(100, value || 0));
  const color =
    v >= 90
      ? "#dc2626"
      : v >= 70
        ? "#f97316"
        : v >= 30
          ? "#f59e0b"
          : "#16a34a";

  // Half-circle gauge: 180 degrees of arc
  const angle = (v / 100) * 180;

  return (
    <div className="flex flex-col items-center justify-center">
      <div className="relative w-48 h-28 overflow-hidden">
        <svg viewBox="0 0 200 110" className="w-full h-full">
          {/* Track */}
          <path
            d="M 10 100 A 90 90 0 0 1 190 100"
            stroke="#e5e7eb"
            strokeWidth="14"
            fill="none"
            strokeLinecap="round"
          />
          {/* Value */}
          <motion.path
            d="M 10 100 A 90 90 0 0 1 190 100"
            stroke={color}
            strokeWidth="14"
            fill="none"
            strokeLinecap="round"
            strokeDasharray={Math.PI * 90}
            initial={{ strokeDashoffset: Math.PI * 90 }}
            animate={{
              strokeDashoffset: Math.PI * 90 - (Math.PI * 90 * angle) / 180,
            }}
            transition={{ type: "spring", stiffness: 80, damping: 15 }}
            style={{ filter: `drop-shadow(0 0 8px ${color}66)` }}
          />
        </svg>
      </div>
      <div className="-mt-6 text-center">
        <div className="text-3xl font-bold" style={{ color }}>
          {v}
        </div>
        <div className="text-[11px] uppercase tracking-widest text-muted">
          {label || "risk"}
        </div>
      </div>
    </div>
  );
}
