import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createElement } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { StudioApp } from "@/features/studio/studio-app";
import type {
  ConversationSummary,
  DeliberationMode,
  RecentRepo,
  SearchResult,
  StudioMessage,
} from "@/lib/types";

const now = "2026-06-16T10:00:00.000Z";

const repos: RecentRepo[] = [
  {
    id: "repo_1",
    name: "Hephaestus",
    path: "C:/Users/Admin/Desktop/Hephaestus",
    stack_summary: "Python, Next.js",
    inspected_at: now,
  },
];

const modes = [
  { value: "balanced" as const, label: "Balanced", description: "Balanced" },
  { value: "strategic" as const, label: "Strategic", description: "Strategic" },
  { value: "architect" as const, label: "Architect", description: "Architect" },
  {
    value: "skeptical_but_fair" as const,
    label: "Skeptical but fair",
    description: "Skeptical but fair",
  },
];

describe("StudioApp", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    window.localStorage.clear();
    window.history.replaceState(null, "", "/");
    document.documentElement.removeAttribute("data-theme");
    document.documentElement.removeAttribute("data-appearance");
    vi.stubGlobal(
      "matchMedia",
      vi.fn().mockImplementation((query: string) => ({
        matches: query.includes("prefers-color-scheme: dark"),
        media: query,
        onchange: null,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        addListener: vi.fn(),
        removeListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    );
  });

  it("renders the conversation sidebar, provider indicator, and context drawer", async () => {
    installFetchMock();
    renderStudio();

    expect(
      await screen.findByRole("heading", { name: "Validation-backed coding loop" }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Provider: Local deterministic mode")).toBeInTheDocument();
    expect(screen.getByLabelText("Conversation mode")).toHaveValue("strategic");
    expect(screen.getByRole("heading", { name: "Thread details" })).toBeInTheDocument();
    expect(screen.getByText("No linked artifacts yet.")).toBeInTheDocument();
  });

  it("persists system, light, and dark appearance settings locally", async () => {
    const user = userEvent.setup();
    installFetchMock();
    renderStudio();

    await screen.findByRole("heading", { name: "Validation-backed coding loop" });
    expect(screen.getByRole("button", { name: "System" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(document.documentElement.dataset.theme).toBe("dark");

    await user.click(screen.getByRole("button", { name: "Light" }));
    expect(window.localStorage.getItem("heph:studio:appearance")).toBe("light");
    expect(document.documentElement.dataset.theme).toBe("light");

    await user.click(screen.getByRole("button", { name: "Dark" }));
    expect(window.localStorage.getItem("heph:studio:appearance")).toBe("dark");
    expect(document.documentElement.dataset.theme).toBe("dark");

    await user.click(screen.getByRole("button", { name: "System" }));
    expect(window.localStorage.getItem("heph:studio:appearance")).toBe("system");
    expect(document.documentElement.dataset.appearance).toBe("system");
  });

  it("creates a conversation with the New chat action and keyboard shortcut", async () => {
    const { fetchSpy } = installFetchMock();
    const user = userEvent.setup();
    renderStudio();

    await screen.findByRole("heading", { name: "Validation-backed coding loop" });
    await user.click(screen.getByRole("button", { name: "New chat" }));
    expect(await screen.findByRole("heading", { name: "New Conversation" })).toBeInTheDocument();

    await user.keyboard("{Control>}n{/Control}");
    await waitFor(() => expect(fetchSpy).toHaveBeenCalledWith(
      expect.stringContaining("/api/conversations"),
      expect.objectContaining({ method: "POST" }),
    ));
  });

  it("opens an existing conversation and preserves the exact message timeline", async () => {
    installFetchMock();
    const user = userEvent.setup();
    renderStudio();

    await user.click(await screen.findByText("README positioning versus Hermes"));

    expect(await screen.findByText("Clarify positioning against Hermes exactly.")).toBeInTheDocument();
    expect(screen.getByText("Hermes remains complementary, not replaced.")).toBeInTheDocument();
  });

  it("uses a readable conversation structure without replacing exact messages", async () => {
    installFetchMock();
    renderStudio();

    const userMessage = await screen.findByText("Please preserve exact chat history.");
    const assistantMessage = screen.getByText("Persistent chat keeps original messages.");
    const userArticle = userMessage.closest("article");
    const assistantArticle = assistantMessage.closest("article");

    expect(userArticle).toHaveClass("message-block", "user");
    expect(userArticle).toHaveAttribute("data-role", "user");
    expect(assistantArticle).toHaveClass("message-block", "assistant");
    expect(assistantArticle).toHaveAttribute("data-role", "assistant");
    expect(screen.getByText("bash")).toBeInTheDocument();
    expect(screen.queryByText(/context resume/i)).not.toBeInTheDocument();
  });

  it("sends a message and shows the pending state", async () => {
    const deferred = createDeferred<Response>();
    installFetchMock({ postMessageResponse: deferred.promise });
    const user = userEvent.setup();
    renderStudio();

    await screen.findByRole("heading", { name: "Validation-backed coding loop" });
    await user.type(screen.getByLabelText("Message Hephaestus"), "Add exact history tests");
    await user.click(screen.getByRole("button", { name: "Send message" }));

    expect(screen.getByLabelText("Hephaestus is responding")).toBeInTheDocument();
    deferred.resolve(jsonResponse(postMessagePayload("conv_1", "Add exact history tests")));

    expect((await screen.findAllByText("Add exact history tests")).length).toBeGreaterThan(0);
    expect(screen.getByText("Persisted agent response for Add exact history tests")).toBeInTheDocument();
  });

  it("sends with Enter and keeps Shift+Enter as a newline", async () => {
    const { fetchSpy } = installFetchMock();
    const user = userEvent.setup();
    renderStudio();

    await screen.findByRole("heading", { name: "Validation-backed coding loop" });
    const input = screen.getByLabelText("Message Hephaestus");
    await user.click(input);
    await user.keyboard("Line one{Shift>}{Enter}{/Shift}Line two");
    expect(input).toHaveValue("Line one\nLine two");

    await user.keyboard("{Enter}");
    await waitFor(() =>
      expect(fetchSpy).toHaveBeenCalledWith(
        expect.stringContaining("/api/conversations/conv_1/messages"),
        expect.objectContaining({ method: "POST" }),
      ),
    );
  });

  it("shows a retryable error when sending fails", async () => {
    installFetchMock({ failPostMessage: true });
    const user = userEvent.setup();
    renderStudio();

    await screen.findByRole("heading", { name: "Validation-backed coding loop" });
    await user.type(screen.getByLabelText("Message Hephaestus"), "Trigger failure");
    await user.click(screen.getByRole("button", { name: "Send message" }));

    expect(await screen.findByText("Message failed")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it("renames, pins, archives, and reveals archived conversations", async () => {
    installFetchMock();
    const user = userEvent.setup();
    renderStudio();

    await screen.findByRole("heading", { name: "Validation-backed coding loop" });
    const row = screen.getByText("README positioning versus Hermes").closest("article");
    expect(row).not.toBeNull();

    await user.click(within(row as HTMLElement).getByRole("button", { name: "Rename conversation" }));
    const input = within(row as HTMLElement).getByLabelText("Conversation title");
    await user.clear(input);
    await user.type(input, "Hermes boundary");
    fireEvent.keyDown(input, { key: "Enter" });
    expect(await screen.findByText("Hermes boundary")).toBeInTheDocument();

    await user.click(within(row as HTMLElement).getByRole("button", { name: "Pin conversation" }));
    await waitFor(() => {
      const pinnedRow = screen.getByText("Hermes boundary").closest("article");
      expect(pinnedRow).not.toBeNull();
      expect(
        within(pinnedRow as HTMLElement).getByRole("button", { name: "Unpin conversation" }),
      ).toBeInTheDocument();
    });

    const pinnedRow = screen.getByText("Hermes boundary").closest("article");
    await user.click(within(pinnedRow as HTMLElement).getByRole("button", { name: "Archive conversation" }));
    await user.click(screen.getByRole("button", { name: /show archived/i }));
    expect(await screen.findByText("Hermes boundary")).toBeInTheDocument();
  });

  it("searches past messages and opens the matching message", async () => {
    installFetchMock();
    const user = userEvent.setup();
    renderStudio();

    await screen.findByRole("heading", { name: "Validation-backed coding loop" });
    await user.keyboard("{Control>}k{/Control}");
    expect(screen.getByRole("dialog", { name: "Search conversations" })).toBeInTheDocument();
    await user.type(screen.getByLabelText("Search past conversations and messages"), "Hermes");
    await user.click(await screen.findByText("Hermes remains complementary, not replaced."));

    expect(await screen.findByText("Clarify positioning against Hermes exactly.")).toBeInTheDocument();
  });

  it("updates mode and repo selectors", async () => {
    const { fetchSpy } = installFetchMock();
    const user = userEvent.setup();
    renderStudio();

    await screen.findByRole("heading", { name: "Validation-backed coding loop" });
    await user.selectOptions(screen.getByLabelText("Conversation mode"), "architect");
    await user.selectOptions(screen.getByLabelText("Repository context"), "repo_1");

    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalledWith(
        expect.stringContaining("/api/conversations/conv_1"),
        expect.objectContaining({ method: "PATCH" }),
      );
    });
    expect(screen.getByLabelText("Repository context")).toHaveValue("repo_1");
  });

  it("collapses the right context drawer", async () => {
    installFetchMock();
    const user = userEvent.setup();
    renderStudio();

    await screen.findByRole("heading", { name: "Validation-backed coding loop" });
    await user.click(screen.getAllByRole("button", { name: "Collapse context" })[0]);
    expect(document.querySelector(".context-drawer.is-collapsed")).toBeInTheDocument();
  });

  it("collapses the sidebar into a compact rail", async () => {
    installFetchMock();
    const user = userEvent.setup();
    renderStudio();

    await screen.findByRole("heading", { name: "Validation-backed coding loop" });
    await user.click(screen.getByRole("button", { name: "Collapse sidebar" }));
    expect(screen.getByLabelText("Conversations")).toHaveClass("is-collapsed");
    expect(screen.getByRole("button", { name: "Expand sidebar" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "New chat" })).toBeInTheDocument();
  });

  it("opens the responsive sidebar drawer", async () => {
    installFetchMock();
    const user = userEvent.setup();
    renderStudio();

    await screen.findByRole("heading", { name: "Validation-backed coding loop" });
    await user.click(screen.getByRole("button", { name: "Open conversations" }));

    expect(screen.getByLabelText("Conversations")).toHaveClass("is-open");
  });
});

interface FetchMockOptions {
  failPostMessage?: boolean;
  postMessageResponse?: Promise<Response>;
}

function installFetchMock(options: FetchMockOptions = {}) {
  const state = createState();
  const fetchSpy = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(typeof input === "string" ? input : input.toString());
    const path = url.pathname.replace(/^\/api/, "");
    const method = init?.method ?? "GET";

    if (path === "/config") {
      return jsonResponse({
        app_name: "Hephaestus Studio",
        version: "0.1.0",
        database_path: "C:/tmp/hephaestus.db",
        default_host: "127.0.0.1",
        default_port: 8741,
        default_url: "http://127.0.0.1:8741",
        static_assets_available: false,
        active_policy_profile: "Balanced",
        provider_label: "Local deterministic mode",
        local_mode_available: true,
      });
    }
    if (path === "/providers/status") {
      return jsonResponse({
        active_label: "Local deterministic mode",
        active_provider: "local/fake",
        statuses: [
          {
            provider: "local/fake",
            label: "Local deterministic mode",
            available: true,
            detail: "deterministic local fallback; no API key required",
            profile_count: 3,
            local: true,
          },
        ],
      });
    }
    if (path === "/policy/active") {
      return jsonResponse({
        id: "balanced",
        name: "Balanced",
        profile_type: "balanced",
        description: "Default policy profile.",
      });
    }
    if (path === "/modes") {
      return jsonResponse(modes);
    }
    if (path === "/repos/recent") {
      return jsonResponse(repos);
    }
    if (path === "/conversations" && method === "GET") {
      return jsonResponse({
        conversations: state.conversations,
        limit: 120,
        offset: 0,
        total: state.conversations.length,
      });
    }
    if (path === "/conversations" && method === "POST") {
      const body = parseBody(init);
      const conversation = makeConversation({
        id: `conv_${state.conversations.length + 1}`,
        title: typeof body.title === "string" ? body.title : "New Conversation",
        mode: (body.mode as DeliberationMode | undefined) ?? "balanced",
        repo_profile_id:
          typeof body.repo_profile_id === "string" ? body.repo_profile_id : null,
      });
      state.conversations.unshift(conversation);
      state.messages[conversation.id] = [];
      return jsonResponse(conversation, 201);
    }
    const conversationMatch = /^\/conversations\/([^/]+)$/.exec(path);
    if (conversationMatch && method === "GET") {
      const conversation = state.conversations.find((item) => item.id === conversationMatch[1]);
      return jsonResponse({
        conversation,
        regular_memory_count: 2,
        strategic_memory_count: 1,
        linked_artifact_count: 1,
      });
    }
    if (conversationMatch && method === "PATCH") {
      const body = parseBody(init);
      const conversation = updateConversation(state, conversationMatch[1], body);
      return jsonResponse(conversation);
    }
    const messagesMatch = /^\/conversations\/([^/]+)\/messages$/.exec(path);
    if (messagesMatch && method === "GET") {
      return jsonResponse(state.messages[messagesMatch[1]] ?? []);
    }
    if (messagesMatch && method === "POST") {
      if (options.failPostMessage) {
        return jsonResponse({ detail: { code: "MESSAGE_FAILED", message: "Provider failed" } }, 500);
      }
      if (options.postMessageResponse) {
        return options.postMessageResponse;
      }
      const body = parseBody(init);
      return jsonResponse(postMessagePayload(messagesMatch[1], String(body.content)));
    }
    const pinMatch = /^\/conversations\/([^/]+)\/pin$/.exec(path);
    if (pinMatch) {
      const body = parseBody(init);
      const conversation = updateConversation(state, pinMatch[1], {
        is_pinned: Boolean(body.is_pinned),
      });
      return jsonResponse(conversation);
    }
    const archiveMatch = /^\/conversations\/([^/]+)\/archive$/.exec(path);
    if (archiveMatch) {
      const body = parseBody(init);
      const conversation = updateConversation(state, archiveMatch[1], {
        is_archived: Boolean(body.is_archived),
      });
      return jsonResponse(conversation);
    }
    if (path === "/search") {
      const query = url.searchParams.get("q") ?? "";
      return jsonResponse({
        query,
        results: searchResults().filter((result) =>
          result.snippet.toLowerCase().includes(query.toLowerCase()),
        ),
      });
    }
    return jsonResponse({ detail: { code: "NOT_FOUND", message: path } }, 404);
  });
  vi.stubGlobal("fetch", fetchSpy);
  return { fetchSpy, state };
}

function createState() {
  const conversations = [
    makeConversation({
      id: "conv_1",
      title: "Validation-backed coding loop",
      mode: "strategic",
      repo_profile_id: "repo_1",
      is_pinned: true,
      last_message_preview: "Persist exact messages.",
    }),
    makeConversation({
      id: "conv_2",
      title: "README positioning versus Hermes",
      mode: "balanced",
      last_message_preview: "Hermes remains complementary.",
    }),
  ];
  const messages: Record<string, StudioMessage[]> = {
    conv_1: [
      message("msg_1", "conv_1", "user", "Please preserve exact chat history."),
      message(
        "msg_2",
        "conv_1",
        "assistant",
        "Persistent chat keeps original messages.\n\n```bash\nuv run heph studio doctor\n```",
      ),
    ],
    conv_2: [
      message("msg_3", "conv_2", "user", "Clarify positioning against Hermes exactly."),
      message("msg_4", "conv_2", "assistant", "Hermes remains complementary, not replaced."),
    ],
  };
  return { conversations, messages };
}

function postMessagePayload(sessionId: string, content: string) {
  const user = message(`msg_user_${content.length}`, sessionId, "user", content);
  const assistant = message(
    `msg_assistant_${content.length}`,
    sessionId,
    "assistant",
    `Persisted agent response for ${content}`,
  );
  return {
    conversation: makeConversation({
      id: sessionId,
      title: content,
      mode: "strategic",
      repo_profile_id: "repo_1",
      last_message_preview: assistant.content,
    }),
    messages: [user, assistant],
    assistant_message_id: assistant.id,
    provider_model: "local/fake-balanced",
    selected_memory_count: 0,
    selected_strategic_memory_count: 0,
  };
}

function makeConversation(
  overrides: Partial<ConversationSummary> & {
    id: string;
    title: string;
    mode?: DeliberationMode;
  },
): ConversationSummary {
  return {
    id: overrides.id,
    title: overrides.title,
    created_at: overrides.created_at ?? now,
    updated_at: overrides.updated_at ?? now,
    mode: overrides.mode ?? "balanced",
    repo_profile_id: overrides.repo_profile_id ?? null,
    repo_name: overrides.repo_name ?? (overrides.repo_profile_id ? "Hephaestus" : null),
    workspace_path: overrides.workspace_path ?? null,
    is_pinned: overrides.is_pinned ?? false,
    is_archived: overrides.is_archived ?? false,
    last_opened_at: overrides.last_opened_at ?? null,
    message_count: overrides.message_count ?? 2,
    last_message_preview: overrides.last_message_preview ?? "",
    linked_decision_count: overrides.linked_decision_count ?? 0,
    coding_request_count: overrides.coding_request_count ?? 0,
    validation_run_count: overrides.validation_run_count ?? 0,
  };
}

function message(
  id: string,
  sessionId: string,
  role: "user" | "assistant",
  content: string,
): StudioMessage {
  return {
    id,
    session_id: sessionId,
    role,
    content,
    created_at: now,
    intent: null,
    mode: "balanced",
    provider_model: role === "assistant" ? "local/fake-balanced" : null,
    metadata: {},
  };
}

function searchResults(): SearchResult[] {
  return [
    {
      conversation_id: "conv_2",
      conversation_title: "README positioning versus Hermes",
      match_type: "message",
      snippet: "Hermes remains complementary, not replaced.",
      message_id: "msg_4",
      role: "assistant",
      occurred_at: now,
      is_archived: false,
    },
  ];
}

function updateConversation(
  state: ReturnType<typeof createState>,
  conversationId: string,
  body: Record<string, unknown>,
) {
  const current = state.conversations.find((item) => item.id === conversationId);
  if (!current) {
    throw new Error(`Missing conversation ${conversationId}`);
  }
  const updated: ConversationSummary = {
    ...current,
    title: typeof body.title === "string" ? body.title : current.title,
    mode: (body.mode as DeliberationMode | undefined) ?? current.mode,
    repo_profile_id:
      "repo_profile_id" in body ? (body.repo_profile_id as string | null) : current.repo_profile_id,
    repo_name: body.repo_profile_id === "repo_1" ? "Hephaestus" : current.repo_name,
    is_pinned:
      typeof body.is_pinned === "boolean" ? body.is_pinned : current.is_pinned,
    is_archived:
      typeof body.is_archived === "boolean" ? body.is_archived : current.is_archived,
  };
  state.conversations = [
    updated,
    ...state.conversations.filter((item) => item.id !== conversationId),
  ];
  return updated;
}

function parseBody(init: RequestInit | undefined): Record<string, unknown> {
  if (!init?.body) {
    return {};
  }
  return JSON.parse(String(init.body)) as Record<string, unknown>;
}

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function createDeferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((innerResolve, innerReject) => {
    resolve = innerResolve;
    reject = innerReject;
  });
  return { promise, resolve, reject };
}

function renderStudio() {
  return render(createElement(StudioApp));
}
