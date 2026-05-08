import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function SettingsBillingPage() {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Billing</h1>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Plan</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">
          Enterprise evaluation — contact miniOrange for usage-based billing integration.
        </CardContent>
      </Card>
    </div>
  );
}
