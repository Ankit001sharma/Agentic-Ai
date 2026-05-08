"use client";

import { useSession } from "next-auth/react";
import type { ApiHeaders } from "@/lib/api";

export function useApiHeaders(): ApiHeaders {
  const { data } = useSession();
  const u = data?.user;
  return {
    userId: u?.id || u?.email || "dashboard-user",
    userTier: u?.tier || "enterprise",
    userRole: u?.role || "viewer",
  };
}
