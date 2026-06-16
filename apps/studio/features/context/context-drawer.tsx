"use client";

import {
  Code2,
  Database,
  FileCheck2,
  GitBranch,
  FolderGit2,
  PanelRightClose,
  ShieldCheck,
  Waypoints,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { ArtifactCard } from "@/components/artifact-card";
import { IconButton } from "@/components/icon-button";
import { StatusBadge } from "@/components/status-badge";
import type {
  ConversationDetail,
  DeliberationMode,
  PolicyProfile,
  ProviderStatusResponse,
  RecentRepo,
} from "@/lib/types";

interface ContextDrawerProps {
  detail: ConversationDetail | null;
  mode: DeliberationMode;
  provider: ProviderStatusResponse | null;
  policy: PolicyProfile | null;
  repos: RecentRepo[];
  mobileOpen: boolean;
  collapsed: boolean;
  onCloseMobile: () => void;
  onToggleCollapsed: () => void;
}

export function ContextDrawer({
  detail,
  mode,
  provider,
  policy,
  repos,
  mobileOpen,
  collapsed,
  onCloseMobile,
  onToggleCollapsed,
}: ContextDrawerProps) {
  const conversation = detail?.conversation ?? null;
  const attachedRepo = repos.find((repo) => repo.id === conversation?.repo_profile_id) ?? null;
  const decisionCount = conversation?.linked_decision_count ?? 0;
  const validationCount = conversation?.validation_run_count ?? 0;
  const codingCount = conversation?.coding_request_count ?? 0;
  const artifactCount = decisionCount + validationCount + codingCount;

  if (collapsed) {
    return <aside aria-hidden="true" className="context-drawer is-collapsed" />;
  }

  return (
    <aside className={`context-drawer ${mobileOpen ? "is-open" : ""}`} aria-label="Context">
      <div className="drawer-heading">
        <div>
          <p>Context</p>
          <h2>Thread details</h2>
        </div>
        <div className="drawer-actions">
          <IconButton
            className="desktop-only"
            icon={PanelRightClose}
            label="Collapse context"
            onClick={onToggleCollapsed}
          />
          <IconButton
            className="mobile-only"
            icon={PanelRightClose}
            label="Close context"
            onClick={onCloseMobile}
          />
        </div>
      </div>

      <div className="context-status-row" aria-label="Thread status">
        <StatusBadge icon={Waypoints} tone="accent">
          {modeLabel(mode)}
        </StatusBadge>
        <StatusBadge icon={Database} tone={provider?.active_provider ? "cyan" : "neutral"}>
          {provider?.active_label ?? "Local deterministic mode"}
        </StatusBadge>
      </div>

      <ContextItem
        icon={FolderGit2}
        label="Repo"
        value={attachedRepo?.name ?? conversation?.repo_name ?? "No repo attached"}
        detail={attachedRepo?.path ?? conversation?.workspace_path ?? undefined}
      />
      <ContextItem
        icon={ShieldCheck}
        label="Policy"
        value={policy?.name ?? "Balanced"}
        detail={policy?.profile_type}
      />
      <section className="artifact-strip" aria-label="Linked artifacts">
        <h3>Artifacts</h3>
        {artifactCount === 0 ? (
          <p className="muted-line">No linked artifacts yet.</p>
        ) : (
          <>
            {decisionCount > 0 ? (
              <ArtifactCard icon={GitBranch} label="Decisions" value={decisionCount} />
            ) : null}
            {validationCount > 0 ? (
              <ArtifactCard
                icon={FileCheck2}
                label="Validation"
                tone="success"
                value={validationCount}
              />
            ) : null}
            {codingCount > 0 ? (
              <ArtifactCard icon={Code2} label="Coding" value={codingCount} />
            ) : null}
          </>
        )}
      </section>
    </aside>
  );
}

interface ContextItemProps {
  icon: LucideIcon;
  label: string;
  value: string;
  detail?: string;
}

function ContextItem({ icon: Icon, label, value, detail }: ContextItemProps) {
  return (
    <section className="context-item">
      <Icon aria-hidden="true" size={17} />
      <div>
        <span>{label}</span>
        <strong>{value}</strong>
        {detail ? <small>{detail}</small> : null}
      </div>
    </section>
  );
}

function modeLabel(mode: DeliberationMode) {
  return mode
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}
