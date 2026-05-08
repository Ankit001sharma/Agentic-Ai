import { type DefaultSession } from "next-auth";

declare module "next-auth" {
  interface Session {
    user: DefaultSession["user"] & {
      id: string;
      role: "admin" | "analyst" | "viewer";
      orgId: string;
      tier: string;
    };
  }

  interface User {
    role?: "admin" | "analyst" | "viewer";
    orgId?: string;
    tier?: string;
  }
}

declare module "next-auth/jwt" {
  interface JWT {
    role?: string;
    orgId?: string;
    tier?: string;
  }
}
