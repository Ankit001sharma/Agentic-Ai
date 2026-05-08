import { AppSidebar } from "@/components/layout/app-sidebar";
import { AppTopbar } from "@/components/layout/app-topbar";
import { CommandPalette } from "@/components/layout/command-palette";
import { auth } from "@/auth";
import { redirect } from "next/navigation";

export default async function DashboardLayout({ children }: { children: React.ReactNode }) {
  const session = await auth();
  if (!session?.user) {
    redirect("/login");
  }

  return (
    <div className="flex h-screen min-h-0 overflow-hidden">
      <AppSidebar />
      <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
        <AppTopbar />
        <main className="min-h-0 flex-1 overflow-y-auto p-6">{children}</main>
      </div>
      <CommandPalette />
    </div>
  );
}
