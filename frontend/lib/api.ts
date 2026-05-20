/** Browser-side API client for SentinelGuard backend */

export const API_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8080";

export const defaultSentinelKey =
  process.env.NEXT_PUBLIC_SENTINEL_KEY || "demo-key";

export type ApiHeaders = {
  sentinelKey?: string;
  userId?: string;
  userTier?: string;
  userRole?: string;
  sensitivity?: string;
  authType?: string;
  resource?: string;
};

export async function apiFetch<T>(
  path: string,
  init?: RequestInit & ApiHeaders
): Promise<T> {
  const {
    sentinelKey,
    userId,
    userTier,
    userRole,
    sensitivity,
    authType,
    resource,
    ...rest
  } = init || {};
  const headers = buildBrowserHeaders({
    sentinelKey,
    userId,
    userTier,
    userRole,
    sensitivity,
    authType,
    resource,
    headers: rest.headers as HeadersInit,
  });

  const controller = new AbortController();
  const timeoutMs = 15_000;
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      ...rest,
      headers,
      cache: "no-store",
      signal: controller.signal,
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new Error(`${path}: request timed out after ${timeoutMs / 1000}s (is the backend up at ${API_URL}?)`);
    }
    throw err;
  } finally {
    clearTimeout(timeoutId);
  }
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${path} ${res.status}: ${text.slice(0, 200)}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export type AttachmentPayload = {
  filename: string;
  mime_type?: string;
  data_b64: string;
};

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

export async function chatV2(
  body: {
    prompt: string;
    conv_id?: string | null;
    model_pref?: string;
    simulate?: boolean;
  },
  headers?: ApiHeaders
) {
  return apiFetch<Record<string, unknown>>("/api/v2/chat", {
    method: "POST",
    body: JSON.stringify(body),
    ...headers,
  });
}

export async function chatCompletions(
  args: {
    prompt: string;
    model?: string;
    attachments?: AttachmentPayload[];
    files?: File[];
  } & ApiHeaders
) {
  let attachments = args.attachments;
  if (!attachments && args.files?.length) {
    attachments = await Promise.all(args.files.map(fileToAttachment));
  }
  const { files: _files, ...rest } = args;
  return apiFetch<Record<string, unknown>>("/v1/chat/completions", {
    method: "POST",
    body: JSON.stringify({
      model: args.model || "gpt-4o-mini",
      messages: [{ role: "user", content: args.prompt }],
      ...(attachments?.length ? { attachments } : {}),
    }),
    ...rest,
  });
}

/** Build fetch headers for browser calls (shared by apiFetch + sandbox OpenAI path). */
function buildBrowserHeaders(
  fields: ApiHeaders & { headers?: HeadersInit }
): Record<string, string> {
  const {
    sentinelKey,
    userId,
    userTier,
    userRole,
    sensitivity,
    authType,
    resource,
    headers: incoming,
  } = fields;
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    "X-Sentinel-Key": sentinelKey ?? defaultSentinelKey,
    ...(typeof incoming === "object" && incoming !== null && !(incoming instanceof Headers)
      ? (incoming as Record<string, string>)
      : {}),
  };
  if (userId) headers["X-User-Id"] = userId;
  if (userTier) headers["X-User-Tier"] = userTier;
  if (userRole) headers["X-User-Role"] = userRole;
  if (sensitivity) headers["X-Sensitivity"] = sensitivity;
  if (authType) headers["X-Auth-Type"] = authType;
  if (resource) headers["X-Resource"] = resource;
  return headers;
}

/**
 * Maps `/v1/chat/completions` JSON to the flat Sandbox shape (same as `/api/v2/chat`).
 * OpenAI response nests gateway fields under `sentinel` and assistant text under `choices`.
 */
export function normalizeOpenAiSandboxRow(body: Record<string, unknown>): Record<string, unknown> {
  const sentinel = body.sentinel as Record<string, unknown> | undefined;
  const choices = body.choices as Array<{ message?: { content?: string } }> | undefined;
  const assistantText = choices?.[0]?.message?.content ?? "";

  if (!sentinel) {
    return { ...body, message: assistantText };
  }

  const intentRaw = sentinel.intent;
  const intent_detail =
    typeof sentinel.intent_detail === "object" && sentinel.intent_detail !== null
      ? sentinel.intent_detail
      : typeof intentRaw === "string"
        ? { intent: intentRaw }
        : undefined;

  return {
    ...sentinel,
    ...(intent_detail !== undefined ? { intent_detail } : {}),
    message:
      assistantText ||
      (typeof sentinel.message === "string" ? sentinel.message : "") ||
      "",
    _openai_raw: body,
  };
}

/**
 * OpenAI-compatible chat completions for Sandbox: normalizes 200 responses and maps 403
 * `detail.sentinel` (blocked request) into the same flat shape so the UI can render verdict/risk/message.
 */
export async function fetchChatCompletionsSandboxNormalized(
  args: {
    prompt: string;
    model?: string;
    attachments?: AttachmentPayload[];
    files?: File[];
  } & ApiHeaders
): Promise<Record<string, unknown>> {
  let attachments = args.attachments;
  if (!attachments && args.files?.length) {
    attachments = await Promise.all(args.files.map(fileToAttachment));
  }
  const { files: _files, prompt, model, attachments: _att, ...headerRest } = args;

  const headers = buildBrowserHeaders(headerRest);

  const res = await fetch(`${API_URL}/v1/chat/completions`, {
    method: "POST",
    headers,
    cache: "no-store",
    body: JSON.stringify({
      model: model || "gpt-4o-mini",
      messages: [{ role: "user", content: prompt }],
      ...(attachments?.length ? { attachments } : {}),
    }),
  });

  const text = await res.text();
  let parsed: Record<string, unknown> | null = null;
  try {
    parsed = text ? (JSON.parse(text) as Record<string, unknown>) : null;
  } catch {
    throw new Error(`/v1/chat/completions ${res.status}: ${text.slice(0, 200)}`);
  }

  if (res.ok && parsed) {
    return normalizeOpenAiSandboxRow(parsed);
  }

  const detail = parsed?.detail as Record<string, unknown> | string | undefined;
  const detailObj =
    typeof detail === "object" && detail !== null && !Array.isArray(detail)
      ? detail
      : undefined;

  const sentinel =
    (detailObj?.sentinel as Record<string, unknown> | undefined) ||
    (parsed?.sentinel as Record<string, unknown> | undefined);

  if (sentinel && typeof sentinel === "object") {
    const detailMsg =
      typeof detailObj?.message === "string"
        ? detailObj.message
        : typeof parsed?.message === "string"
          ? parsed.message
          : "";
    const blockedMsg =
      detailMsg ||
      (typeof sentinel.message === "string" ? sentinel.message : "") ||
      (typeof sentinel.block_reason === "string" ? sentinel.block_reason : "") ||
      "Request blocked";

    return {
      ...sentinel,
      message: blockedMsg,
      verdict: sentinel.verdict ?? "BLOCK",
      agent_steps: Array.isArray(sentinel.agent_steps)
        ? sentinel.agent_steps
        : [{ stage: 4, name: "early_gate" }],
      _openai_error: parsed,
    };
  }

  throw new Error(`/v1/chat/completions ${res.status}: ${text.slice(0, 280)}`);
}

export async function endSession(convId: string, headers?: ApiHeaders) {
  return apiFetch<{ status: string }>(`/api/v2/session/${convId}`, {
    method: "DELETE",
    ...headers,
  });
}
