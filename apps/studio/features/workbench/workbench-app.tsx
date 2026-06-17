"use client";

import { FileCheck2, GitPullRequest, RotateCcw, Search, Settings2, ShieldCheck } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { CheckpointDetailView, CheckpointList } from "@/features/checkpoints/checkpoint-panels";
import { CodingDetailView, CodingRequestList } from "@/features/coding/coding-panels";
import { OutcomeDetailView, OutcomeList } from "@/features/outcomes/outcome-panels";
import { ReleaseDetailView, ReleaseList } from "@/features/releases/release-panels";
import { ToolActionDetailView, ToolActionList } from "@/features/tools/tool-panels";
import { TrustSettings } from "@/features/trust/trust-settings";
import { ValidationDetailView, ValidationList } from "@/features/validation/validation-panels";
import {
  WorkbenchArtifactCard,
  WorkbenchError,
  WorkbenchLoading,
  WorkbenchSection,
} from "@/features/workbench/workbench-shared";
import { StudioApiClient, StudioApiError } from "@/lib/api/client";
import type {
  CheckpointDetailResponse,
  CheckpointSummary,
  CodingDetailResponse,
  CodingListResponse,
  ConversationSummary,
  OutcomeDetailResponse,
  OutcomeListResponse,
  RecentRepo,
  ReleaseDetailResponse,
  ReleaseListResponse,
  ToolActionDetailResponse,
  ToolActionSummary,
  TrustMode,
  TrustRuleKey,
  TrustSettingsResponse,
  ValidationDetailResponse,
  ValidationListResponse,
  WorkbenchOverview,
} from "@/lib/types";

export type WorkbenchArea =
  | "overview"
  | "coding"
  | "validation"
  | "checkpoints"
  | "tools"
  | "releases"
  | "outcomes"
  | "trust";

export interface WorkbenchRoute {
  section: "workbench";
  area: WorkbenchArea;
  id: string | null;
}

interface WorkbenchAppProps {
  api: StudioApiClient;
  route: WorkbenchRoute;
  repos: RecentRepo[];
  conversations: ConversationSummary[];
  onNavigate: (href: string) => void;
}

export function WorkbenchApp({
  api,
  route,
  repos,
  conversations,
  onNavigate,
}: WorkbenchAppProps) {
  const [overview, setOverview] = useState<WorkbenchOverview | null>(null);
  const [codingList, setCodingList] = useState<CodingListResponse | null>(null);
  const [codingDetail, setCodingDetail] = useState<CodingDetailResponse | null>(null);
  const [validationList, setValidationList] = useState<ValidationListResponse | null>(null);
  const [validationDetail, setValidationDetail] = useState<ValidationDetailResponse | null>(null);
  const [checkpoints, setCheckpoints] = useState<CheckpointSummary[] | null>(null);
  const [checkpointDetail, setCheckpointDetail] = useState<CheckpointDetailResponse | null>(null);
  const [tools, setTools] = useState<ToolActionSummary[] | null>(null);
  const [toolDetail, setToolDetail] = useState<ToolActionDetailResponse | null>(null);
  const [releases, setReleases] = useState<ReleaseListResponse | null>(null);
  const [releaseDetail, setReleaseDetail] = useState<ReleaseDetailResponse | null>(null);
  const [outcomes, setOutcomes] = useState<OutcomeListResponse | null>(null);
  const [outcomeDetail, setOutcomeDetail] = useState<OutcomeDetailResponse | null>(null);
  const [trust, setTrust] = useState<TrustSettingsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [codingQuery, setCodingQuery] = useState("");
  const [codingStatusFilter, setCodingStatusFilter] = useState("");
  const [codingRepoFilter, setCodingRepoFilter] = useState("");
  const [codingConversationFilter, setCodingConversationFilter] = useState("");

  const defaultRepoPath = repos[0]?.path ?? ".";

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        if (route.area === "overview") {
          const next = await api.workbenchOverview();
          if (!cancelled) setOverview(next);
        } else if (route.area === "coding") {
          if (route.id) {
            const next = await api.codingDetail(route.id);
            if (!cancelled) setCodingDetail(next);
          } else {
            const next = await api.coding({
              conversation: codingConversationFilter || undefined,
              limit: 120,
              q: codingQuery,
              repo: codingRepoFilter || undefined,
              status: codingStatusFilter || undefined,
            });
            if (!cancelled) setCodingList(next);
          }
        } else if (route.area === "validation") {
          if (route.id) {
            const next = await api.validationDetail(route.id);
            if (!cancelled) setValidationDetail(next);
          } else {
            const next = await api.validation();
            if (!cancelled) setValidationList(next);
          }
        } else if (route.area === "checkpoints") {
          if (route.id) {
            const next = await api.checkpoint(route.id);
            if (!cancelled) setCheckpointDetail(next);
          } else {
            const next = await api.checkpoints();
            if (!cancelled) setCheckpoints(next);
          }
        } else if (route.area === "tools") {
          if (route.id) {
            const next = await api.toolAction(route.id);
            if (!cancelled) setToolDetail(next);
          } else {
            const next = await api.toolActions();
            if (!cancelled) setTools(next);
          }
        } else if (route.area === "releases") {
          if (route.id) {
            const next = await api.release(route.id);
            if (!cancelled) setReleaseDetail(next);
          } else {
            const next = await api.releases();
            if (!cancelled) setReleases(next);
          }
        } else if (route.area === "outcomes") {
          if (route.id) {
            const next = await api.outcome(route.id);
            if (!cancelled) setOutcomeDetail(next);
          } else {
            const next = await api.outcomes();
            if (!cancelled) setOutcomes(next);
          }
        } else if (route.area === "trust") {
          const next = await api.trust();
          if (!cancelled) setTrust(next);
        }
      } catch (nextError) {
        const message =
          nextError instanceof StudioApiError ? nextError.message : "Workbench could not load.";
        if (!cancelled) setError(message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [
    api,
    codingConversationFilter,
    codingQuery,
    codingRepoFilter,
    codingStatusFilter,
    route.area,
    route.id,
  ]);

  async function createCoding(kind: "plan" | "propose", request: string, repoPath: string) {
    const payload = { user_request: request, repo_path: repoPath };
    const detail = kind === "plan"
      ? await api.createCodingPlan(payload)
      : await api.proposeCodingChange(payload);
    onNavigate(detail.summary.href);
  }

  async function runValidation(repoPath: string, approved: boolean, dryRun: boolean) {
    const detail = await api.runValidation({ repo_path: repoPath, approved, dry_run: dryRun });
    onNavigate(detail.summary.href);
  }

  async function applyPatch(changeId: string, approved: boolean) {
    const detail = await api.applyCodingChange(changeId, { approved });
    setCodingDetail(detail);
  }

  async function restoreCheckpoint(checkpointId: string) {
    const detail = await api.restoreCheckpoint(checkpointId, { approved: true });
    setCheckpointDetail(detail);
  }

  async function updateTrust(payload: {
    mode?: TrustMode;
    rules?: Partial<Record<TrustRuleKey, boolean>>;
  }) {
    const next = await api.updateTrust(payload);
    setTrust(next);
  }

  async function handlePendingDecision(endpoint: string) {
    const codingApply = /^\/api\/coding\/([^/]+)\/apply$/.exec(endpoint);
    if (codingApply?.[1]) {
      const detail = await api.applyCodingChange(codingApply[1], { approved: true });
      onNavigate(detail.summary.href);
      return;
    }
    if (endpoint === "/api/validation/run") {
      await runValidation(defaultRepoPath, true, false);
    }
  }

  const title = useMemo(() => routeTitle(route), [route]);

  return (
    <div className="workbench-scroll">
      <nav className="workbench-tabs" aria-label="Workbench sections">
        {workbenchTabs.map((tab) => (
          <button
            className={route.area === tab.area ? "is-active" : ""}
            key={tab.area}
            onClick={() => onNavigate(tab.href)}
            type="button"
          >
            <tab.icon aria-hidden="true" size={15} />
            {tab.label}
          </button>
        ))}
      </nav>
      <div className="workbench-inner">
        <header className="workbench-page-heading">
          <p>Workbench</p>
          <h1>{title}</h1>
        </header>
        {loading ? <WorkbenchLoading label="Loading Workbench" /> : null}
        {error ? <WorkbenchError label={error} /> : null}
        {!loading && !error ? (
          <>
            {route.area === "overview" && overview ? (
              <OverviewView
                defaultRepoPath={defaultRepoPath}
                onCreateCoding={(kind, request, repoPath) =>
                  void createCoding(kind, request, repoPath)
                }
                onNavigate={onNavigate}
                onPendingDecision={(endpoint) => void handlePendingDecision(endpoint)}
                onRunValidation={(repoPath, approved, dryRun) =>
                  void runValidation(repoPath, approved, dryRun)
                }
                overview={overview}
              />
            ) : null}
            {route.area === "coding" && route.id && codingDetail ? (
              <CodingDetailView
                detail={codingDetail}
                onApply={(changeId, approved) => void applyPatch(changeId, approved)}
                onNavigate={onNavigate}
              />
            ) : null}
            {route.area === "coding" && !route.id && codingList ? (
              <>
                <div className="workbench-filter-row">
                  <label className="workbench-search">
                    <Search aria-hidden="true" size={16} />
                    <input
                      aria-label="Search coding requests"
                      onChange={(event) => setCodingQuery(event.target.value)}
                      placeholder="Search coding work"
                      value={codingQuery}
                    />
                  </label>
                  <label>
                    Status
                    <select
                      onChange={(event) => setCodingStatusFilter(event.target.value)}
                      value={codingStatusFilter}
                    >
                      <option value="">All statuses</option>
                      {codingStatusOptions.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Repo
                    <select
                      onChange={(event) => setCodingRepoFilter(event.target.value)}
                      value={codingRepoFilter}
                    >
                      <option value="">All repos</option>
                      {repos.map((repo) => (
                        <option key={repo.path} value={repo.path}>
                          {repo.name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Conversation
                    <select
                      onChange={(event) => setCodingConversationFilter(event.target.value)}
                      value={codingConversationFilter}
                    >
                      <option value="">All conversations</option>
                      {conversations.map((conversation) => (
                        <option key={conversation.id} value={conversation.id}>
                          {conversation.title}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
                <CodingRequestList items={codingList.items} onOpen={onNavigate} />
              </>
            ) : null}
            {route.area === "validation" && route.id && validationDetail ? (
              <ValidationDetailView detail={validationDetail} onNavigate={onNavigate} />
            ) : null}
            {route.area === "validation" && !route.id && validationList ? (
              <ValidationList items={validationList.items} onOpen={onNavigate} />
            ) : null}
            {route.area === "checkpoints" && route.id && checkpointDetail ? (
              <CheckpointDetailView
                detail={checkpointDetail}
                onRestore={(checkpointId) => void restoreCheckpoint(checkpointId)}
              />
            ) : null}
            {route.area === "checkpoints" && !route.id && checkpoints ? (
              <CheckpointList items={checkpoints} onOpen={onNavigate} />
            ) : null}
            {route.area === "tools" && route.id && toolDetail ? (
              <ToolActionDetailView detail={toolDetail} onNavigate={onNavigate} />
            ) : null}
            {route.area === "tools" && !route.id && tools ? (
              <ToolActionList items={tools} onOpen={onNavigate} />
            ) : null}
            {route.area === "releases" && route.id && releaseDetail ? (
              <ReleaseDetailView detail={releaseDetail} onNavigate={onNavigate} />
            ) : null}
            {route.area === "releases" && !route.id && releases ? (
              <ReleaseList items={releases.items} onOpen={onNavigate} />
            ) : null}
            {route.area === "outcomes" && route.id && outcomeDetail ? (
              <OutcomeDetailView detail={outcomeDetail} />
            ) : null}
            {route.area === "outcomes" && !route.id && outcomes ? (
              <OutcomeList items={outcomes.items} onOpen={onNavigate} />
            ) : null}
            {route.area === "trust" && trust ? (
              <TrustSettings settings={trust} onUpdate={(payload) => void updateTrust(payload)} />
            ) : null}
          </>
        ) : null}
      </div>
    </div>
  );
}

function OverviewView({
  overview,
  defaultRepoPath,
  onNavigate,
  onCreateCoding,
  onRunValidation,
  onPendingDecision,
}: {
  overview: WorkbenchOverview;
  defaultRepoPath: string;
  onNavigate: (href: string) => void;
  onCreateCoding: (kind: "plan" | "propose", request: string, repoPath: string) => void;
  onRunValidation: (repoPath: string, approved: boolean, dryRun: boolean) => void;
  onPendingDecision: (endpoint: string) => void;
}) {
  const [request, setRequest] = useState("");
  const [repoPath, setRepoPath] = useState(defaultRepoPath);

  return (
    <div className="workbench-overview">
      <section className="workbench-launch-panel" aria-label="Launch work">
        <div>
          <h2>Launch work</h2>
          <p>Create a plan, propose a scoped patch, or run validation from the existing runtime.</p>
        </div>
        <label>
          Request
          <input
            onChange={(event) => setRequest(event.target.value)}
            placeholder="Describe the scoped change"
            value={request}
          />
        </label>
        <label>
          Repo path
          <input onChange={(event) => setRepoPath(event.target.value)} value={repoPath} />
        </label>
        <div className="workbench-action-row">
          <button
            className="workbench-secondary-button"
            disabled={!request.trim()}
            onClick={() => onCreateCoding("plan", request, repoPath)}
            type="button"
          >
            Create plan
          </button>
          <button
            className="workbench-primary-button"
            disabled={!request.trim()}
            onClick={() => onCreateCoding("propose", request, repoPath)}
            type="button"
          >
            Propose change
          </button>
          <button
            className="workbench-secondary-button"
            onClick={() => onRunValidation(repoPath, false, true)}
            type="button"
          >
            Validation dry-run
          </button>
          <button
            className="workbench-secondary-button"
            onClick={() => onRunValidation(repoPath, true, false)}
            type="button"
          >
            Run validation
          </button>
        </div>
      </section>

      <div className="workbench-grid">
        <WorkbenchSection
          count={overview.active_coding_work.length}
          empty="No active coding work."
          title="Active Coding Work"
        >
          {overview.active_coding_work.map((item) => (
            <WorkbenchArtifactCard artifact={item} key={item.id} onOpen={onNavigate} />
          ))}
        </WorkbenchSection>
        <WorkbenchSection
          count={overview.pending_decisions.length}
          empty="No meaningful decisions are pending."
          title="Pending Decisions"
        >
          {overview.pending_decisions.map((decision) => (
            <article className="pending-decision" key={decision.id}>
              <strong>{decision.title}</strong>
              <p>{decision.description}</p>
              <small>{decision.repo} / {decision.risk} / rollback {decision.rollback_available ? "available" : "not available"}</small>
              <div className="workbench-action-row">
                <button
                  className="workbench-primary-button"
                  onClick={() => onPendingDecision(decision.primary_endpoint)}
                  type="button"
                >
                  {decision.primary_label}
                </button>
                <button className="workbench-secondary-button" type="button">
                  {decision.reject_label}
                </button>
              </div>
            </article>
          ))}
        </WorkbenchSection>
        <WorkbenchSection
          count={overview.recent_completed_coding_work.length}
          empty="No completed coding work yet."
          title="Completed Coding Work"
        >
          {overview.recent_completed_coding_work.map((item) => (
            <WorkbenchArtifactCard artifact={item} key={item.id} onOpen={onNavigate} />
          ))}
        </WorkbenchSection>
        <WorkbenchSection
          count={overview.recent_validation_runs.length}
          empty="No validation has run yet."
          title="Recent Validation"
        >
          {overview.recent_validation_runs.map((item) => (
            <WorkbenchArtifactCard artifact={item} key={item.id} onOpen={onNavigate} />
          ))}
        </WorkbenchSection>
        <WorkbenchSection
          count={overview.failed_validation_requiring_attention.length}
          empty="No failed validation needs attention."
          title="Validation Requiring Attention"
        >
          {overview.failed_validation_requiring_attention.map((item) => (
            <WorkbenchArtifactCard artifact={item} key={item.id} onOpen={onNavigate} />
          ))}
        </WorkbenchSection>
        <WorkbenchSection
          count={overview.recent_checkpoints.length}
          empty="No checkpoints yet."
          title="Recent Checkpoints"
        >
          {overview.recent_checkpoints.map((item) => (
            <WorkbenchArtifactCard artifact={item} key={item.id} onOpen={onNavigate} />
          ))}
        </WorkbenchSection>
        <WorkbenchSection
          count={overview.latest_release_evidence.length}
          empty="No release evidence yet."
          title="Latest Release Evidence"
        >
          {overview.latest_release_evidence.map((item) => (
            <WorkbenchArtifactCard artifact={item} key={item.id} onOpen={onNavigate} />
          ))}
        </WorkbenchSection>
      </div>
    </div>
  );
}

const workbenchTabs = [
  { area: "overview" as const, href: "/workbench", label: "Overview", icon: GitPullRequest },
  { area: "coding" as const, href: "/workbench/coding", label: "Coding", icon: GitPullRequest },
  { area: "validation" as const, href: "/workbench/validation", label: "Validation", icon: FileCheck2 },
  { area: "checkpoints" as const, href: "/workbench/checkpoints", label: "Checkpoints", icon: RotateCcw },
  { area: "tools" as const, href: "/workbench/tools", label: "Tools", icon: Settings2 },
  { area: "releases" as const, href: "/workbench/releases", label: "Releases", icon: ShieldCheck },
  { area: "outcomes" as const, href: "/workbench/outcomes", label: "Outcomes", icon: ShieldCheck },
  { area: "trust" as const, href: "/workbench/trust", label: "Trust", icon: ShieldCheck },
];

const codingStatusOptions = [
  { value: "active", label: "Active" },
  { value: "completed", label: "Completed" },
  { value: "failed", label: "Failed" },
  { value: "rolled_back", label: "Rolled back" },
  { value: "needs_input", label: "Needs input" },
];

function routeTitle(route: WorkbenchRoute) {
  if (route.id) {
    return `${route.area.charAt(0).toUpperCase()}${route.area.slice(1)} detail`;
  }
  if (route.area === "overview") {
    return "Agent Workbench";
  }
  return route.area.charAt(0).toUpperCase() + route.area.slice(1);
}
