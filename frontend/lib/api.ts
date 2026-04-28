export const API_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
export const SENTINEL_KEY =
  process.env.NEXT_PUBLIC_SENTINEL_KEY || "demo-key";

export type CallContext = {
  userId?: string;
  tier?: string;
  sensitivity?: string;
  authType?: string;
  role?: string;
  resource?: string;
};

export async function api<T = any>(
  path: string,
  init?: RequestInit & CallContext
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    "X-Sentinel-Key": SENTINEL_KEY,
    ...(init?.headers as Record<string, string>),
  };
  if (init?.userId) headers["X-User-Id"] = init.userId;
  if (init?.tier) headers["X-User-Tier"] = init.tier;
  if (init?.sensitivity) headers["X-Sensitivity"] = init.sensitivity;
  if (init?.authType) headers["X-Auth-Type"] = init.authType;
  if (init?.role) headers["X-User-Role"] = init.role;
  if (init?.resource) headers["X-Resource"] = init.resource;
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers,
    cache: "no-store",
  });
  if (!res.ok && res.status !== 403) {
    throw new Error(`API ${path} failed: ${res.status}`);
  }
  return res.json();
}

export type AttachmentPayload = {
  filename: string;
  mime_type?: string;
  data_b64: string;
};

/**
 * Read a browser File and return a base64-encoded payload ready to send to
 * the SentinelGuard chat endpoint. Strips the "data:<mime>;base64," prefix
 * so the backend gets a clean payload.
 */
export function fileToAttachment(file: File): Promise<AttachmentPayload> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(reader.error || new Error("FileReader error"));
    reader.onload = () => {
      const result = reader.result as string;
      const idx = result.indexOf(",");
      const data_b64 = idx >= 0 ? result.slice(idx + 1) : result;
      resolve({
        filename: file.name,
        mime_type: file.type || undefined,
        data_b64,
      });
    };
    reader.readAsDataURL(file);
  });
}

export async function filesToAttachments(
  files: File[] | FileList | null | undefined
): Promise<AttachmentPayload[]> {
  if (!files) return [];
  const arr = Array.from(files as ArrayLike<File>);
  return Promise.all(arr.map(fileToAttachment));
}

export async function chatCompletions(
  args: {
    prompt: string;
    model?: string;
    attachments?: AttachmentPayload[];
    files?: File[] | FileList;
  } & CallContext
) {
  let attachments = args.attachments;
  if (!attachments && args.files) {
    attachments = await filesToAttachments(args.files);
  }
  return api<any>("/v1/chat/completions", {
    method: "POST",
    userId: args.userId,
    tier: args.tier,
    sensitivity: args.sensitivity,
    authType: args.authType,
    role: args.role,
    resource: args.resource,
    body: JSON.stringify({
      model: args.model || "gpt-4o-mini",
      messages: [{ role: "user", content: args.prompt }],
      ...(attachments && attachments.length > 0 ? { attachments } : {}),
    }),
  });
}
