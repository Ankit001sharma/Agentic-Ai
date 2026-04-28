"use client";

import { Check, X } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

type Policy = {
  id: number;
  name: string;
  rego: string;
  enabled: boolean;
  suggested: boolean;
  suggested_by: string | null;
  suggested_reason: string | null;
  approved: boolean;
  created_at: string;
};

export default function PoliciesPage() {
  const [items, setItems] = useState<Policy[]>([]);

  async function refresh() {
    try {
      const i = await api<Policy[]>("/api/policies");
      setItems(i);
    } catch {
      /* ignore */
    }
  }

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 6000);
    return () => clearInterval(id);
  }, []);

  async function act(id: number, action: "approve" | "reject") {
    await api(`/api/policies/${id}/${action}`, { method: "POST" });
    await refresh();
  }

  const active = items.filter((p) => !p.suggested);
  const suggested = items.filter((p) => p.suggested);

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold">Policies</h1>
        <p className="text-muted text-sm">
          Active OPA-backed policies plus AI-suggested rules from the Adaptive Risk Agent.
        </p>
      </header>

      <section>
        <h2 className="text-sm font-semibold uppercase tracking-wide text-muted mb-2">
          Active OPA bundle
        </h2>
        <div className="panel-pad">
          <div className="text-xs font-mono whitespace-pre text-text/80">
            {`package sentinel\n\n# Default allow with risk-gate enforcement; deny when verdict==BLOCK,\n# or model not in user's allowed_models, or region restricted.\n# See infra/opa/policies/sentinel.rego for source.`}
          </div>
          {active.length > 0 && (
            <div className="mt-3 space-y-2">
              {active.map((p) => (
                <div key={p.id} className="text-xs border border-line rounded p-2">
                  <div className="font-semibold">{p.name}</div>
                  <pre className="text-muted whitespace-pre-wrap">{p.rego}</pre>
                </div>
              ))}
            </div>
          )}
        </div>
      </section>

      <section>
        <h2 className="text-sm font-semibold uppercase tracking-wide text-muted mb-2">
          AI-Suggested Rules
        </h2>
        {suggested.length === 0 ? (
          <div className="panel-pad text-center text-muted py-8">
            No suggestions yet. The Adaptive Risk Agent emits rules after recurring
            attack patterns are detected.
          </div>
        ) : (
          <ul className="space-y-3">
            {suggested.map((p) => (
              <li key={p.id} className="panel-pad">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <div className="font-semibold text-sm">{p.name}</div>
                    <div className="text-xs text-muted mt-0.5">
                      suggested by{" "}
                      <span className="text-text">{p.suggested_by}</span>{" "}
                      — {p.suggested_reason}
                    </div>
                  </div>
                  <div className="flex gap-2">
                    {!p.approved && (
                      <button
                        onClick={() => act(p.id, "approve")}
                        className="btn-primary"
                      >
                        <Check className="w-4 h-4 inline mr-1" />
                        Approve
                      </button>
                    )}
                    <button
                      onClick={() => act(p.id, "reject")}
                      className="btn"
                    >
                      <X className="w-4 h-4 inline mr-1" />
                      Reject
                    </button>
                  </div>
                </div>
                <pre className="mt-3 text-[11px] text-text/80 whitespace-pre-wrap font-mono bg-panel2 p-3 rounded border border-line">
                  {p.rego}
                </pre>
                {p.approved && (
                  <div className="text-success text-xs mt-2">✓ Approved & enabled</div>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
