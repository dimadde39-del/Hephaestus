import type {
  ConversationDetail,
  ConversationListResponse,
  ConversationSummary,
  CreateConversationRequest,
  ModeOption,
  PolicyProfile,
  PostMessageRequest,
  PostMessageResponse,
  ProviderStatusResponse,
  RecentRepo,
  SearchResponse,
  StudioConfig,
  StudioHealth,
  StudioMessage,
  UpdateConversationRequest,
} from "@/lib/types";

export class StudioApiError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(message: string, status: number, code = "REQUEST_FAILED") {
    super(message);
    this.name = "StudioApiError";
    this.status = status;
    this.code = code;
  }
}

export class StudioApiClient {
  private readonly baseUrl: string;

  constructor(baseUrl = resolveApiBaseUrl()) {
    this.baseUrl = baseUrl.replace(/\/$/, "");
  }

  health() {
    return this.request<StudioHealth>("/health");
  }

  config() {
    return this.request<StudioConfig>("/config");
  }

  conversations(params: {
    q?: string;
    includeArchived?: boolean;
    archivedOnly?: boolean;
    limit?: number;
  } = {}) {
    const search = new URLSearchParams();
    if (params.q) {
      search.set("q", params.q);
    }
    if (params.includeArchived) {
      search.set("include_archived", "true");
    }
    if (params.archivedOnly) {
      search.set("archived_only", "true");
    }
    if (params.limit) {
      search.set("limit", String(params.limit));
    }
    return this.request<ConversationListResponse>(`/conversations?${search.toString()}`);
  }

  createConversation(payload: CreateConversationRequest = {}) {
    return this.request<ConversationSummary>("/conversations", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  conversation(sessionId: string) {
    return this.request<ConversationDetail>(`/conversations/${encodeURIComponent(sessionId)}`);
  }

  messages(sessionId: string) {
    return this.request<StudioMessage[]>(
      `/conversations/${encodeURIComponent(sessionId)}/messages`,
    );
  }

  postMessage(sessionId: string, payload: PostMessageRequest) {
    return this.request<PostMessageResponse>(
      `/conversations/${encodeURIComponent(sessionId)}/messages`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
    );
  }

  updateConversation(sessionId: string, payload: UpdateConversationRequest) {
    return this.request<ConversationSummary>(`/conversations/${encodeURIComponent(sessionId)}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  }

  pinConversation(sessionId: string, isPinned: boolean) {
    return this.request<ConversationSummary>(
      `/conversations/${encodeURIComponent(sessionId)}/pin`,
      {
        method: "POST",
        body: JSON.stringify({ is_pinned: isPinned }),
      },
    );
  }

  archiveConversation(sessionId: string, isArchived: boolean) {
    return this.request<ConversationSummary>(
      `/conversations/${encodeURIComponent(sessionId)}/archive`,
      {
        method: "POST",
        body: JSON.stringify({ is_archived: isArchived }),
      },
    );
  }

  search(query: string, includeArchived = false) {
    const search = new URLSearchParams({ q: query });
    if (includeArchived) {
      search.set("include_archived", "true");
    }
    return this.request<SearchResponse>(`/search?${search.toString()}`);
  }

  modes() {
    return this.request<ModeOption[]>("/modes");
  }

  activePolicy() {
    return this.request<PolicyProfile>("/policy/active");
  }

  providerStatus() {
    return this.request<ProviderStatusResponse>("/providers/status");
  }

  recentRepos() {
    return this.request<RecentRepo[]>("/repos/recent");
  }

  private async request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...init.headers,
      },
    });
    if (!response.ok) {
      throw await apiErrorFromResponse(response);
    }
    return (await response.json()) as T;
  }
}

export function resolveApiBaseUrl() {
  const configured = process.env.NEXT_PUBLIC_HEPH_STUDIO_API;
  if (configured) {
    return configured.replace(/\/$/, "");
  }
  if (typeof window !== "undefined" && window.location.port !== "3000") {
    return `${window.location.origin}/api`;
  }
  return "http://127.0.0.1:8741/api";
}

async function apiErrorFromResponse(response: Response) {
  const fallback = `Request failed with status ${response.status}`;
  try {
    const body = (await response.json()) as {
      detail?: { code?: string; message?: string } | string;
    };
    if (typeof body.detail === "string") {
      return new StudioApiError(body.detail, response.status);
    }
    return new StudioApiError(
      body.detail?.message ?? fallback,
      response.status,
      body.detail?.code,
    );
  } catch {
    return new StudioApiError(fallback, response.status);
  }
}

export const studioApi = new StudioApiClient();
