import "./globals.css";
import type { Metadata } from "next";
import { Nav } from "@/components/Nav";
import { AlertToast } from "@/components/AlertToast";

export const metadata: Metadata = {
  title: "SentinelGuard — AI Security Gateway",
  description:
    "Agentic AI security gateway: parallel scanners, 4-tier risk gate, OPA, model routing, HITL review, adaptive learning.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <div className="flex min-h-screen">
          <Nav />
          <main className="flex-1 p-6 overflow-x-hidden">{children}</main>
        </div>
        <AlertToast />
      </body>
    </html>
  );
}
