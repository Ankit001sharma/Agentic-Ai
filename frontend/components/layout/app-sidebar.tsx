"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  BarChart3,
  BookOpen,
  Building2,
  CreditCard,
  FlaskConical,
  Inbox,
  KeyRound,
  LayoutDashboard,
  Network,
  Plug,
  ScrollText,
  Settings,
  Shield,
  ShieldCheck,
  Users,
  Wrench,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { useSession } from "next-auth/react";
import { ChevronDown } from "lucide-react";

type Item = { href: string; label: string; icon: React.ElementType; roles?: string[] };

const SECTIONS: { title: string; items: Item[] }[] = [
  {
    title: "Operate",
    items: [
      { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
      { href: "/live", label: "Live stream", icon: Activity },
      { href: "/incidents", label: "Incidents", icon: ShieldCheck },
      { href: "/review", label: "Review queue", icon: Inbox, roles: ["admin", "analyst"] },
    ],
  },
  {
    title: "Investigate",
    items: [
      { href: "/conversations", label: "Conversations", icon: Network },
      { href: "/threat-intel", label: "Threat intelligence", icon: BarChart3 },
    ],
  },
  {
    title: "Configure",
    items: [
      { href: "/policies", label: "Policies", icon: Shield, roles: ["admin", "analyst"] },
      { href: "/tools", label: "Tools catalog", icon: Wrench },
      { href: "/models", label: "Models & routing", icon: Settings },
      { href: "/integrations", label: "Integrations", icon: Plug },
    ],
  },
  {
    title: "Develop",
    items: [
      { href: "/sandbox", label: "Sandbox", icon: FlaskConical },
      { href: "/api-keys", label: "API keys", icon: KeyRound, roles: ["admin"] },
      { href: "/quickstart", label: "Quickstart", icon: BookOpen },
    ],
  },
  {
    title: "Observe",
    items: [
      { href: "/analytics", label: "Analytics", icon: BarChart3 },
      { href: "/audit", label: "Audit log", icon: ScrollText },
      { href: "/health", label: "Health", icon: Activity },
    ],
  },
  {
    title: "Settings",
    items: [
      { href: "/settings/org", label: "Organization", icon: Building2, roles: ["admin"] },
      { href: "/settings/members", label: "Members", icon: Users, roles: ["admin"] },
      { href: "/settings/sso", label: "SSO", icon: Shield, roles: ["admin"] },
      { href: "/settings/billing", label: "Billing", icon: CreditCard, roles: ["admin"] },
    ],
  },
];

export function AppSidebar({ className }: { className?: string }) {
  const path = usePathname();
  const { data } = useSession();
  const role = data?.user?.role || "viewer";

  return (
    <aside
      className={cn(
        "flex h-full w-60 shrink-0 flex-col border-r bg-card",
        className
      )}
    >
      <div className="flex items-center gap-2 px-4 py-4">
        <Shield className="h-8 w-8 text-primary" aria-hidden />
        <div>
          <div className="text-sm font-bold tracking-tight">SentinelGuard</div>
          <div className="text-[10px] font-medium uppercase tracking-widest text-muted-foreground">
            AI Security Gateway
          </div>
        </div>
      </div>
      <Separator />
      <ScrollArea className="flex-1 px-2 py-3">
        <nav className="space-y-1">
          {SECTIONS.map((sec) => (
            <Collapsible key={sec.title} defaultOpen>
              <CollapsibleTrigger asChild>
                <Button
                  variant="ghost"
                  className="mb-1 flex h-8 w-full justify-between px-2 text-xs font-semibold text-muted-foreground"
                >
                  {sec.title}
                  <ChevronDown className="h-3 w-3" />
                </Button>
              </CollapsibleTrigger>
              <CollapsibleContent className="space-y-0.5">
                {sec.items.map((it) => {
                  if (it.roles && !it.roles.includes(role)) return null;
                  const Icon = it.icon;
                  const active = path === it.href || path.startsWith(it.href + "/");
                  return (
                    <Link
                      key={it.href}
                      href={it.href}
                      className={cn(
                        "flex items-center gap-2 rounded-lg px-3 py-2 text-sm transition-colors",
                        active
                          ? "bg-primary/15 font-medium text-primary"
                          : "text-muted-foreground hover:bg-muted hover:text-foreground"
                      )}
                    >
                      <Icon className="h-4 w-4 shrink-0" />
                      {it.label}
                    </Link>
                  );
                })}
              </CollapsibleContent>
            </Collapsible>
          ))}
        </nav>
      </ScrollArea>
      <div className="border-t p-3 text-[10px] text-muted-foreground">v1.0.0 · miniOrange</div>
    </aside>
  );
}
