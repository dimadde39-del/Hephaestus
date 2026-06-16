"use client";

import { Brain, Boxes, Database, PanelRightClose, ShieldCheck, Waypoints } from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { IconButton } from "@/components/icon-button";
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
  onCloseMobile: () => void;
}

export function ContextDrawer({
  detail,
  mode,
  provider,
  policy,
  repos,
  mobileOpen,
  onCloseMobile,
}: ContextDrawerProps) {
  const conversation = detail?.conversation ?? null;
  const attachedRepo = repos.find((repo) => repo.id === conversation?.repo_profile_id) ?? null;

  return (
    <aside className={`context-drawer ${mobileOpen ? "is-open" : ""}`} aria-label="Context">
      <div className="drawer-heading">
        <div>
          <p className="eyebrow">Context</p>
          <h2>Active thread</h2>
        </div>
        <IconButton
          className="mobile-only"
          icon={PanelRightClose}
          label="Close context"
          onClick={onCloseMobile}
        />
      </div>

      <ContextItem icon={Waypoints} label="Mode" value={modeLabel(mode)} />
      <ContextItem
        icon={Boxes}
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
      <ContextItem
        icon={Database}
        label="Provider"
        value={provider?.active_label ?? "Local deterministic mode"}
        detail={provider?.statuses.find((status) => status.provider === provider.active_provider)?.detail}
      />
      <ContextItem
        icon={Brain}
        label="Memory"
        value={`${detail?.regular_memory_count ?? 0} regular / ${detail?.strategic_memory_count ?? 0} strategic`}
      />

      <section className="artifact-strip" aria-label="Linked artifacts">
        <span>{conversation?.linked_decision_count ?? 0} linked decisions</span>
        <span>{conversation?.validation_run_count ?? 0} validation runs</span>
        <span>{conversation?.coding_request_count ?? 0} coding requests</span>
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
