"use client";

import { Archive, CheckCircle2, RotateCcw, Save, Search, Trash2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { StatusBadge } from "@/components/status-badge";
import {
  WorkbenchError,
  WorkbenchLoading,
  formatDate,
} from "@/features/workbench/workbench-shared";
import { StudioApiClient, StudioApiError } from "@/lib/api/client";
import type {
  RecentRepo,
  StudioMemoryCreateRequest,
  StudioMemoryDetail,
  StudioMemoryKind,
  StudioMemoryListResponse,
  StudioMemoryPatchRequest,
  StudioMemoryScope,
  StudioMemoryState,
  StudioMemorySuggestion,
  StudioMemorySuggestionListResponse,
  StudioMemorySummary,
} from "@/lib/types";

export interface MemoryRoute {
  section: "memory";
  id: string | null;
}

interface MemoryAppProps {
  api: StudioApiClient;
  route: MemoryRoute;
  repos: RecentRepo[];
  onNavigate: (href: string) => void;
}

const memoryTypes = [
  ["goal", "Goal"],
  ["constraint", "Constraint"],
  ["preference", "Preference"],
  ["principle", "Principle"],
  ["strategic_decision", "Strategic decision"],
  ["rejected_path", "Rejected path"],
  ["lesson_learned", "Lesson learned"],
  ["open_question", "Open question"],
  ["project_fact", "Project fact"],
  ["working_style", "Working style"],
] as const;

const scopes: StudioMemoryScope[] = ["global", "project", "repo", "conversation"];

export function MemoryApp({ api, route, repos, onNavigate }: MemoryAppProps) {
  const [list, setList] = useState<StudioMemoryListResponse | null>(null);
  const [detail, setDetail] = useState<StudioMemoryDetail | null>(null);
  const [suggestions, setSuggestions] = useState<StudioMemorySuggestionListResponse | null>(null);
  const [query, setQuery] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [scopeFilter, setScopeFilter] = useState("");
  const [repoFilter, setRepoFilter] = useState("");
  const [stateFilter, setStateFilter] = useState<StudioMemoryState>("active");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [draft, setDraft] = useState<MemoryDraft>(() => emptyDraft());

  const selectedMemory = useMemo(() => {
    if (!route.id || !list) return null;
    return list.memories.find((memory) => memory.id === route.id) ?? null;
  }, [list, route.id]);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const [nextList, nextSuggestions] = await Promise.all([
          api.memories({
            limit: 200,
            q: query,
            repoProfileId: repoFilter || undefined,
            scope: (scopeFilter || undefined) as StudioMemoryScope | undefined,
            state: stateFilter,
            type: typeFilter || undefined,
          }),
          api.memorySuggestions(),
        ]);
        if (cancelled) return;
        setList(nextList);
        setSuggestions(nextSuggestions);
      } catch (nextError) {
        if (!cancelled) setError(errorMessage(nextError, "Memory could not load."));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    const timer = window.setTimeout(() => void load(), 140);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [api, query, repoFilter, scopeFilter, stateFilter, typeFilter]);

  useEffect(() => {
    let cancelled = false;
    async function loadDetail() {
      if (!route.id) {
        setDetail(null);
        setDraft(emptyDraft());
        return;
      }
      setLoading(true);
      setError(null);
      try {
        const nextDetail = await api.memory(route.id);
        if (cancelled) return;
        setDetail(nextDetail);
        setDraft(draftFromMemory(nextDetail));
      } catch (nextError) {
        if (!cancelled) setError(errorMessage(nextError, "Memory detail could not load."));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void loadDetail();
    return () => {
      cancelled = true;
    };
  }, [api, route.id]);

  async function refresh() {
    const [nextList, nextSuggestions] = await Promise.all([
      api.memories({
        limit: 200,
        q: query,
        repoProfileId: repoFilter || undefined,
        scope: (scopeFilter || undefined) as StudioMemoryScope | undefined,
        state: stateFilter,
        type: typeFilter || undefined,
      }),
      api.memorySuggestions(),
    ]);
    setList(nextList);
    setSuggestions(nextSuggestions);
    if (route.id) {
      setDetail(await api.memory(route.id));
    }
  }

  async function createMemory() {
    if (!draft.content.trim()) return;
    const created = await api.createMemory(payloadFromDraft(draft));
    setDraft(emptyDraft());
    await refresh();
    onNavigate(`/memory/${created.id}`);
  }

  async function saveDetail() {
    if (!detail) return;
    const updated = await api.updateMemory(detail.id, patchFromDraft(draft));
    setDetail(updated);
    await refresh();
  }

  async function archiveOrRestore(memory: StudioMemoryDetail) {
    const updated = memory.archived
      ? await api.restoreMemory(memory.id)
      : await api.archiveMemory(memory.id);
    setDetail(updated);
    await refresh();
  }

  async function deleteDetail() {
    if (!detail) return;
    if (!window.confirm(`Delete memory "${detail.summary}" permanently?`)) return;
    await api.deleteMemory(detail.id, true);
    setDetail(null);
    await refresh();
    onNavigate("/memory");
  }

  async function saveSuggestion(suggestion: StudioMemorySuggestion) {
    const memory = await api.saveMemorySuggestion(suggestion.id);
    await refresh();
    onNavigate(`/memory/${memory.id}`);
  }

  async function ignoreSuggestion(suggestion: StudioMemorySuggestion) {
    await api.ignoreMemorySuggestion(suggestion.id);
    await refresh();
  }

  return (
    <div className="workbench-scroll">
      <div className="workbench-inner">
        <header className="workbench-page-heading">
          <p>Memory</p>
          <h1>{route.id ? "Memory detail" : "Memory"}</h1>
        </header>

        {loading ? <WorkbenchLoading label="Loading memory" /> : null}
        {error ? <WorkbenchError label={error} /> : null}

        {!loading && !error ? (
          <div className="studio-two-column">
            <section className="workbench-launch-panel" aria-label="Memory controls">
              <div>
                <h2>Create memory</h2>
                <p>
                  Save durable context only when it matters. Sensitive personal details stay out
                  unless you explicitly choose to add them.
                </p>
              </div>
              <MemoryDraftForm draft={draft} onChange={setDraft} repos={repos} />
              <div className="workbench-action-row">
                <button
                  className="workbench-primary-button"
                  disabled={!draft.content.trim()}
                  onClick={() => void createMemory()}
                  type="button"
                >
                  <Save aria-hidden="true" size={15} />
                  Save memory
                </button>
              </div>
              <SuggestionPanel
                onIgnore={(suggestion) => void ignoreSuggestion(suggestion)}
                onSave={(suggestion) => void saveSuggestion(suggestion)}
                suggestions={suggestions?.suggestions ?? []}
              />
            </section>

            <section className="workbench-detail" aria-label="Memory list and detail">
              <MemoryFilters
                query={query}
                repoFilter={repoFilter}
                repos={repos}
                scopeFilter={scopeFilter}
                stateFilter={stateFilter}
                typeFilter={typeFilter}
                onQuery={setQuery}
                onRepo={setRepoFilter}
                onScope={setScopeFilter}
                onState={setStateFilter}
                onType={setTypeFilter}
              />

              {route.id && detail ? (
                <MemoryDetailView
                  detail={detail}
                  draft={draft}
                  onArchiveRestore={() => void archiveOrRestore(detail)}
                  onDelete={() => void deleteDetail()}
                  onDraft={setDraft}
                  onNavigate={onNavigate}
                  onSave={() => void saveDetail()}
                  repos={repos}
                />
              ) : (
                <MemoryList
                  activeId={selectedMemory?.id ?? null}
                  memories={list?.memories ?? []}
                  onOpen={(memoryId) => onNavigate(`/memory/${memoryId}`)}
                />
              )}
            </section>
          </div>
        ) : null}
      </div>
    </div>
  );
}

interface MemoryDraft {
  kind: StudioMemoryKind;
  type: string;
  scope: StudioMemoryScope;
  repo_profile_id: string;
  summary: string;
  content: string;
  source: string;
  stability: string;
  confidence: number;
  importance: number;
}

function emptyDraft(): MemoryDraft {
  return {
    kind: "strategic",
    type: "project_fact",
    scope: "project",
    repo_profile_id: "",
    summary: "",
    content: "",
    source: "manual",
    stability: "medium_term",
    confidence: 0.75,
    importance: 0.6,
  };
}

function draftFromMemory(memory: StudioMemoryDetail): MemoryDraft {
  return {
    kind: memory.kind,
    type: memory.type,
    scope: memory.scope,
    repo_profile_id: memory.repo_profile_id ?? "",
    summary: memory.summary,
    content: memory.content,
    source: memory.source,
    stability: memory.stability,
    confidence: memory.confidence,
    importance: memory.importance,
  };
}

function payloadFromDraft(draft: MemoryDraft): StudioMemoryCreateRequest {
  return {
    confidence: draft.confidence,
    content: draft.content,
    importance: draft.importance,
    kind: draft.kind,
    repo_profile_id: draft.repo_profile_id || null,
    scope: draft.scope,
    source: draft.source,
    stability: draft.stability,
    summary: draft.summary,
    type: draft.type,
  };
}

function patchFromDraft(draft: MemoryDraft): StudioMemoryPatchRequest {
  return payloadFromDraft(draft);
}

function MemoryDraftForm({
  draft,
  repos,
  onChange,
}: {
  draft: MemoryDraft;
  repos: RecentRepo[];
  onChange: (draft: MemoryDraft) => void;
}) {
  return (
    <div className="studio-form-grid">
      <label>
        Kind
        <select
          onChange={(event) =>
            onChange({ ...draft, kind: event.target.value as StudioMemoryKind })
          }
          value={draft.kind}
        >
          <option value="strategic">Strategic</option>
          <option value="regular">Regular</option>
        </select>
      </label>
      <label>
        Type
        <select
          onChange={(event) => onChange({ ...draft, type: event.target.value })}
          value={draft.type}
        >
          {memoryTypes.map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
      </label>
      <label>
        Scope
        <select
          onChange={(event) =>
            onChange({ ...draft, scope: event.target.value as StudioMemoryScope })
          }
          value={draft.scope}
        >
          {scopes.map((scope) => (
            <option key={scope} value={scope}>
              {labelize(scope)}
            </option>
          ))}
        </select>
      </label>
      <label>
        Repo
        <select
          onChange={(event) => onChange({ ...draft, repo_profile_id: event.target.value })}
          value={draft.repo_profile_id}
        >
          <option value="">No repo scope</option>
          {repos.map((repo) => (
            <option key={repo.id} value={repo.id}>
              {repo.name}
            </option>
          ))}
        </select>
      </label>
      <label className="studio-form-wide">
        Summary
        <input
          onChange={(event) => onChange({ ...draft, summary: event.target.value })}
          placeholder="Short human-readable belief"
          value={draft.summary}
        />
      </label>
      <label className="studio-form-wide">
        Original content
        <textarea
          onChange={(event) => onChange({ ...draft, content: event.target.value })}
          placeholder="What should Hephaestus remember?"
          rows={4}
          value={draft.content}
        />
      </label>
    </div>
  );
}

function MemoryFilters({
  query,
  typeFilter,
  scopeFilter,
  repoFilter,
  stateFilter,
  repos,
  onQuery,
  onType,
  onScope,
  onRepo,
  onState,
}: {
  query: string;
  typeFilter: string;
  scopeFilter: string;
  repoFilter: string;
  stateFilter: StudioMemoryState;
  repos: RecentRepo[];
  onQuery: (value: string) => void;
  onType: (value: string) => void;
  onScope: (value: string) => void;
  onRepo: (value: string) => void;
  onState: (value: StudioMemoryState) => void;
}) {
  return (
    <div className="workbench-filter-row">
      <label className="workbench-search">
        <Search aria-hidden="true" size={16} />
        <input
          aria-label="Search memories"
          onChange={(event) => onQuery(event.target.value)}
          placeholder="Search memory"
          value={query}
        />
      </label>
      <label>
        Type
        <select onChange={(event) => onType(event.target.value)} value={typeFilter}>
          <option value="">All types</option>
          {memoryTypes.map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
      </label>
      <label>
        Scope
        <select onChange={(event) => onScope(event.target.value)} value={scopeFilter}>
          <option value="">All scopes</option>
          {scopes.map((scope) => (
            <option key={scope} value={scope}>
              {labelize(scope)}
            </option>
          ))}
        </select>
      </label>
      <label>
        Repo
        <select onChange={(event) => onRepo(event.target.value)} value={repoFilter}>
          <option value="">All repos</option>
          {repos.map((repo) => (
            <option key={repo.id} value={repo.id}>
              {repo.name}
            </option>
          ))}
        </select>
      </label>
      <label>
        State
        <select
          onChange={(event) => onState(event.target.value as StudioMemoryState)}
          value={stateFilter}
        >
          <option value="active">Active</option>
          <option value="archived">Archived</option>
          <option value="all">All</option>
        </select>
      </label>
    </div>
  );
}

function MemoryList({
  activeId,
  memories,
  onOpen,
}: {
  activeId: string | null;
  memories: StudioMemorySummary[];
  onOpen: (memoryId: string) => void;
}) {
  if (memories.length === 0) {
    return (
      <div className="workbench-state">
        <CheckCircle2 aria-hidden="true" size={18} />
        <span>No memories match this view. Data is safe; create or save a suggestion when it matters.</span>
      </div>
    );
  }
  return (
    <div className="workbench-table" role="list" aria-label="Memories">
      <div className="workbench-table-row is-heading">
        <span>Memory</span>
        <span>Type</span>
        <span>Scope</span>
        <span>Confidence</span>
      </div>
      {memories.map((memory) => (
        <button
          className={`workbench-table-row ${activeId === memory.id ? "is-active" : ""}`}
          key={memory.id}
          onClick={() => onOpen(memory.id)}
          role="listitem"
          type="button"
        >
          <span>
            <strong>{memory.summary || memory.id}</strong>
            <small>{memory.repo_name ?? memory.project ?? "Global"}</small>
          </span>
          <span>{memory.type_label}</span>
          <span>{labelize(memory.scope)}</span>
          <span>{Math.round(memory.confidence * 100)}%</span>
        </button>
      ))}
    </div>
  );
}

function MemoryDetailView({
  detail,
  draft,
  repos,
  onDraft,
  onSave,
  onArchiveRestore,
  onDelete,
  onNavigate,
}: {
  detail: StudioMemoryDetail;
  draft: MemoryDraft;
  repos: RecentRepo[];
  onDraft: (draft: MemoryDraft) => void;
  onSave: () => void;
  onArchiveRestore: () => void;
  onDelete: () => void;
  onNavigate: (href: string) => void;
}) {
  return (
    <div className="memory-detail">
      <div className="workbench-detail-hero">
        <div>
          <StatusBadge tone={detail.archived ? "warning" : "success"}>
            {detail.archived ? "Archived" : "Active"}
          </StatusBadge>
          <h2>{detail.summary}</h2>
          <p className="workbench-muted">
            {detail.type_label} / {labelize(detail.scope)} / updated {formatDate(detail.updated_at)}
          </p>
        </div>
        <div className="workbench-action-row">
          <button className="workbench-primary-button" onClick={onSave} type="button">
            <Save aria-hidden="true" size={15} />
            Save changes
          </button>
          <button className="workbench-secondary-button" onClick={onArchiveRestore} type="button">
            {detail.archived ? <RotateCcw aria-hidden="true" size={15} /> : <Archive aria-hidden="true" size={15} />}
            {detail.archived ? "Restore" : "Archive"}
          </button>
          <button className="workbench-secondary-button" onClick={onDelete} type="button">
            <Trash2 aria-hidden="true" size={15} />
            Delete
          </button>
        </div>
      </div>
      {detail.conflict_warnings.length > 0 ? (
        <div className="workbench-warning" role="status">
          <span>{detail.conflict_warnings[0]}</span>
        </div>
      ) : null}
      <MemoryDraftForm draft={draft} onChange={onDraft} repos={repos} />
      <section className="workbench-detail-section">
        <h2>Evidence</h2>
        {detail.evidence.length === 0 ? (
          <p className="workbench-muted">No explicit evidence has been attached yet.</p>
        ) : (
          <ul className="workbench-list">
            {detail.evidence.map((evidence) => (
              <li key={`${evidence.kind}-${evidence.source_id ?? evidence.content}`}>
                {evidence.content}
              </li>
            ))}
          </ul>
        )}
      </section>
      <section className="workbench-detail-section">
        <h2>Links</h2>
        {detail.linked_conversation ? (
          <button
            className="workbench-linked-row"
            onClick={() => onNavigate(detail.linked_conversation?.href ?? "/memory")}
            type="button"
          >
            <span>{detail.linked_conversation.label}</span>
            <small>Conversation</small>
          </button>
        ) : (
          <p className="workbench-muted">No conversation link is attached.</p>
        )}
      </section>
    </div>
  );
}

function SuggestionPanel({
  suggestions,
  onSave,
  onIgnore,
}: {
  suggestions: StudioMemorySuggestion[];
  onSave: (suggestion: StudioMemorySuggestion) => void;
  onIgnore: (suggestion: StudioMemorySuggestion) => void;
}) {
  return (
    <section className="memory-suggestions" aria-label="Memory suggestions">
      <h2>Suggestions</h2>
      {suggestions.length === 0 ? (
        <p className="workbench-muted">
          No memory suggestions are waiting. Conversation stays uninterrupted.
        </p>
      ) : null}
      {suggestions.map((suggestion) => (
        <article className="pending-decision" key={suggestion.id}>
          <strong>{suggestion.proposed_memory}</strong>
          <p>{suggestion.why_it_may_matter}</p>
          <small>
            {suggestion.proposed_type_label} / {labelize(suggestion.proposed_scope)} /{" "}
            {suggestion.proposed_stability}
          </small>
          <div className="workbench-action-row">
            <button className="workbench-primary-button" onClick={() => onSave(suggestion)} type="button">
              Save
            </button>
            <button className="workbench-secondary-button" onClick={() => onIgnore(suggestion)} type="button">
              Ignore
            </button>
          </div>
        </article>
      ))}
    </section>
  );
}

function labelize(value: string) {
  return value.replaceAll("_", " ").replace(/^\w/, (letter) => letter.toUpperCase());
}

function errorMessage(error: unknown, fallback: string) {
  return error instanceof StudioApiError ? error.message : fallback;
}
