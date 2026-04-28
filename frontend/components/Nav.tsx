"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Activity, BarChart3, FileText, Inbox, Network, Shield, Sparkles } from "lucide-react";

const ITEMS = [
  { href: "/", label: "Live", icon: Activity },
  { href: "/sandbox", label: "Sandbox", icon: Sparkles },
  { href: "/agent-trace", label: "Agent trace", icon: Network },
  { href: "/review", label: "Review", icon: Inbox },
  { href: "/analytics", label: "Analytics", icon: BarChart3 },
  { href: "/policies", label: "Policies", icon: Shield },
  { href: "/logs", label: "Logs", icon: FileText },
];

export function Nav() {
  const path = usePathname();
  return (
    <aside className="w-56 shrink-0 border-r border-line bg-panel min-h-screen p-4 flex flex-col gap-1">
      <div className="flex items-center gap-2 px-2 mb-4">
        <Shield className="w-5 h-5 text-primary" />
        <div>
          <div className="font-semibold text-sm tracking-wide">SentinelGuard</div>
          <div className="text-[10px] uppercase text-muted">AI Security Gateway</div>
        </div>
      </div>
      {ITEMS.map((it) => {
        const active = path === it.href;
        const Icon = it.icon;
        return (
          <Link
            key={it.href}
            href={it.href}
            className={`flex items-center gap-2 px-3 py-2 text-sm rounded-lg ${
              active
                ? "bg-primary/15 text-primary border border-primary/30"
                : "text-muted hover:text-text hover:bg-panel2"
            }`}
          >
            <Icon className="w-4 h-4" />
            {it.label}
          </Link>
        );
      })}
      <div className="mt-auto text-[10px] text-muted px-2 pt-4 border-t border-line">
        v0.1.0
      </div>
    </aside>
  );
}
