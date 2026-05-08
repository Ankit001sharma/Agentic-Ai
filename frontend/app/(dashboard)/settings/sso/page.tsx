import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function SettingsSsoPage() {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">SSO</h1>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">SAML / OIDC</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">
          Configure IdP metadata here in a future release. NextAuth providers can be extended in{" "}
          <code className="text-xs">auth.ts</code>.
        </CardContent>
      </Card>
    </div>
  );
}
