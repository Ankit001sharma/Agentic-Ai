import { Suspense } from "react";
import { LoginForm } from "./login-form";
import { Skeleton } from "@/components/ui/skeleton";

export default function LoginPage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-muted/30 px-4">
      <div className="mb-8 text-center">
        <h1 className="text-2xl font-bold text-primary">SentinelGuard</h1>
        <p className="text-sm text-muted-foreground">Sign in to the security gateway console</p>
      </div>
      <Suspense fallback={<Skeleton className="h-64 w-full max-w-md" />}>
        <LoginForm />
      </Suspense>
    </div>
  );
}
