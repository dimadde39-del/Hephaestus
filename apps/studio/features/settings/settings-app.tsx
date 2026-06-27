"use client";

import { DatabaseBackup, Download, PlugZap, RotateCcw, ShieldCheck } from "lucide-react";
import { useEffect, useState } from "react";

import { StatusBadge } from "@/components/status-badge";
import {
  WorkbenchError,
  WorkbenchLoading,
  formatDate,
} from "@/features/workbench/workbench-shared";
import { StudioApiClient, StudioApiError } from "@/lib/api/client";
import type {
  BackupResponse,
  ConversationSummary,
  ExportResponse,
  PolicyProfile,
  ProviderStatusResponse,
  StudioProviderConfig,
  StudioProviderListResponse,
  StudioProviderTestResponse,
  StudioProviderUpsertRequest,
  StudioSettings,
  StudioSettingsPatchRequest,
  StudioSettingsResponse,
  StudioUsageResponse,
} from "@/lib/types";

export type SettingsArea = "general" | "models" | "policy" | "data" | "appearance" | "advanced";

export interface SettingsRoute {
  section: "settings";
  area: SettingsArea;
}

interface SettingsAppProps {
  api: StudioApiClient;
  route: SettingsRoute;
  conversations: ConversationSummary[];
  policy: PolicyProfile | null;
  providerStatus: ProviderStatusResponse | null;
  onNavigate: (href: string) => void;
  onAppearanceChange: (appearance: "system" | "light" | "dark") => void;
}

const settingsTabs: Array<{ area: SettingsArea; label: string; href: string }> = [
  { area: "general", label: "General", href: "/settings" },
  { area: "appearance", label: "Appearance", href: "/settings/appearance" },
  { area: "models", label: "Models", href: "/settings/models" },
  { area: "policy", label: "Policy and Trust", href: "/settings/policy" },
  { area: "data", label: "Data", href: "/settings/data" },
  { area: "advanced", label: "Advanced", href: "/settings/advanced" },
];

export function SettingsApp({
  api,
  route,
  conversations,
  policy,
  providerStatus,
  onNavigate,
  onAppearanceChange,
}: SettingsAppProps) {
  const [settings, setSettings] = useState<StudioSettingsResponse | null>(null);
  const [providers, setProviders] = useState<StudioProviderListResponse | null>(null);
  const [usage, setUsage] = useState<StudioUsageResponse | null>(null);
  const [backup, setBackup] = useState<BackupResponse | null>(null);
  const [restorePath, setRestorePath] = useState("");
  const [restoreMessage, setRestoreMessage] = useState("");
  const [exportResult, setExportResult] = useState<ExportResponse | null>(null);
  const [selectedConversationId, setSelectedConversationId] = useState(conversations[0]?.id ?? "");
  const [providerDraft, setProviderDraft] = useState<ProviderDraft>(() => emptyProviderDraft());
  const [testResult, setTestResult] = useState<StudioProviderTestResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const [nextSettings, nextProviders, nextUsage] = await Promise.all([
          api.settings(),
          api.providers(),
          api.usage(100),
        ]);
        if (cancelled) return;
        setSettings(nextSettings);
        setProviders(nextProviders);
        setUsage(nextUsage);
      } catch (nextError) {
        if (!cancelled) setError(errorMessage(nextError, "Settings could not load."));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [api]);

  async function patchSettings(payload: StudioSettingsPatchRequest) {
    const next = await api.updateSettings(payload);
    setSettings(next);
  }

  async function createProvider() {
    if (!providerDraft.name.trim()) return;
    await api.createProvider(providerPayload(providerDraft));
    setProviderDraft(emptyProviderDraft());
    setProviders(await api.providers());
  }

  async function setProviderDefault(provider: StudioProviderConfig) {
    if (provider.id === "local") {
      await patchSettings({ deterministic_mode: true });
    } else {
      await api.updateProvider(provider.id, {
        base_url: provider.base_url,
        context_window: provider.context_window,
        default_for_conversation: true,
        input_cost_per_million: provider.input_cost_per_million,
        intended_roles: provider.intended_roles,
        model: provider.model,
        name: provider.name,
        output_cost_per_million: provider.output_cost_per_million,
        provider_type: provider.provider_type,
        thinking_enabled: provider.thinking_enabled,
        reasoning_effort: provider.reasoning_effort,
        max_output_tokens: provider.max_output_tokens,
      });
      await patchSettings({ deterministic_mode: false });
    }
    setProviders(await api.providers());
  }

  async function testProvider(providerId: string) {
    setTestResult({
      id: providerId,
      status: "testing",
      message: "Testing one minimal request…",
      provider: "",
      model: "",
      latency_ms: 0,
    });
    try {
      setTestResult(await api.testProvider(providerId));
      setProviders(await api.providers());
    } catch (nextError) {
      setError(errorMessage(nextError, "Connection test failed."));
    }
  }

  async function removeProvider(providerId: string) {
    await api.deleteProvider(providerId);
    setProviders(await api.providers());
  }

  async function createBackup() {
    setBackup(await api.backup());
  }

  async function restoreBackup() {
    const restored = await api.restoreBackup(restorePath, true);
    setRestoreMessage(restored.message);
  }

  async function exportConversation(format: "markdown" | "json") {
    if (!selectedConversationId) return;
    setExportResult(await api.exportConversation(selectedConversationId, format));
  }

  async function exportMemories() {
    setExportResult(await api.exportMemories());
  }

  return (
    <div className="workbench-scroll">
      <nav className="workbench-tabs" aria-label="Settings sections">
        {settingsTabs.map((tab) => (
          <button
            className={route.area === tab.area ? "is-active" : ""}
            key={tab.area}
            onClick={() => onNavigate(tab.href)}
            type="button"
          >
            {tab.label}
          </button>
        ))}
      </nav>
      <div className="workbench-inner">
        <header className="workbench-page-heading">
          <p>Settings</p>
          <h1>{settingsTabs.find((tab) => tab.area === route.area)?.label ?? "Settings"}</h1>
        </header>

        {loading ? <WorkbenchLoading label="Loading settings" /> : null}
        {error ? <WorkbenchError label={error} /> : null}

        {!loading && !error && settings ? (
          <>
            {route.area === "general" ? (
              <GeneralSettings settings={settings.settings} onPatch={(payload) => void patchSettings(payload)} />
            ) : null}
            {route.area === "appearance" ? (
              <AppearanceSettings
                settings={settings.settings}
                onAppearanceChange={onAppearanceChange}
                onPatch={(payload) => void patchSettings(payload)}
              />
            ) : null}
            {route.area === "models" && providers && usage ? (
              <ModelSettings
                draft={providerDraft}
                providers={providers}
                status={providerStatus}
                testResult={testResult}
                usage={usage}
                onCreate={() => void createProvider()}
                onDraft={setProviderDraft}
                onRemove={(providerId) => void removeProvider(providerId)}
                onSetDefault={(provider) => void setProviderDefault(provider)}
                onTest={(providerId) => void testProvider(providerId)}
              />
            ) : null}
            {route.area === "policy" ? (
              <PolicySettings policy={policy} />
            ) : null}
            {route.area === "data" ? (
              <DataSettings
                backup={backup}
                conversations={conversations}
                databasePath={settings.database_path}
                exportResult={exportResult}
                restoreMessage={restoreMessage}
                restorePath={restorePath}
                schemaVersion={settings.schema_version}
                selectedConversationId={selectedConversationId}
                onBackup={() => void createBackup()}
                onExportConversation={(format) => void exportConversation(format)}
                onExportMemories={() => void exportMemories()}
                onRestore={() => void restoreBackup()}
                onRestorePath={setRestorePath}
                onSelectedConversation={setSelectedConversationId}
              />
            ) : null}
            {route.area === "advanced" ? (
              <AdvancedSettings settings={settings} />
            ) : null}
          </>
        ) : null}
      </div>
    </div>
  );
}

function GeneralSettings({
  settings,
  onPatch,
}: {
  settings: StudioSettings;
  onPatch: (payload: StudioSettingsPatchRequest) => void;
}) {
  return (
    <section className="workbench-detail">
      <div className="studio-form-grid">
        <label>
          Startup route
          <select
            onChange={(event) => onPatch({ startup_route: event.target.value })}
            value={settings.startup_route}
          >
            <option value="/">Chat</option>
            <option value="/workbench">Workbench</option>
            <option value="/memory">Memory</option>
            <option value="/settings">Settings</option>
          </select>
        </label>
        <label>
          Recent repo behavior
          <select
            onChange={(event) => onPatch({ recent_repo_behavior: event.target.value })}
            value={settings.recent_repo_behavior}
          >
            <option value="remember">Remember recent repos</option>
            <option value="ask">Ask before attaching</option>
            <option value="ignore">Do not auto-suggest</option>
          </select>
        </label>
        <label className="studio-check-row">
          <input
            checked={settings.browser_auto_open}
            onChange={(event) => onPatch({ browser_auto_open: event.target.checked })}
            type="checkbox"
          />
          Open browser on `heph studio`
        </label>
      </div>
    </section>
  );
}

function AppearanceSettings({
  settings,
  onPatch,
  onAppearanceChange,
}: {
  settings: StudioSettings;
  onPatch: (payload: StudioSettingsPatchRequest) => void;
  onAppearanceChange: (appearance: "system" | "light" | "dark") => void;
}) {
  function setAppearance(appearance: "system" | "light" | "dark") {
    onAppearanceChange(appearance);
    onPatch({ appearance });
  }
  return (
    <section className="workbench-detail">
      <div className="trust-mode-control" role="group" aria-label="Theme">
        {(["system", "light", "dark"] as const).map((appearance) => (
          <button
            className={settings.appearance === appearance ? "is-active" : ""}
            key={appearance}
            onClick={() => setAppearance(appearance)}
            type="button"
          >
            {labelize(appearance)}
          </button>
        ))}
      </div>
      <label className="studio-check-row">
        <input
          checked={settings.reduced_motion}
          onChange={(event) => onPatch({ reduced_motion: event.target.checked })}
          type="checkbox"
        />
        Reduce motion
      </label>
      <label>
        Density
        <select
          onChange={(event) => onPatch({ density: event.target.value })}
          value={settings.density}
        >
          <option value="comfortable">Comfortable</option>
          <option value="compact">Compact</option>
        </select>
      </label>
    </section>
  );
}

function ModelSettings({
  providers,
  status,
  usage,
  draft,
  testResult,
  onDraft,
  onCreate,
  onSetDefault,
  onTest,
  onRemove,
}: {
  providers: StudioProviderListResponse;
  status: ProviderStatusResponse | null;
  usage: StudioUsageResponse;
  draft: ProviderDraft;
  testResult: StudioProviderTestResponse | null;
  onDraft: (draft: ProviderDraft) => void;
  onCreate: () => void;
  onSetDefault: (provider: StudioProviderConfig) => void;
  onTest: (providerId: string) => void;
  onRemove: (providerId: string) => void;
}) {
  return (
    <div className="studio-two-column">
      <section className="workbench-launch-panel">
        <div>
          <h2>Add provider</h2>
          <p>{providers.storage_note}</p>
        </div>
        <div className="studio-form-grid">
          <label>
            Provider
            <select
              onChange={(event) =>
                onDraft(
                  event.target.value === "deepseek"
                    ? {
                        ...draft,
                        provider_type: "deepseek",
                        name: "DeepSeek",
                        model: "deepseek-v4-flash",
                        base_url: "https://api.deepseek.com",
                        thinking_enabled: true,
                        reasoning_effort: "high",
                      }
                    : { ...draft, provider_type: event.target.value },
                )
              }
              value={draft.provider_type}
            >
              <option value="openai-compatible">OpenAI-compatible / OpenRouter</option>
              <option value="deepseek">DeepSeek</option>
            </select>
          </label>
          <label>
            Name
            <input onChange={(event) => onDraft({ ...draft, name: event.target.value })} value={draft.name} />
          </label>
          <label>
            Model
            <input onChange={(event) => onDraft({ ...draft, model: event.target.value })} value={draft.model} />
          </label>
          <label>
            Base URL
            <input onChange={(event) => onDraft({ ...draft, base_url: event.target.value })} value={draft.base_url} />
          </label>
          <label className="studio-form-wide">
            API key
            <input
              aria-label="Provider API key"
              onChange={(event) => onDraft({ ...draft, api_key: event.target.value })}
              placeholder="Stored key stays hidden after save"
              type="password"
              value={draft.api_key}
            />
          </label>
          <label>
            Thinking
            <input
              checked={draft.thinking_enabled}
              onChange={(event) => onDraft({ ...draft, thinking_enabled: event.target.checked })}
              type="checkbox"
            />
          </label>
          <label>
            Reasoning effort
            <select
              onChange={(event) =>
                onDraft({ ...draft, reasoning_effort: event.target.value as "high" | "max" })
              }
              value={draft.reasoning_effort}
            >
              <option value="high">High</option>
              <option value="max">Max (higher cost)</option>
            </select>
          </label>
          <NumberField label="Max output tokens" value={draft.max_output_tokens} onChange={(value) => onDraft({ ...draft, max_output_tokens: value })} />
          <NumberField label="Context window" value={draft.context_window} onChange={(value) => onDraft({ ...draft, context_window: value })} />
          <NumberField label="Input cost / 1M" value={draft.input_cost_per_million} onChange={(value) => onDraft({ ...draft, input_cost_per_million: value })} />
          <NumberField label="Output cost / 1M" value={draft.output_cost_per_million} onChange={(value) => onDraft({ ...draft, output_cost_per_million: value })} />
        </div>
        <div className="workbench-action-row">
          <button className="workbench-primary-button" disabled={!draft.name.trim()} onClick={onCreate} type="button">
            <PlugZap aria-hidden="true" size={15} />
            Save provider
          </button>
        </div>
      </section>
      <section className="workbench-detail">
        <h2>Providers</h2>
        <div className="provider-list">
          {providers.providers.map((provider) => (
            <article className="provider-row" key={provider.id}>
              <div>
                <strong>{provider.name}</strong>
                <small>
                  {provider.model || "No model"} / {provider.base_url || "local"}
                  {" · "}
                  {provider.thinking_enabled ? `thinking ${provider.reasoning_effort}` : "thinking off"}
                  {" · "}key: {provider.api_key_source}
                </small>
              </div>
              <StatusBadge tone={["connection_failed", "insufficient_balance"].includes(provider.status) ? "error" : provider.configured ? "success" : "warning"}>
                {provider.status_label}
              </StatusBadge>
              <div className="workbench-action-row">
                <button className="workbench-secondary-button" onClick={() => onSetDefault(provider)} type="button">
                  {provider.default_for_conversation ? "Default" : "Use as default"}
                </button>
                <button className="workbench-secondary-button" onClick={() => onTest(provider.id)} type="button">
                  Test connection
                </button>
                {provider.id !== "local" ? (
                  <button className="workbench-secondary-button" onClick={() => onRemove(provider.id)} type="button">
                    Remove
                  </button>
                ) : null}
              </div>
            </article>
          ))}
        </div>
        {testResult ? <p className="workbench-muted">{testResult.message}{testResult.model ? ` ${testResult.provider}/${testResult.model} · ${testResult.latency_ms} ms` : ""}</p> : null}
        <p className="workbench-muted">
          Live smoke is CLI-only and always shows its call budget first; Test connection never starts coding.
        </p>
        <section className="workbench-detail-section">
          <h2>Usage and Economy</h2>
          <div className="usage-grid">
            <Metric label="Model calls this week" value={usage.aggregate.estimated_model_calls_this_week} />
            <Metric label="Deterministic operations" value={usage.aggregate.deterministic_operations} />
            <Metric label="Estimated cost" value={`$${usage.aggregate.estimated_cost.toFixed(6)}`} />
          </div>
          <p className="workbench-muted">{usage.estimate_note}</p>
          {usage.events.length === 0 ? (
            <p className="workbench-muted">No model usage recorded yet. Local mode remains available.</p>
          ) : (
            <div className="tool-timeline">
              {usage.events.slice(0, 8).map((event) => (
                <div className="tool-event" key={event.id}>
                  <span className="tool-event-dot" />
                  <span>
                    <strong>{event.message}</strong>
                    <small>{event.provider_model} / {event.task_type}</small>
                  </span>
                  <small>{formatDate(event.created_at)}</small>
                </div>
              ))}
            </div>
          )}
        </section>
        {status ? (
          <p className="workbench-muted">Runtime provider status: {status.active_label}</p>
        ) : null}
      </section>
    </div>
  );
}

function PolicySettings({ policy }: { policy: PolicyProfile | null }) {
  return (
    <section className="workbench-detail">
      <div className="workbench-detail-hero">
        <div>
          <StatusBadge tone="success">Active</StatusBadge>
          <h2>{policy?.name ?? "Balanced"}</h2>
          <p className="workbench-muted">{policy?.description ?? "Default policy profile."}</p>
        </div>
        <ShieldCheck aria-hidden="true" size={22} />
      </div>
      <p className="workbench-muted">
        Trust and autonomy controls live in Workbench today so approval behavior stays near
        real work. Advanced hard blocks remain enforced locally.
      </p>
    </section>
  );
}

function DataSettings({
  databasePath,
  schemaVersion,
  conversations,
  selectedConversationId,
  backup,
  restorePath,
  restoreMessage,
  exportResult,
  onSelectedConversation,
  onBackup,
  onRestorePath,
  onRestore,
  onExportConversation,
  onExportMemories,
}: {
  databasePath: string;
  schemaVersion: number;
  conversations: ConversationSummary[];
  selectedConversationId: string;
  backup: BackupResponse | null;
  restorePath: string;
  restoreMessage: string;
  exportResult: ExportResponse | null;
  onSelectedConversation: (value: string) => void;
  onBackup: () => void;
  onRestorePath: (value: string) => void;
  onRestore: () => void;
  onExportConversation: (format: "markdown" | "json") => void;
  onExportMemories: () => void;
}) {
  return (
    <div className="studio-two-column">
      <section className="workbench-detail">
        <h2>Backup and Restore</h2>
        <dl className="workbench-definition-grid">
          <div>
            <dt>Database path</dt>
            <dd>{databasePath}</dd>
          </div>
          <div>
            <dt>Schema</dt>
            <dd>{schemaVersion}</dd>
          </div>
        </dl>
        <div className="workbench-action-row">
          <button className="workbench-primary-button" onClick={onBackup} type="button">
            <DatabaseBackup aria-hidden="true" size={15} />
            Create backup
          </button>
        </div>
        {backup ? (
          <p className="workbench-muted">Backup saved at {backup.path}</p>
        ) : null}
        <label className="studio-form-wide">
          Restore backup path
          <input onChange={(event) => onRestorePath(event.target.value)} value={restorePath} />
        </label>
        <button
          className="workbench-secondary-button"
          disabled={!restorePath.trim()}
          onClick={onRestore}
          type="button"
        >
          <RotateCcw aria-hidden="true" size={15} />
          Restore compatible backup
        </button>
        {restoreMessage ? <p className="workbench-muted">{restoreMessage}</p> : null}
      </section>
      <section className="workbench-detail">
        <h2>Export</h2>
        <label>
          Conversation
          <select
            onChange={(event) => onSelectedConversation(event.target.value)}
            value={selectedConversationId}
          >
            {conversations.map((conversation) => (
              <option key={conversation.id} value={conversation.id}>
                {conversation.title}
              </option>
            ))}
          </select>
        </label>
        <div className="workbench-action-row">
          <button className="workbench-secondary-button" onClick={() => onExportConversation("markdown")} type="button">
            Markdown conversation
          </button>
          <button className="workbench-secondary-button" onClick={() => onExportConversation("json")} type="button">
            JSON conversation
          </button>
          <button className="workbench-secondary-button" onClick={onExportMemories} type="button">
            <Download aria-hidden="true" size={15} />
            Memory JSON
          </button>
        </div>
        {exportResult ? (
          <div className="workbench-output">
            <strong>{exportResult.filename}</strong>
            <pre>{exportResult.content.slice(0, 1400)}</pre>
          </div>
        ) : null}
      </section>
    </div>
  );
}

function AdvancedSettings({ settings }: { settings: StudioSettingsResponse }) {
  return (
    <section className="workbench-detail">
      <dl className="workbench-definition-grid">
        <div>
          <dt>Local API</dt>
          <dd>{settings.local_api_url}</dd>
        </div>
        <div>
          <dt>Static frontend</dt>
          <dd>{settings.static_assets_available ? "available" : "missing build"}</dd>
        </div>
      </dl>
      <p className="workbench-muted">
        Developer details are available only where they are safe to display. Secrets are never
        included in settings or export responses.
      </p>
    </section>
  );
}

interface ProviderDraft {
  provider_type: string;
  name: string;
  model: string;
  base_url: string;
  api_key: string;
  thinking_enabled: boolean;
  reasoning_effort: "high" | "max";
  max_output_tokens: number | null;
  context_window: number | null;
  input_cost_per_million: number | null;
  output_cost_per_million: number | null;
}

function emptyProviderDraft(): ProviderDraft {
  return {
    provider_type: "openai-compatible",
    name: "OpenAI-compatible",
    model: "",
    base_url: "",
    api_key: "",
    thinking_enabled: false,
    reasoning_effort: "high",
    max_output_tokens: 4096,
    context_window: 128000,
    input_cost_per_million: 0,
    output_cost_per_million: 0,
  };
}

function providerPayload(draft: ProviderDraft): StudioProviderUpsertRequest {
  return {
    api_key: draft.api_key || null,
    base_url: draft.base_url,
    default_for_conversation: false,
    intended_roles: ["conversation", "strategic_reasoning", "repo_question"],
    model: draft.model,
    name: draft.name,
    provider_type: draft.provider_type,
    thinking_enabled: draft.thinking_enabled,
    reasoning_effort: draft.reasoning_effort,
    max_output_tokens: draft.max_output_tokens,
    context_window: draft.context_window,
    input_cost_per_million: draft.input_cost_per_million,
    output_cost_per_million: draft.output_cost_per_million,
  };
}

function NumberField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: number | null;
  onChange: (value: number | null) => void;
}) {
  return (
    <label>
      {label}
      <input
        min="0"
        onChange={(event) => onChange(event.target.value ? Number(event.target.value) : null)}
        type="number"
        value={value ?? ""}
      />
    </label>
  );
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="metric-tile">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function labelize(value: string) {
  return value.replaceAll("_", " ").replace(/^\w/, (letter) => letter.toUpperCase());
}

function errorMessage(error: unknown, fallback: string) {
  return error instanceof StudioApiError ? error.message : fallback;
}
