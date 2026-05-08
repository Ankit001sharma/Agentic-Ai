import NextAuth from "next-auth";
import Credentials from "next-auth/providers/credentials";

const dashboardPassword = process.env.DASHBOARD_PASSWORD || "sentinel";

export const { handlers, signIn, signOut, auth } = NextAuth({
  trustHost: true,
  providers: [
    Credentials({
      name: "credentials",
      credentials: {
        email: { label: "Email", type: "email" },
        password: { label: "Password", type: "password" },
      },
      async authorize(credentials) {
        if (!credentials?.email || !credentials?.password) return null;
        if (credentials.password !== dashboardPassword) return null;
        const email = String(credentials.email).toLowerCase();
        let role: "admin" | "analyst" | "viewer" = "viewer";
        if (email.includes("admin")) role = "admin";
        else if (email.includes("analyst")) role = "analyst";
        return {
          id: email,
          email,
          name: email.split("@")[0],
          role,
          orgId: "org-demo",
          tier: "enterprise",
        };
      },
    }),
  ],
  session: { strategy: "jwt", maxAge: 60 * 60 * 8 },
  pages: { signIn: "/login" },
  callbacks: {
    async jwt({ token, user }) {
      if (user) {
        token.id = user.id;
        token.role = user.role;
        token.orgId = user.orgId;
        token.tier = user.tier;
      }
      return token;
    },
    async session({ session, token }) {
      if (session.user) {
        session.user.id = String(token.id ?? token.sub ?? "");
        session.user.role = (token.role as "admin" | "analyst" | "viewer") || "viewer";
        session.user.orgId = String(token.orgId ?? "org-demo");
        session.user.tier = String(token.tier ?? "free");
      }
      return session;
    },
  },
});
