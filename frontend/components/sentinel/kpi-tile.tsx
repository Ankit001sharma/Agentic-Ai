import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

export function KpiTile({
  label,
  value,
  sub,
  className,
  valueClassName,
}: {
  label: string;
  value: React.ReactNode;
  sub?: string;
  className?: string;
  valueClassName?: string;
}) {
  return (
    <Card className={cn("shadow-sm", className)}>
      <CardContent className="p-4">
        <div className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
          {label}
        </div>
        <div className={cn("mt-1 text-2xl font-bold tabular-nums", valueClassName)}>{value}</div>
        {sub ? <div className="mt-1 text-xs text-muted-foreground">{sub}</div> : null}
      </CardContent>
    </Card>
  );
}
