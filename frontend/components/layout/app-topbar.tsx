"use client";

import { signOut, useSession } from "next-auth/react";
import { Bell, LogOut, Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useUiStore } from "@/lib/store/ui-store";
import { apiFetch } from "@/lib/api";
import { useQuery } from "@tanstack/react-query";
import { useApiHeaders } from "@/lib/hooks/use-api-headers";

export function AppTopbar() {
  const { data } = useSession();
  const { theme, setTheme } = useTheme();
  const { simulateEnv, setSimulateEnv } = useUiStore();
  const headers = useApiHeaders();

  const health = useQuery({
    queryKey: ["system-health"],
    queryFn: () =>
      apiFetch<{ overall: string }>("/api/system/health", {
        ...headers,
      }),
    refetchInterval: 30_000,
  });

  const ok = health.data?.overall === "healthy";

  return (
    <header className="flex h-14 items-center justify-between gap-4 border-b bg-background px-4">
      <div className="flex items-center gap-3">
        <Badge variant="outline" className="font-mono text-[10px]">
          {data?.user?.orgId ?? "org"}
        </Badge>
        <button
          type="button"
          onClick={() => setSimulateEnv(!simulateEnv)}
          className="rounded-md border px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide hover:bg-muted"
        >
          {simulateEnv ? "Simulate" : "Live"}
        </button>
        <Badge variant={ok ? "success" : "warning"} className="text-[10px]">
          {health.isLoading ? "Health…" : ok ? "Systems OK" : "Degraded"}
        </Badge>
      </div>
      <div className="flex items-center gap-2">
        <span className="hidden text-xs text-muted-foreground md:inline">
          <kbd className="rounded border bg-muted px-1">⌘K</kbd> search
        </span>
        <Button variant="ghost" size="icon" asChild>
          <Link href="/review" aria-label="Notifications">
            <Bell className="h-4 w-4" />
          </Link>
        </Button>
        <Button
          variant="ghost"
          size="icon"
          onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
          aria-label="Toggle theme"
        >
          {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
        </Button>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" size="sm" className="max-w-[160px] truncate">
              {data?.user?.email ?? "Account"}
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-56">
            <DropdownMenuLabel>
              <div className="text-xs font-normal text-muted-foreground">Signed in</div>
              <div className="truncate font-medium">{data?.user?.email}</div>
              <div className="text-xs text-muted-foreground">Role: {data?.user?.role}</div>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={() => signOut({ callbackUrl: "/login" })}>
              <LogOut className="mr-2 h-4 w-4" />
              Sign out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}
