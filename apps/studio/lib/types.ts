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
