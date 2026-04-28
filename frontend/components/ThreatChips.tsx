"use client";

import {
  AlertTriangle,
  Bot,
  Bug,
  Code2,
  Eye,
  EyeOff,
  FileWarning,
  Key,
  Lock,
  Repeat,
  Skull,
  UserCog,
} from "lucide-react";
import type { ReactNode } from "react";

const META: Record<string, { color: string; icon: ReactNode; label: string }> = {
  PROMPT_INJECTION: {
    color: "border-danger/40 text-danger bg-danger/10",
    icon: <AlertTriangle className="w-3 h-3" />,
    label: "Prompt Injection",
  },
  JAILBREAK: {
    color: "border-danger/40 text-danger bg-danger/10",
    icon: <Skull className="w-3 h-3" />,
    label: "Jailbreak",
  },
  ROLE_OVERRIDE: {
    color: "border-warning/50 text-warning bg-warning/10",
    icon: <UserCog className="w-3 h-3" />,
    label: "Role Override",
  },
  SYSTEM_PROMPT_EXTRACTION: {
    color: "border-warning/50 text-warning bg-warning/10",
    icon: <Eye className="w-3 h-3" />,
    label: "System Prompt Leak",
  },
  HIDDEN_INSTRUCTION: {
    color: "border-warning/50 text-warning bg-warning/10",
    icon: <EyeOff className="w-3 h-3" />,
    label: "Hidden Instruction",
  },
  PII: {
    color: "border-primary/40 text-primary bg-primary/10",
    icon: <Eye className="w-3 h-3" />,
    label: "PII",
  },
  SECRET: {
    color: "border-danger/40 text-danger bg-danger/10",
    icon: <Key className="w-3 h-3" />,
    label: "Secret",
  },
  TOXIC: {
    color: "border-danger/40 text-danger bg-danger/10",
    icon: <Skull className="w-3 h-3" />,
    label: "Toxic",
  },
  CODE_IP: {
    color: "border-warning/50 text-warning bg-warning/10",
    icon: <Code2 className="w-3 h-3" />,
    label: "Code/IP",
  },
  REPEAT_ATTACK: {
    color: "border-danger/40 text-danger bg-danger/10",
    icon: <Repeat className="w-3 h-3" />,
    label: "Repeat Attack",
  },
  DANGEROUS_CODE: {
    color: "border-danger/50 text-danger bg-danger/10",
    icon: <Skull className="w-3 h-3" />,
    label: "Dangerous Code",
  },
  POLICY_VIOLATION: {
    color: "border-warning/50 text-warning bg-warning/10",
    icon: <AlertTriangle className="w-3 h-3" />,
    label: "Policy Violation",
  },
  HALLUCINATION: {
    color: "border-warning/50 text-warning bg-warning/10",
    icon: <AlertTriangle className="w-3 h-3" />,
    label: "Hallucination",
  },
  SPAM: {
    color: "border-muted text-muted bg-line",
    icon: <Repeat className="w-3 h-3" />,
    label: "Spam",
  },
  MALWARE: {
    color: "border-danger/50 text-danger bg-danger/10",
    icon: <Bug className="w-3 h-3" />,
    label: "Malware Request",
  },
  RBAC_VIOLATION: {
    color: "border-danger/40 text-danger bg-danger/10",
    icon: <Lock className="w-3 h-3" />,
    label: "RBAC Violation",
  },
  UNVERIFIED_INTERNAL: {
    color: "border-warning/50 text-warning bg-warning/10",
    icon: <FileWarning className="w-3 h-3" />,
    label: "Unverified Internal",
  },
  NHI_VIOLATION: {
    color: "border-warning/60 text-warning bg-warning/10",
    icon: <Bot className="w-3 h-3" />,
    label: "Non-Human Identity",
  },
};

export function ThreatChips({ categories }: { categories: string[] }) {
  if (!categories?.length) return null;
  return (
    <div className="flex flex-wrap gap-1">
      {categories.map((c) => {
        const m = META[c] || {
          color: "border-muted text-muted bg-line",
          icon: <AlertTriangle className="w-3 h-3" />,
          label: c,
        };
        return (
          <span key={c} className={`chip ${m.color}`}>
            {m.icon}
            {m.label}
          </span>
        );
      })}
    </div>
  );
}

export function VerdictChip({ verdict }: { verdict?: string }) {
  if (!verdict) return null;
  const v = verdict.toUpperCase();
  const map: Record<string, string> = {
    ALLOW: "border-success/40 text-success bg-success/10",
    MASK: "border-warning/50 text-warning bg-warning/10",
    ESCALATE: "border-warning/60 text-warning bg-warning/10",
    BLOCK: "border-danger/50 text-danger bg-danger/10",
    CLEAN: "border-success/40 text-success bg-success/10",
    REDACT: "border-warning/50 text-warning bg-warning/10",
  };
  return (
    <span className={`chip ${map[v] || "border-muted text-muted"}`}>{v}</span>
  );
}
