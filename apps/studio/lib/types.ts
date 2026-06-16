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
