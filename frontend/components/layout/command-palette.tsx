"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";

const NAV: { href: string; label: string; group: string }[] = [
  { group: "Operate", href: "/dashboard", label: "Dashboard" },
  { group: "Operate", href: "/live", label: "Live stream" },
  { group: "Operate", href: "/incidents", label: "Incidents" },
  { group: "Operate", href: "/review", label: "Review queue" },
  { group: "Investigate", href: "/conversations", label: "Conversations" },
  { group: "Investigate", href: "/threat-intel", label: "Threat intelligence" },
  { group: "Configure", href: "/policies", label: "Policies" },
  { group: "Configure", href: "/tools", label: "Tools catalog" },
  { group: "Configure", href: "/models", label: "Models & routing" },
  { group: "Configure", href: "/integrations", label: "Integrations" },
  { group: "Develop", href: "/sandbox", label: "Sandbox" },
  { group: "Develop", href: "/api-keys", label: "API keys" },
  { group: "Develop", href: "/quickstart", label: "Quickstart" },
  { group: "Observe", href: "/analytics", label: "Analytics" },
  { group: "Observe", href: "/audit", label: "Audit log" },
  { group: "Observe", href: "/health", label: "Health" },
  { group: "Settings", href: "/settings/org", label: "Organization" },
  { group: "Settings", href: "/settings/members", label: "Members" },
  { group: "Settings", href: "/settings/sso", label: "SSO" },
  { group: "Settings", href: "/settings/billing", label: "Billing" },
];

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const router = useRouter();

  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.key === "k" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setOpen((o) => !o);
      }
    };
    document.addEventListener("keydown", down);
    return () => document.removeEventListener("keydown", down);
  }, []);

  const run = useCallback(
    (href: string) => {
      setOpen(false);
      router.push(href);
    },
    [router]
  );

  const groups = [...new Set(NAV.map((n) => n.group))];

  return (
    <CommandDialog open={open} onOpenChange={setOpen}>
      <CommandInput placeholder="Jump to page…" />
      <CommandList>
        <CommandEmpty>No results.</CommandEmpty>
        {groups.map((g) => (
          <CommandGroup key={g} heading={g}>
            {NAV.filter((n) => n.group === g).map((n) => (
              <CommandItem key={n.href} value={`${n.label} ${n.href}`} onSelect={() => run(n.href)}>
                {n.label}
              </CommandItem>
            ))}
          </CommandGroup>
        ))}
      </CommandList>
    </CommandDialog>
  );
}
