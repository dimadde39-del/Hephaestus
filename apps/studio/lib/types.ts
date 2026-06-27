export type ConversationRole = "user" | "assistant" | "system";

export type DeliberationMode =
  | "balanced"
  | "direct"
  | "critical"
  | "strategic"
  | "research"
  | "architect"
  | "coach"
  | "skeptical_but_fair";

export type StudioStatus = "ok" | "warn" | "error";

export interface StudioHealth {
  status: StudioStatus;
  database_path: string;
  static_assets_available: boolean;
  provider_label: string;
  policy_profile: string;
}

export interface StudioConfig {
  app_name: string;
  version: string;
  database_path: string;
  default_host: string;
  default_port: number;
  default_url: string;
  static_assets_available: boolean;
  active_policy_profile: string;
  provider_label: string;
  local_mode_available: boolean;
}

export interface ConversationSummary {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  mode: DeliberationMode;
  repo_profile_id: string | null;
  repo_name: string | null;
  workspace_path: string | null;
  is_pinned: boolean;
  is_archived: boolean;
  last_opened_at: string | null;
  message_count: number;
  last_message_preview: string;
  linked_decision_count: number;
  coding_request_count: number;
  validation_run_count: number;
}

export interface ConversationDetail {
  conversation: ConversationSummary;
  regular_memory_count: number;
  strategic_memory_count: number;
  linked_artifact_count: number;
}

export interface StudioMessage {
  id: string;
  session_id: string;
  role: ConversationRole;
  content: string;
  created_at: string;
  intent: string | null;
  mode: DeliberationMode | null;
  provider_model: string | null;
  metadata: Record<string, unknown>;
}

export interface ConversationListResponse {
  conversations: ConversationSummary[];
  limit: number;
  offset: number;
  total: number;
}

export interface CreateConversationRequest {
  title?: string | null;
  mode?: DeliberationMode;
  repo_profile_id?: string | null;
  workspace_path?: string | null;
}

export interface UpdateConversationRequest {
  title?: string;
  mode?: DeliberationMode;
  repo_profile_id?: string | null;
  workspace_path?: string | null;
}

export interface PostMessageRequest {
  content: string;
  mode?: DeliberationMode | null;
  repo_profile_id?: string | null;
  workspace_path?: string | null;
  provider?: string;
}

export interface PostMessageResponse {
  conversation: ConversationSummary;
  messages: StudioMessage[];
  assistant_message_id: string;
  provider_model: string;
  selected_memory_count: number;
  selected_strategic_memory_count: number;
}

export interface SearchResult {
  conversation_id: string;
  conversation_title: string;
  match_type: string;
  snippet: string;
  message_id: string | null;
  role: ConversationRole | null;
  occurred_at: string | null;
  is_archived: boolean;
}

export interface SearchResponse {
  query: string;
  results: SearchResult[];
}

export interface ModeOption {
  value: DeliberationMode;
  label: string;
  description: string;
}

export interface PolicyProfile {
  id: string;
  name: string;
  profile_type: string;
  description: string;
}

export interface ProviderStatusItem {
  provider: string;
  label: string;
  available: boolean;
  detail: string;
  profile_count: number;
  local: boolean;
}

export interface ProviderStatusResponse {
  active_label: string;
  active_provider: string;
  statuses: ProviderStatusItem[];
}

export interface RecentRepo {
  id: string;
  name: string;
  path: string;
  stack_summary: string;
  inspected_at: string;
}

export interface StudioLink {
  label: string;
  href: string;
}

export type StudioMemoryKind = "regular" | "strategic";
export type StudioMemoryScope = "global" | "project" | "repo" | "conversation";
export type StudioMemoryState = "active" | "archived" | "all";

export interface StudioMemoryEvidence {
  source: string;
  content: string;
  kind: string;
  source_id: string | null;
  confidence: number;
}

export interface StudioMemoryHistoryItem {
  at: string;
  event: string;
  detail: string;
}

export interface StudioMemorySummary {
  id: string;
  kind: StudioMemoryKind;
  type: string;
  type_label: string;
  summary: string;
  scope: StudioMemoryScope;
  project: string | null;
  repo_profile_id: string | null;
  repo_name: string | null;
  source: string;
  confidence: number;
  importance: number;
  stability: string;
  created_at: string;
  updated_at: string;
  archived: boolean;
  linked_conversation_id: string | null;
  conflict_count: number;
}

export interface StudioMemoryDetail extends StudioMemorySummary {
  content: string;
  evidence: StudioMemoryEvidence[];
  linked_conversation: StudioLink | null;
  linked_work: StudioLink[];
  conflict_warnings: string[];
  history: StudioMemoryHistoryItem[];
}

export interface StudioMemoryListResponse {
  memories: StudioMemorySummary[];
  total: number;
  filters: Record<string, string | null>;
  suggestions_pending: number;
}

export interface StudioMemoryCreateRequest {
  kind?: StudioMemoryKind;
  type?: string;
  content: string;
  summary?: string;
  scope?: StudioMemoryScope;
  project?: string | null;
  repo_profile_id?: string | null;
  conversation_id?: string | null;
  confidence?: number;
  importance?: number;
  stability?: string;
  source?: string;
  evidence?: StudioMemoryEvidence[];
  tags?: string[];
}

export type StudioMemoryPatchRequest = Partial<StudioMemoryCreateRequest> & {
  resolve_conflicts?: boolean;
};

export interface StudioMemorySuggestion {
  id: string;
  proposed_memory: string;
  why_it_may_matter: string;
  proposed_type: string;
  proposed_type_label: string;
  proposed_scope: StudioMemoryScope;
  proposed_stability: string;
  source: string;
  source_link: StudioLink | null;
  confidence: number;
  importance: number;
  status: string;
  created_at: string;
}

export interface StudioMemorySuggestionListResponse {
  suggestions: StudioMemorySuggestion[];
  total: number;
}

export type StudioProviderStatus =
  | "configured"
  | "testing"
  | "connected"
  | "not_configured"
  | "connection_failed"
  | "insufficient_balance"
  | "local_mode";

export interface StudioProviderConfig {
  id: string;
  provider_type: string;
  name: string;
  model: string;
  base_url: string;
  configured: boolean;
  status: StudioProviderStatus;
  status_label: string;
  status_detail: string;
  intended_roles: string[];
  context_window: number | null;
  input_cost_per_million: number | null;
  output_cost_per_million: number | null;
  thinking_enabled: boolean;
  reasoning_effort: "high" | "max";
  max_output_tokens: number | null;
  effective_source: string;
  api_key_source: string;
  default_for_conversation: boolean;
  created_at: string;
  updated_at: string;
}

export interface StudioProviderListResponse {
  providers: StudioProviderConfig[];
  default_provider_id: string;
  local_mode: StudioProviderConfig;
  storage_note: string;
}

export interface StudioProviderUpsertRequest {
  provider_type?: string;
  name: string;
  model?: string;
  base_url?: string;
  api_key?: string | null;
  context_window?: number | null;
  input_cost_per_million?: number | null;
  output_cost_per_million?: number | null;
  thinking_enabled?: boolean;
  reasoning_effort?: "high" | "max";
  max_output_tokens?: number | null;
  intended_roles?: string[];
  default_for_conversation?: boolean;
}

export interface StudioProviderTestResponse {
  id: string;
  status: StudioProviderStatus;
  message: string;
  provider: string;
  model: string;
  latency_ms: number;
}

export interface StudioSettings {
  startup_route: string;
  recent_repo_behavior: string;
  browser_auto_open: boolean;
  appearance: string;
  reduced_motion: boolean;
  density: string;
  active_policy_profile: string;
  debug_logging: boolean;
  developer_details: boolean;
  deterministic_mode: boolean;
}

export interface StudioSettingsResponse {
  settings: StudioSettings;
  database_path: string;
  schema_version: number;
  local_api_url: string;
  static_assets_available: boolean;
}

export type StudioSettingsPatchRequest = Partial<StudioSettings>;

export interface StudioUsageEvent {
  id: string;
  task_type: string;
  provider: string;
  model: string;
  provider_model: string;
  message: string;
  estimated_input_tokens: number;
  estimated_output_tokens: number;
  input_tokens: number;
  output_tokens: number;
  cached_input_tokens: number;
  estimated_cost: number;
  thinking_enabled: boolean;
  reasoning_effort: string | null;
  usage_source: string;
  deterministic: boolean;
  context_trimmed: boolean;
  success: boolean;
  linked_conversation: StudioLink | null;
  created_at: string;
}

export interface StudioUsageAggregate {
  estimated_model_calls_this_week: number;
  deterministic_operations: number;
  estimated_cost: number;
  cost_per_validated_successful_coding_task: number | null;
  provider_usage: Record<string, number>;
}

export interface StudioUsageResponse {
  aggregate: StudioUsageAggregate;
  events: StudioUsageEvent[];
  estimate_note: string;
}

export interface AdvancedArtifactSummary {
  id: string;
  title: string;
  kind: string;
  created_at: string;
  linked_work: StudioLink[];
}

export interface AdvancedDecisionSummary {
  id: string;
  decision_type: string;
  decision: string;
  selected_option: string;
  confidence: number;
  outcome: string | null;
  repo: string | null;
  occurred_at: string;
  href: string;
}

export interface AdvancedDecisionListResponse {
  decisions: AdvancedDecisionSummary[];
  total: number;
  pareto_frontiers: AdvancedArtifactSummary[];
  qubo_problems: AdvancedArtifactSummary[];
}

export interface AdvancedDecisionDetail extends AdvancedDecisionSummary {
  alternatives: string[];
  reasons: string[];
  assumptions: string[];
  evidence: string[];
  linked_work: StudioLink[];
  later_evidence_supported: string;
  developer_payload: Record<string, unknown> | null;
}

export interface AdvancedParetoCandidate {
  id: string;
  label: string;
  x: number;
  y: number;
  is_frontier: boolean;
  selected: boolean;
  rationale: string;
  objectives: Record<string, number>;
}

export interface AdvancedParetoDetail {
  id: string;
  title: string;
  objective_x: string;
  objective_y: string;
  selected_candidate_id: string | null;
  preference_profile: string;
  explanation: string;
  tradeoffs: string[];
  candidates: AdvancedParetoCandidate[];
  created_at: string;
}

export interface AdvancedQuboVariable {
  id: string;
  label: string;
  selected: boolean;
}

export interface AdvancedQuboDetail {
  id: string;
  purpose: string;
  problem_type: string;
  solver_used: string;
  selected_solution: string;
  objective_value: number | null;
  feasible: boolean | null;
  variables: AdvancedQuboVariable[];
  constraints: string[];
  comparison_with_heuristic: string | null;
  explanation: string;
  mathematical_details: Record<string, unknown>;
  created_at: string;
}

export interface ExportResponse {
  filename: string;
  format: string;
  content: string;
  includes_secrets: boolean;
}

export interface BackupResponse {
  path: string;
  schema_version: number;
  created_at: string;
  size_bytes: number;
}

export interface RestoreBackupResponse {
  restored: boolean;
  message: string;
  schema_version: number;
}

export type WorkbenchTone = "neutral" | "accent" | "success" | "warning" | "error";

export interface WorkbenchStatus {
  value: string;
  label: string;
  tone: WorkbenchTone;
}

export interface WorkbenchLink {
  label: string | null;
  href: string;
}

export interface WorkbenchArtifactSummary {
  id: string;
  kind: string;
  title: string;
  status: WorkbenchStatus;
  repo: string;
  repo_path: string;
  summary: string;
  files_changed: number;
  validation: string;
  checkpoint: string;
  conversation_id: string | null;
  created_at: string;
  updated_at: string | null;
  href: string;
}

export interface PendingDecision {
  id: string;
  kind: string;
  title: string;
  description: string;
  repo: string;
  files: string[];
  risk: string;
  rollback_available: boolean;
  external_side_effects: boolean;
  primary_label: string;
  primary_endpoint: string;
  reject_label: string;
}

export interface WorkbenchOverview {
  active_coding_work: WorkbenchArtifactSummary[];
  recent_completed_coding_work: WorkbenchArtifactSummary[];
  recent_validation_runs: WorkbenchArtifactSummary[];
  failed_validation_requiring_attention: WorkbenchArtifactSummary[];
  pending_decisions: PendingDecision[];
  recent_checkpoints: WorkbenchArtifactSummary[];
  latest_release_evidence: WorkbenchArtifactSummary[];
}

export interface CodingRequestSummary {
  id: string;
  title: string;
  repo: string;
  repo_path: string;
  scope: string;
  risk: string;
  status: WorkbenchStatus;
  files_touched: string[];
  validation_result: string;
  checkpoint_state: string;
  conversation_id: string | null;
  conversation_title: string | null;
  created_at: string;
  updated_at: string;
  href: string;
}

export interface CodingListResponse {
  items: CodingRequestSummary[];
  total: number;
  filters: Record<string, string | null>;
}

export interface CodingPlanView {
  summary: string;
  steps: string[];
  expected_files: string[];
  validation_strategy: string[];
  rollback_behavior: string;
  current_state: WorkbenchStatus;
}

export interface DiffStats {
  additions: number;
  deletions: number;
  line_count: number;
  large: boolean;
}

export interface CodingPatchView {
  id: string;
  status: WorkbenchStatus;
  summary: string;
  files: string[];
  proposed: boolean;
  applied: boolean;
  diff: string;
  diff_stats: DiffStats;
  review_result: string;
  protected_files: string[];
}

export interface ValidationCommandView {
  id: string;
  command_type: string;
  command: string;
  risk: string;
  status: WorkbenchStatus;
  exit_code: number | null;
  duration_seconds: number;
  output_summary: string;
  stdout: string;
  stderr: string;
  output_truncated: boolean;
  tool_action_id: string | null;
  outcome_id: string | null;
  readiness_effect: number;
}

export interface ValidationSummary {
  id: string;
  repo: string;
  repo_path: string;
  related_coding_request_id: string | null;
  release_plan_id: string | null;
  evidence_mode: string;
  total_commands: number;
  passed: number;
  failed: number;
  skipped: number;
  duration_seconds: number;
  status: WorkbenchStatus;
  created_at: string;
  href: string;
}

export interface ValidationListResponse {
  items: ValidationSummary[];
  total: number;
}

export interface ValidationDetailResponse {
  summary: ValidationSummary;
  commands: ValidationCommandView[];
  linked_tool_actions: WorkbenchLink[];
  linked_outcomes: WorkbenchLink[];
}

export interface ValidationPlanResponse {
  id: string;
  repo: string;
  repo_path: string;
  commands: ValidationCommandView[];
  notes: string[];
  status: WorkbenchStatus;
}

export interface CheckpointSummary {
  id: string;
  created_at: string;
  associated_coding_request_id: string | null;
  files_covered: string[];
  availability: string;
  restored_at: string | null;
  href: string;
}

export interface CheckpointFileView {
  path: string;
  existed: boolean;
  original_hash: string;
  protected: boolean;
  modified_at: string | null;
}

export interface CheckpointDetailResponse {
  summary: CheckpointSummary;
  workspace_path: string;
  files: CheckpointFileView[];
  related_patch_id: string | null;
  validation_result: string;
  restore_warnings: string[];
  restore_history: WorkbenchLink[];
}

export interface ToolActionSummary {
  id: string;
  action: string;
  status: WorkbenchStatus;
  risk: string;
  policy_decision: string;
  result: string;
  related_coding_request_id: string | null;
  related_validation_id: string | null;
  created_at: string;
  href: string;
}

export interface ToolActionDetailResponse {
  summary: ToolActionSummary;
  workspace_path: string;
  command: string;
  target_path: string;
  files_touched: string[];
  stdout: string;
  stderr: string;
  exit_code: number | null;
  checkpoint_id: string | null;
  outcome_id: string | null;
  observations: string[];
}

export interface ReleaseSummary {
  id: string;
  repo: string;
  repo_path: string;
  readiness: number;
  evidence_mode: string;
  validation_status: string;
  blockers: string[];
  recommendation: string;
  created_at: string;
  linked_work: WorkbenchLink[];
  href: string;
}

export interface ReleaseListResponse {
  items: ReleaseSummary[];
  total: number;
}

export interface ReleaseDetailResponse {
  summary: ReleaseSummary;
  practical_summary: string;
  real_validation_evidence: ValidationSummary[];
  blockers: string[];
  next_actions: string[];
  related_coding_requests: CodingRequestSummary[];
  advanced_optimization_details: {
    pareto_frontier_ids: string[];
    qubo_problem_ids: string[];
  };
}

export interface OutcomeSummary {
  id: string;
  what_happened: string;
  evidence: string;
  status: WorkbenchStatus;
  rollback: string;
  practical_lesson: string;
  related_task: string;
  observed_at: string;
  href: string;
}

export interface OutcomeListResponse {
  items: OutcomeSummary[];
  total: number;
}

export interface OutcomeDetailResponse {
  summary: OutcomeSummary;
  evidence_items: string[];
  reflections: string[];
  what_hephaestus_learned: string[];
  related_links: WorkbenchLink[];
}

export interface CodingDetailResponse {
  summary: CodingRequestSummary;
  original_user_request: string;
  linked_conversation: WorkbenchLink | null;
  policy_trust_profile: string;
  plan: CodingPlanView | null;
  changes: CodingPatchView[];
  validation: ValidationDetailResponse[];
  result: string;
  practical_next_step: string;
  checkpoint_available: boolean;
  rollback_available: boolean;
  advanced_details: Record<string, string[]>;
}

export type TrustMode = "manual" | "developer" | "local_power_user" | "strict";

export type TrustRuleKey =
  | "read_repo_files"
  | "search_repo"
  | "inspect_repo_metadata"
  | "create_coding_plans"
  | "create_patch_proposals"
  | "create_checkpoints"
  | "run_safe_validation"
  | "apply_low_risk_documentation_patches"
  | "apply_low_risk_code_patches_with_validation"
  | "restore_checkpoints"
  | "install_dependencies"
  | "push_git_changes"
  | "send_external_messages";

export interface TrustRule {
  key: TrustRuleKey;
  label: string;
  allowed: boolean;
  implemented: boolean;
  risk: string;
  hard_blocked: boolean;
}

export interface TrustSettingsResponse {
  mode: TrustMode;
  effective_policy_profile: string;
  rules: TrustRule[];
  effective_behavior: string[];
  hard_blocks: string[];
  updated_at: string;
}

export interface CodingPlanRequest {
  user_request: string;
  repo_path?: string;
  scope?: string | null;
  conversation_id?: string | null;
}

export type CodingProposeRequest = CodingPlanRequest;

export interface CodingApplyRequest {
  approved?: boolean;
  dry_run?: boolean;
  no_validate?: boolean;
  rollback_on_failure?: boolean;
}

export interface ValidationPlanRequest {
  repo_path?: string;
  release_plan_id?: string | null;
}

export interface ValidationRunRequest {
  repo_path?: string;
  plan_id?: string | null;
  release_plan_id?: string | null;
  approved?: boolean;
  dry_run?: boolean;
  stop_on_failure?: boolean;
}

export interface CheckpointRestoreRequest {
  approved?: boolean;
  dry_run?: boolean;
}
