"use client";

import { AlertCircle, CheckCircle2, Clock3, Loader2 } from "lucide-react";
import type { ReactNode } from "react";

import { StatusBadge } from "@/components/status-badge";
import type { WorkbenchArtifactSummary, WorkbenchStatus, WorkbenchTone } from "@/lib/types";

interface WorkbenchStatusBadgeProps {
  status: WorkbenchStatus;
}

export function WorkbenchStatusBadge({ status }: WorkbenchStatusBadgeProps) {
  const Icon =
    status.tone === "success"
      ? CheckCircle2
      : status.tone === "error"
        ? AlertCircle
        : status.tone === "warning"
          ? Clock3
          : undefined;
  return (
    <StatusBadge icon={Icon} tone={status.tone}>
      {status.label}
    </StatusBadge>
  );
}

interface WorkbenchCardProps {
  artifact: WorkbenchArtifactSummary;
  onOpen: (href: string) => void;
}

export function WorkbenchArtifactCard({ artifact, onOpen }: WorkbenchCardProps) {
  return (
    <article className="workbench-card">
      <button onClick={() => onOpen(artifact.href)} type="button">
        <span className="workbench-card-kind">{kindLabel(artifact.kind)}</span>
        <strong>{artifact.title}</strong>
        <small>{artifact.repo}</small>
      </button>
      <div className="workbench-card-meta">
        <WorkbenchStatusBadge status={artifact.status} />
        {artifact.files_changed > 0 ? <span>{artifact.files_changed} files changed</span> : null}
        {artifact.validation ? <span>Validation {artifact.validation}</span> : null}
        {artifact.checkpoint ? <span>Checkpoint {artifact.checkpoint}</span> : null}
      </div>
    </article>
  );
}

interface WorkbenchSectionProps {
  title: string;
  children: ReactNode;
  empty?: string;
  count?: number;
}

export function WorkbenchSection({ title, children, empty, count }: WorkbenchSectionProps) {
  return (
    <section className="workbench-section">
      <header>
        <h2>{title}</h2>
        {typeof count === "number" ? <span>{count}</span> : null}
      </header>
      {count === 0 && empty ? <p className="workbench-empty">{empty}</p> : children}
    </section>
  );
}

interface StateProps {
  label: string;
}

export function WorkbenchLoading({ label }: StateProps) {
  return (
    <div className="workbench-state" aria-label={label}>
      <Loader2 aria-hidden="true" size={18} />
      <span>{label}</span>
    </div>
  );
}

export function WorkbenchError({ label }: StateProps) {
  return (
    <div className="workbench-state is-error" role="alert">
      <AlertCircle aria-hidden="true" size={18} />
      <span>{label}</span>
    </div>
  );
}

interface DetailSectionProps {
  title: string;
  children: ReactNode;
}

export function DetailSection({ title, children }: DetailSectionProps) {
  return (
    <section className="workbench-detail-section">
      <h2>{title}</h2>
      {children}
    </section>
  );
}

export function toneForValue(value: string): WorkbenchTone {
  if (["passed", "completed", "success", "succeeded", "available", "ready"].includes(value)) {
    return "success";
  }
  if (["failed", "blocked", "timed_out", "failure"].includes(value)) {
    return "error";
  }
  if (["requires_approval", "skipped", "partial", "rolled_back"].includes(value)) {
    return "warning";
  }
  return "neutral";
}

export function formatDate(value: string | null) {
  if (!value) {
    return "";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}

function kindLabel(kind: string) {
  return kind.replaceAll("_", " ");
}
