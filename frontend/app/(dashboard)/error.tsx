"use client";

import { useEffect } from "react";
import { Button } from "@/components/ui/button";

export default function DashboardError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("dashboard_error", error);
  }, [error]);

  return (
    <div className="flex flex-col items-center justify-center gap-4 py-16">
      <h2 className="text-lg font-semibold">Something went wrong</h2>
      <p className="max-w-md text-center text-sm text-muted-foreground">{error.message}</p>
      <Button onClick={() => reset()}>Try again</Button>
    </div>
  );
}
