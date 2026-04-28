"use client";

import { FileText, Image as ImageIcon, Paperclip, X, FileCode2, FileType2 } from "lucide-react";
import { useCallback, useId, useRef, useState } from "react";

const MAX_FILES = 8;
const MAX_FILE_BYTES = 10 * 1024 * 1024; // 10 MB
const MAX_TOTAL_BYTES = 30 * 1024 * 1024; // 30 MB

const ACCEPT =
  ".txt,.md,.csv,.tsv,.json,.jsonl,.yaml,.yml,.toml,.ini,.cfg,.env,.xml,.html,.css," +
  ".py,.ipynb,.js,.jsx,.ts,.tsx,.java,.kt,.go,.rs,.c,.h,.cpp,.cs,.swift,.rb,.php,.sh,.sql," +
  ".pdf,.docx," +
  "image/*,text/*,application/json,application/pdf," +
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document";

function humanSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(2)} MB`;
}

function fileIcon(file: File): React.ReactNode {
  const t = file.type || "";
  const name = file.name.toLowerCase();
  if (t.startsWith("image/")) return <ImageIcon className="w-4 h-4" />;
  if (t === "application/pdf" || name.endsWith(".pdf")) return <FileType2 className="w-4 h-4" />;
  if (
    name.endsWith(".docx") ||
    t === "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
  )
    return <FileType2 className="w-4 h-4" />;
  if (
    /\.(py|js|jsx|ts|tsx|java|kt|go|rs|c|h|cpp|cs|swift|rb|php|sh|sql|ipynb|json|yaml|yml|toml)$/i.test(
      name
    )
  )
    return <FileCode2 className="w-4 h-4" />;
  return <FileText className="w-4 h-4" />;
}

export type FileUploaderProps = {
  files: File[];
  onChange: (files: File[]) => void;
  disabled?: boolean;
  className?: string;
  /** Show inline previews for image files. */
  showImagePreviews?: boolean;
};

export function FileUploader({
  files,
  onChange,
  disabled,
  className = "",
  showImagePreviews = true,
}: FileUploaderProps) {
  const inputId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const addFiles = useCallback(
    (incoming: FileList | File[] | null) => {
      if (!incoming) return;
      const next = [...files];
      const list = Array.from(incoming as ArrayLike<File>);
      let total = next.reduce((s, f) => s + f.size, 0);
      let err: string | null = null;
      for (const f of list) {
        if (next.length >= MAX_FILES) {
          err = `Up to ${MAX_FILES} files per request.`;
          break;
        }
        if (f.size > MAX_FILE_BYTES) {
          err = `${f.name} is ${humanSize(f.size)} (limit ${humanSize(MAX_FILE_BYTES)} per file).`;
          continue;
        }
        if (total + f.size > MAX_TOTAL_BYTES) {
          err = `Total upload size would exceed ${humanSize(MAX_TOTAL_BYTES)}.`;
          break;
        }
        if (next.some((x) => x.name === f.name && x.size === f.size)) continue;
        next.push(f);
        total += f.size;
      }
      setError(err);
      onChange(next);
    },
    [files, onChange]
  );

  const remove = (idx: number) => {
    const next = files.slice();
    next.splice(idx, 1);
    onChange(next);
    setError(null);
  };

  return (
    <div className={className}>
      <div
        onDragOver={(e) => {
          if (disabled) return;
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          if (disabled) return;
          e.preventDefault();
          setDragOver(false);
          addFiles(e.dataTransfer.files);
        }}
        className={[
          "rounded-lg border-2 border-dashed px-3 py-3 text-xs transition-colors",
          dragOver
            ? "border-primary/60 bg-primary/5"
            : "border-line bg-panel2/50 hover:border-primary/40",
          disabled ? "opacity-50 pointer-events-none" : "",
        ].join(" ")}
      >
        <div className="flex items-center justify-between gap-2 flex-wrap">
          <div className="flex items-center gap-2 text-muted">
            <Paperclip className="w-4 h-4 text-primary" />
            <span>
              Drop files here, or{" "}
              <label
                htmlFor={inputId}
                className="text-primary cursor-pointer underline-offset-2 hover:underline"
              >
                browse
              </label>
              .
            </span>
          </div>
          <span className="text-[11px] text-muted">
            text · code · pdf · docx · images · up to {MAX_FILES} files / {humanSize(MAX_TOTAL_BYTES)}
          </span>
        </div>
        <input
          id={inputId}
          ref={inputRef}
          type="file"
          multiple
          accept={ACCEPT}
          className="hidden"
          onChange={(e) => {
            addFiles(e.target.files);
            if (inputRef.current) inputRef.current.value = "";
          }}
        />
      </div>

      {error && <div className="mt-2 text-[11px] text-danger">{error}</div>}

      {files.length > 0 && (
        <ul className="mt-2 flex flex-wrap gap-2">
          {files.map((f, i) => {
            const isImage = (f.type || "").startsWith("image/");
            const url = isImage && showImagePreviews ? URL.createObjectURL(f) : null;
            return (
              <li
                key={`${f.name}-${i}`}
                className="flex items-center gap-2 bg-panel2 border border-line rounded-lg pl-2 pr-1 py-1 text-xs"
              >
                {url ? (
                  <img
                    src={url}
                    alt={f.name}
                    className="w-6 h-6 rounded object-cover"
                    onLoad={() => URL.revokeObjectURL(url)}
                  />
                ) : (
                  <span className="text-muted">{fileIcon(f)}</span>
                )}
                <span className="font-mono max-w-[180px] truncate" title={f.name}>
                  {f.name}
                </span>
                <span className="text-[10px] text-muted">{humanSize(f.size)}</span>
                <button
                  type="button"
                  onClick={() => remove(i)}
                  className="ml-1 p-1 rounded hover:bg-line text-muted hover:text-danger"
                  aria-label={`Remove ${f.name}`}
                  disabled={disabled}
                >
                  <X className="w-3 h-3" />
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
