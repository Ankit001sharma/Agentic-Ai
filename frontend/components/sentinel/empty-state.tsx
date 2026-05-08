import { cn } from "@/lib/utils";

export function EmptyState({
  title,
  description,
  className,
  children,
}: {
  title: string;
  description?: string;
  className?: string;
  children?: React.ReactNode;
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center rounded-xl border border-dashed py-16 text-center",
        className
      )}
    >
      <h3 className="text-lg font-semibold">{title}</h3>
      {description ? <p className="mt-2 max-w-md text-sm text-muted-foreground">{description}</p> : null}
      {children ? <div className="mt-4">{children}</div> : null}
    </div>
  );
}
