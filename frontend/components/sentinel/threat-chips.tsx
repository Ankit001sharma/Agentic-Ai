import { Badge } from "@/components/ui/badge";

export function ThreatChips({ categories }: { categories: string[] }) {
  if (!categories?.length) return null;
  return (
    <div className="flex flex-wrap gap-1">
      {categories.map((c) => (
        <Badge key={c} variant="outline" className="text-[10px] font-normal">
          {c}
        </Badge>
      ))}
    </div>
  );
}
