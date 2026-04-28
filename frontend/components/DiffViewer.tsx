"use client";

export function DiffViewer({
  before,
  after,
  beforeLabel = "Before",
  afterLabel = "After",
}: {
  before?: string;
  after?: string;
  beforeLabel?: string;
  afterLabel?: string;
}) {
  if (!before && !after) return null;
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
      <div className="panel-pad">
        <div className="text-[11px] uppercase text-muted mb-2">{beforeLabel}</div>
        <pre className="text-xs whitespace-pre-wrap break-words text-text/90">
          {before || ""}
        </pre>
      </div>
      <div className="panel-pad border-l-2 border-primary/40">
        <div className="text-[11px] uppercase text-primary mb-2">{afterLabel}</div>
        <pre className="text-xs whitespace-pre-wrap break-words text-text/90">
          {after || ""}
        </pre>
      </div>
    </div>
  );
}
