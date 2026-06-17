import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createElement } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { StudioApp } from "@/features/studio/studio-app";
import type {
  CheckpointDetailResponse,
  CheckpointSummary,
  ConversationSummary,
  CodingDetailResponse,
  CodingRequestSummary,
  DeliberationMode,
  OutcomeDetailResponse,
  OutcomeSummary,
  RecentRepo,
  ReleaseDetailResponse,
  ReleaseSummary,
  SearchResult,
  StudioMemoryDetail,
  StudioMessage,
  StudioProviderConfig,
  StudioSettings,
  StudioUsageResponse,
  ToolActionDetailResponse,
  ToolActionSummary,
  TrustSettingsResponse,
  ValidationDetailResponse,
  ValidationSummary,
  WorkbenchArtifactSummary,
  WorkbenchOverview,
  WorkbenchStatus,
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

  it("keeps Chat as the default route and opens the Workbench overview from primary navigation", async () => {
    installFetchMock();
    const user = userEvent.setup();
    renderStudio();

    expect(await screen.findByRole("heading", { name: "Validation-backed coding loop" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Workbench" }));

    expect((await screen.findAllByRole("heading", { name: "Agent Workbench" })).length).toBeGreaterThan(0);
    expect(screen.getByText("README positioning update")).toBeInTheDocument();
    expect(screen.getByText("Fix provider fallback")).toBeInTheDocument();
    expect(screen.getByText("Approve patch batch")).toBeInTheDocument();
    expect(screen.queryByLabelText("Message Hephaestus")).not.toBeInTheDocument();
    expect(window.location.pathname).toBe("/workbench");
  });

  it("renders coding detail with a readable diff and linked conversation", async () => {
    installFetchMock();
    const user = userEvent.setup();
    window.history.replaceState(null, "", "/workbench/coding/coding_1");
    renderStudio();

    expect(await screen.findByRole("heading", { name: "README positioning update" })).toBeInTheDocument();
    expect(screen.getAllByText("README.md").length).toBeGreaterThan(0);
    expect(screen.getByText("+Talk in Chat.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /copy patch/i })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /open linked conversation/i }));
    expect(await screen.findByText("Please preserve exact chat history.")).toBeInTheDocument();
    expect(window.location.pathname).toBe("/conversations/conv_1");
  });

  it("filters coding requests locally through typed API parameters", async () => {
    const { fetchSpy } = installFetchMock();
    const user = userEvent.setup();
    window.history.replaceState(null, "", "/workbench/coding");
    renderStudio();

    expect(await screen.findByLabelText("Search coding requests")).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Status"), "completed");

    await waitFor(() =>
      expect(fetchSpy).toHaveBeenCalledWith(
        expect.stringContaining("status=completed"),
        expect.objectContaining({
          headers: expect.any(Object),
        }),
      ),
    );
  });

  it("renders validation detail with collapsed command output", async () => {
    installFetchMock();
    const user = userEvent.setup();
    window.history.replaceState(null, "", "/workbench/validation/validation_1");
    renderStudio();

    expect(await screen.findByRole("heading", { name: "Hephaestus" })).toBeInTheDocument();
    expect(screen.getByText("uv run pytest")).toBeInTheDocument();
    expect(screen.queryByText("162 passed")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /uv run pytest/i }));
    expect(screen.getByText("162 passed")).toBeInTheDocument();
    expect(screen.getByText("Output was truncated.")).toBeInTheDocument();
  });

  it("confirms checkpoint restore as one batch", async () => {
    const { fetchSpy } = installFetchMock();
    const user = userEvent.setup();
    window.history.replaceState(null, "", "/workbench/checkpoints/checkpoint_1");
    renderStudio();

    expect(await screen.findByRole("heading", { name: "checkpoint_1" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Restore checkpoint" }));
    expect(screen.getByRole("dialog", { name: "Restore checkpoint?" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Restore" }));

    await waitFor(() =>
      expect(fetchSpy).toHaveBeenCalledWith(
        expect.stringContaining("/api/checkpoints/checkpoint_1/restore"),
        expect.objectContaining({ method: "POST" }),
      ),
    );
  });

  it("updates trust settings and shows effective behavior", async () => {
    const { fetchSpy } = installFetchMock();
    const user = userEvent.setup();
    window.history.replaceState(null, "", "/workbench/trust");
    renderStudio();

    expect(await screen.findByRole("heading", { name: "Autonomy and approvals" })).toBeInTheDocument();
    expect(screen.getByText("Safe analysis runs without approval spam.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Local Power User" }));

    await waitFor(() =>
      expect(fetchSpy).toHaveBeenCalledWith(
        expect.stringContaining("/api/trust"),
        expect.objectContaining({ method: "PATCH" }),
      ),
    );
  });

  it("shows Workbench artifact cards inside chat without changing message text", async () => {
    installFetchMock();
    const user = userEvent.setup();
    renderStudio();

    expect(await screen.findByText("Persistent chat keeps original messages.")).toBeInTheDocument();
    expect(screen.getAllByText("Coding request completed").length).toBeGreaterThan(0);
    await user.click(screen.getByRole("button", { name: /Coding request completed/i }));

    expect(await screen.findByRole("heading", { name: "README positioning update" })).toBeInTheDocument();
  });

  it("shows short first-run onboarding and persists skip", async () => {
    installFetchMock();
    const user = userEvent.setup();
    renderStudio({ onboarding: true });

    expect(await screen.findByRole("heading", { name: "Welcome to Hephaestus Studio" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Skip" }));

    expect(window.localStorage.getItem("heph:studio:onboardingComplete")).toBe("true");
  });

  it("opens Memory, edits a memory, and reviews suggestions", async () => {
    installFetchMock();
    const user = userEvent.setup();
    renderStudio();

    await screen.findByRole("heading", { name: "Validation-backed coding loop" });
    await user.click(screen.getByRole("button", { name: "Memory" }));

    expect(await screen.findByLabelText("Search memories")).toBeInTheDocument();
    const memoryRow = screen
      .getAllByText("Prefer validation-backed release evidence.")
      .map((element) => element.closest("button"))
      .find((element) => element);
    expect(memoryRow).not.toBeNull();
    await user.click(memoryRow as HTMLButtonElement);
    const detailRegion = await screen.findByRole("region", { name: "Memory list and detail" });
    const summaryInput = within(detailRegion).getByPlaceholderText("Short human-readable belief");
    await user.clear(summaryInput);
    await user.type(summaryInput, "Validate before release");
    await user.click(within(detailRegion).getByRole("button", { name: "Save changes" }));

    expect(await screen.findByText("Validate before release")).toBeInTheDocument();
    const suggestion = screen.getByText("It affects how future coding work is judged.").closest("article");
    expect(suggestion).not.toBeNull();
    await user.click(within(suggestion as HTMLElement).getByRole("button", { name: "Save" }));

    expect(
      await screen.findByRole("heading", { name: "Prefer validation-backed release evidence." })
    ).toBeInTheDocument();
  });

  it("opens Settings models, handles secret fields, usage, backup, and export", async () => {
    installFetchMock();
    const user = userEvent.setup();
    renderStudio();

    await screen.findByRole("heading", { name: "Validation-backed coding loop" });
    await user.click(screen.getByRole("button", { name: "Settings" }));
    await user.click(await screen.findByRole("button", { name: "Models" }));

    expect(await screen.findByText("Usage and Economy")).toBeInTheDocument();
    await user.type(screen.getByLabelText("Provider API key"), "sk-secret-test");
    await user.type(screen.getByLabelText("Model"), "gpt-test");
    await user.type(screen.getByLabelText("Base URL"), "fake://openai");
    await user.click(screen.getByRole("button", { name: "Save provider" }));

    expect(screen.queryByText("sk-secret-test")).not.toBeInTheDocument();
    expect(await screen.findByText("Solved without a model call")).toBeInTheDocument();
    await user.click(screen.getAllByRole("button", { name: "Test connection" }).at(-1)!);
    expect(await screen.findByText("Fake provider endpoint accepted for local validation.")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Data" }));
    await user.click(await screen.findByRole("button", { name: "Create backup" }));
    expect(await screen.findByText(/hephaestus-backup\.db/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Markdown conversation" }));
    expect(await screen.findByText("conversation.md")).toBeInTheDocument();
  });

  it("opens Advanced decision, Pareto, and QUBO views with table fallbacks", async () => {
    installFetchMock();
    const user = userEvent.setup();
    window.history.replaceState(null, "", "/advanced/decisions");
    renderStudio();

    expect(await screen.findByText("Choose validation-backed release path.")).toBeInTheDocument();
    await user.click(screen.getByText("Choose validation-backed release path."));
    expect(await screen.findByText("Validation evidence reduces release risk.")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Decisions" }));
    await user.click(await screen.findByText("Model route tradeoff"));
    expect(await screen.findByText("Accessible table")).toBeInTheDocument();
    expect(screen.getAllByText("Balanced").length).toBeGreaterThan(0);

    await user.click(screen.getByRole("button", { name: "Decisions" }));
    await user.click(await screen.findByText("Context packing"));
    expect(await screen.findByText("Pack context within a token budget.")).toBeInTheDocument();
    expect(screen.getByText("Mathematical details")).toBeInTheDocument();
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
    const studioResponse = handleStudioExperienceRequest(path, method, state, init);
    if (studioResponse) {
      return studioResponse;
    }
    const workbenchResponse = handleWorkbenchRequest(path, method, init);
    if (workbenchResponse) {
      return workbenchResponse;
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
        {
          workbench_artifacts: [
            {
              kind: "coding_request",
              id: "coding_1",
              title: "Coding request completed",
              status: "completed",
              files_changed: 2,
              validation: "3/3 passed",
              href: "/workbench/coding/coding_1",
            },
          ],
        },
      ),
    ],
    conv_2: [
      message("msg_3", "conv_2", "user", "Clarify positioning against Hermes exactly."),
      message("msg_4", "conv_2", "assistant", "Hermes remains complementary, not replaced."),
    ],
  };
  const memories: StudioMemoryDetail[] = [memoryDetail()];
  const providers: StudioProviderConfig[] = [localProvider()];
  const settings: StudioSettings = {
    active_policy_profile: "balanced",
    appearance: "system",
    browser_auto_open: true,
    debug_logging: false,
    density: "comfortable",
    deterministic_mode: true,
    developer_details: false,
    recent_repo_behavior: "remember",
    reduced_motion: false,
    startup_route: "/",
  };
  return { conversations, memories, messages, providers, settings };
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
  metadata: Record<string, unknown> = {},
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
    metadata,
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

function handleStudioExperienceRequest(
  path: string,
  method: string,
  state: ReturnType<typeof createState>,
  init?: RequestInit,
) {
  if (path === "/memories" && method === "GET") {
    return jsonResponse({
      memories: state.memories,
      total: state.memories.length,
      filters: {},
      suggestions_pending: 1,
    });
  }
  if (path === "/memories" && method === "POST") {
    const body = parseBody(init);
    const memory = memoryDetail({
      id: `mem_${state.memories.length + 1}`,
      content: String(body.content ?? ""),
      summary: String(body.summary ?? body.content ?? ""),
      type: String(body.type ?? "project_fact"),
      type_label: "Project fact",
      kind: body.kind === "regular" ? "regular" : "strategic",
      scope: body.scope === "repo" ? "repo" : "project",
    });
    state.memories.unshift(memory);
    return jsonResponse(memory, 201);
  }
  const memoryArchiveMatch = /^\/memories\/([^/]+)\/archive$/.exec(path);
  if (memoryArchiveMatch && method === "POST") {
    const memory = updateMemoryState(state, memoryArchiveMatch[1], { archived: true });
    return jsonResponse(memory);
  }
  const memoryRestoreMatch = /^\/memories\/([^/]+)\/restore$/.exec(path);
  if (memoryRestoreMatch && method === "POST") {
    const memory = updateMemoryState(state, memoryRestoreMatch[1], { archived: false });
    return jsonResponse(memory);
  }
  const memoryMatch = /^\/memories\/([^/]+)$/.exec(path);
  if (memoryMatch && method === "GET") {
    return jsonResponse(state.memories.find((memory) => memory.id === memoryMatch[1]));
  }
  if (memoryMatch && method === "PATCH") {
    const body = parseBody(init);
    const memory = updateMemoryState(state, memoryMatch[1], {
      content: String(body.content ?? state.memories[0].content),
      summary: String(body.summary ?? state.memories[0].summary),
    });
    return jsonResponse(memory);
  }
  if (memoryMatch && method === "DELETE") {
    state.memories = state.memories.filter((memory) => memory.id !== memoryMatch[1]);
    return new Response(null, { status: 204 });
  }
  if (path === "/memory-suggestions" && method === "GET") {
    return jsonResponse({
      suggestions: [
        {
          id: "suggestion_1",
          proposed_memory: "Prefer validation-backed release evidence.",
          why_it_may_matter: "It affects how future coding work is judged.",
          proposed_type: "preference",
          proposed_type_label: "Preference",
          proposed_scope: "project",
          proposed_stability: "long_term",
          source: "conversation",
          source_link: { label: "Validation-backed coding loop", href: "/conversations/conv_1" },
          confidence: 0.78,
          importance: 0.72,
          status: "suggested",
          created_at: now,
        },
      ],
      total: 1,
    });
  }
  const suggestionSaveMatch = /^\/memory-suggestions\/([^/]+)\/save$/.exec(path);
  if (suggestionSaveMatch && method === "POST") {
    const memory = memoryDetail({
      id: "mem_suggestion",
      summary: "Prefer validation-backed release evidence.",
      content: "Prefer validation-backed release evidence.",
      type: "preference",
      type_label: "Preference",
    });
    state.memories.unshift(memory);
    return jsonResponse(memory);
  }
  const suggestionIgnoreMatch = /^\/memory-suggestions\/([^/]+)\/ignore$/.exec(path);
  if (suggestionIgnoreMatch && method === "POST") {
    return new Response(null, { status: 204 });
  }
  if (path === "/settings" && method === "GET") {
    return jsonResponse(settingsResponse(state.settings));
  }
  if (path === "/settings" && method === "PATCH") {
    state.settings = { ...state.settings, ...parseBody(init) };
    return jsonResponse(settingsResponse(state.settings));
  }
  if (path === "/providers" && method === "GET") {
    return jsonResponse(providerList(state.providers));
  }
  if (path === "/providers" && method === "POST") {
    const body = parseBody(init);
    const provider = providerConfig({
      id: `provider_${state.providers.length + 1}`,
      base_url: String(body.base_url ?? ""),
      model: String(body.model ?? ""),
      name: String(body.name ?? "OpenAI-compatible"),
      provider_type: String(body.provider_type ?? "openai-compatible"),
    });
    state.providers.push(provider);
    return jsonResponse(provider, 201);
  }
  const providerTestMatch = /^\/providers\/([^/]+)\/test$/.exec(path);
  if (providerTestMatch && method === "POST") {
    return jsonResponse({
      id: providerTestMatch[1],
      status: providerTestMatch[1] === "local" ? "local_mode" : "configured",
      message: "Fake provider endpoint accepted for local validation.",
    });
  }
  const providerMatch = /^\/providers\/([^/]+)$/.exec(path);
  if (providerMatch && method === "PATCH") {
    state.providers = state.providers.map((provider) =>
      provider.id === providerMatch[1] ? { ...provider, default_for_conversation: true } : provider,
    );
    return jsonResponse(state.providers.find((provider) => provider.id === providerMatch[1]));
  }
  if (providerMatch && method === "DELETE") {
    state.providers = state.providers.filter((provider) => provider.id !== providerMatch[1]);
    return new Response(null, { status: 204 });
  }
  if (path === "/usage" && method === "GET") {
    return jsonResponse(usageResponse());
  }
  if (path === "/advanced/decisions" && method === "GET") {
    return jsonResponse(advancedList());
  }
  const decisionMatch = /^\/advanced\/decisions\/([^/]+)$/.exec(path);
  if (decisionMatch && method === "GET") {
    return jsonResponse(decisionDetail());
  }
  const paretoMatch = /^\/advanced\/pareto\/([^/]+)$/.exec(path);
  if (paretoMatch && method === "GET") {
    return jsonResponse(paretoDetail());
  }
  const quboMatch = /^\/advanced\/qubo\/([^/]+)$/.exec(path);
  if (quboMatch && method === "GET") {
    return jsonResponse(quboDetail());
  }
  const exportConversationMatch = /^\/export\/conversation\/([^/]+)$/.exec(path);
  if (exportConversationMatch && method === "POST") {
    const body = parseBody(init);
    const format = body.format === "json" ? "json" : "markdown";
    return jsonResponse({
      filename: `conversation.${format === "json" ? "json" : "md"}`,
      format,
      content: format === "json" ? "[{\"role\":\"user\"}]" : "## user\n\nPlease preserve exact chat history.",
      includes_secrets: false,
    });
  }
  if (path === "/export/memories" && method === "POST") {
    return jsonResponse({
      filename: "hephaestus-memories.json",
      format: "json",
      content: JSON.stringify(state.memories),
      includes_secrets: false,
    });
  }
  if (path === "/backup" && method === "POST") {
    return jsonResponse({
      path: "C:/tmp/hephaestus-backup.db",
      schema_version: 18,
      created_at: now,
      size_bytes: 4096,
    });
  }
  if (path === "/restore" && method === "POST") {
    return jsonResponse({
      restored: true,
      message: "Backup restored. Reload Studio to refresh open views.",
      schema_version: 18,
    });
  }
  return null;
}

function memoryDetail(overrides: Partial<StudioMemoryDetail> = {}): StudioMemoryDetail {
  return {
    id: overrides.id ?? "mem_1",
    kind: overrides.kind ?? "strategic",
    type: overrides.type ?? "project_fact",
    type_label: overrides.type_label ?? "Project fact",
    summary: overrides.summary ?? "Prefer validation-backed release evidence.",
    content: overrides.content ?? "Prefer validation-backed release evidence for coding work.",
    scope: overrides.scope ?? "project",
    project: overrides.project ?? "default",
    repo_profile_id: overrides.repo_profile_id ?? "repo_1",
    repo_name: overrides.repo_name ?? "Hephaestus",
    source: overrides.source ?? "manual",
    confidence: overrides.confidence ?? 0.82,
    importance: overrides.importance ?? 0.76,
    stability: overrides.stability ?? "long_term",
    created_at: overrides.created_at ?? now,
    updated_at: overrides.updated_at ?? now,
    archived: overrides.archived ?? false,
    linked_conversation_id: overrides.linked_conversation_id ?? "conv_1",
    conflict_count: overrides.conflict_count ?? 0,
    evidence: overrides.evidence ?? [],
    linked_conversation:
      overrides.linked_conversation ?? { label: "Validation-backed coding loop", href: "/conversations/conv_1" },
    linked_work: overrides.linked_work ?? [],
    conflict_warnings: overrides.conflict_warnings ?? [],
    history: overrides.history ?? [{ at: now, event: "Created", detail: "" }],
  };
}

function updateMemoryState(
  state: ReturnType<typeof createState>,
  memoryId: string,
  patch: Partial<StudioMemoryDetail>,
) {
  let updated = state.memories.find((memory) => memory.id === memoryId);
  if (!updated) {
    updated = memoryDetail({ id: memoryId });
  }
  updated = { ...updated, ...patch, updated_at: now };
  state.memories = [updated, ...state.memories.filter((memory) => memory.id !== memoryId)];
  return updated;
}

function localProvider(): StudioProviderConfig {
  return providerConfig({
    id: "local",
    provider_type: "local",
    name: "Local deterministic",
    model: "deterministic",
    status: "local_mode",
    status_label: "Local mode",
    default_for_conversation: true,
  });
}

function providerConfig(overrides: Partial<StudioProviderConfig>): StudioProviderConfig {
  return {
    id: overrides.id ?? "provider_1",
    provider_type: overrides.provider_type ?? "openai-compatible",
    name: overrides.name ?? "OpenAI-compatible",
    model: overrides.model ?? "gpt-test",
    base_url: overrides.base_url ?? "fake://openai",
    configured: overrides.configured ?? true,
    status: overrides.status ?? "configured",
    status_label: overrides.status_label ?? "Configured",
    status_detail: overrides.status_detail ?? "Configured",
    intended_roles: overrides.intended_roles ?? ["conversation"],
    context_window: overrides.context_window ?? 128000,
    input_cost_per_million: overrides.input_cost_per_million ?? 0.1,
    output_cost_per_million: overrides.output_cost_per_million ?? 0.2,
    default_for_conversation: overrides.default_for_conversation ?? false,
    created_at: overrides.created_at ?? now,
    updated_at: overrides.updated_at ?? now,
  };
}

function providerList(providers: StudioProviderConfig[]) {
  const local = providers.find((provider) => provider.id === "local") ?? localProvider();
  return {
    providers,
    default_provider_id: providers.find((provider) => provider.default_for_conversation)?.id ?? "local",
    local_mode: local,
    storage_note: "Provider secrets are stored locally and never returned by API responses.",
  };
}

function settingsResponse(settings: StudioSettings) {
  return {
    settings,
    database_path: "C:/tmp/hephaestus.db",
    schema_version: 18,
    local_api_url: "http://127.0.0.1:8741",
    static_assets_available: true,
  };
}

function usageResponse(): StudioUsageResponse {
  return {
    aggregate: {
      cost_per_validated_successful_coding_task: null,
      deterministic_operations: 4,
      estimated_cost: 0,
      estimated_model_calls_this_week: 1,
      provider_usage: { local: 4 },
    },
    estimate_note: "Token and cost values are estimates unless the provider returned usage.",
    events: [
      {
        id: "usage_1",
        task_type: "conversation",
        provider: "local",
        model: "deterministic",
        provider_model: "local/fake-balanced",
        message: "Solved without a model call",
        estimated_input_tokens: 120,
        estimated_output_tokens: 80,
        estimated_cost: 0,
        deterministic: true,
        context_trimmed: false,
        success: true,
        linked_conversation: { label: "Validation-backed coding loop", href: "/conversations/conv_1" },
        created_at: now,
      },
    ],
  };
}

function advancedList() {
  return {
    decisions: [
      {
        id: "trace_1",
        decision_type: "optimization",
        decision: "Choose validation-backed release path.",
        selected_option: "validation-first",
        confidence: 0.84,
        outcome: "outcome_1",
        repo: "Hephaestus",
        occurred_at: now,
        href: "/advanced/decisions/trace_1",
      },
    ],
    total: 1,
    pareto_frontiers: [
      { id: "frontier_1", title: "Model route tradeoff", kind: "pareto", created_at: now, linked_work: [] },
    ],
    qubo_problems: [
      { id: "qubo_1", title: "Context packing", kind: "qubo", created_at: now, linked_work: [] },
    ],
  };
}

function decisionDetail() {
  return {
    ...advancedList().decisions[0],
    alternatives: ["fast route: less validation"],
    reasons: ["Validation evidence reduces release risk."],
    assumptions: ["Repo validation commands are available."],
    evidence: ["confidence: 0.84"],
    linked_work: [{ label: "Outcome", href: "/workbench/outcomes/outcome_1" }],
    later_evidence_supported: "linked outcome available",
    developer_payload: { tags: ["release"] },
  };
}

function paretoDetail() {
  return {
    id: "frontier_1",
    title: "Model route tradeoff",
    objective_x: "quality",
    objective_y: "cost",
    selected_candidate_id: "candidate_a",
    preference_profile: "balanced",
    explanation: "These were the strongest non-dominated options.",
    tradeoffs: ["Higher quality costs more."],
    candidates: [
      {
        id: "candidate_a",
        label: "Balanced",
        x: 0.85,
        y: 0.2,
        is_frontier: true,
        selected: true,
        rationale: "Best balance.",
        objectives: { quality: 0.85, cost: 0.2 },
      },
      {
        id: "candidate_b",
        label: "Cheap",
        x: 0.7,
        y: 0.05,
        is_frontier: true,
        selected: false,
        rationale: "Lower cost.",
        objectives: { quality: 0.7, cost: 0.05 },
      },
    ],
    created_at: now,
  };
}

function quboDetail() {
  return {
    id: "qubo_1",
    purpose: "Pack context within a token budget.",
    problem_type: "context_packing",
    solver_used: "local exhaustive",
    selected_solution: "memory A",
    objective_value: -1.2,
    feasible: true,
    variables: [
      { id: "x_a", label: "memory A", selected: true },
      { id: "x_b", label: "memory B", selected: false },
    ],
    constraints: ["Stay within token budget."],
    comparison_with_heuristic: "Heuristic baseline selected memory B.",
    explanation: "This is a classical/local binary optimization formulation.",
    mathematical_details: { linear_terms: 2, quadratic_terms: 1 },
    created_at: now,
  };
}

function handleWorkbenchRequest(path: string, method: string, init?: RequestInit) {
  if (path === "/workbench/overview" && method === "GET") {
    return jsonResponse(workbenchOverview());
  }
  if (path === "/coding" && method === "GET") {
    return jsonResponse({ items: [codingSummary()], total: 1, filters: {} });
  }
  if ((path === "/coding/plan" || path === "/coding/propose") && method === "POST") {
    return jsonResponse(codingDetail());
  }
  const applyMatch = /^\/coding\/([^/]+)\/apply$/.exec(path);
  if (applyMatch && method === "POST") {
    return jsonResponse(codingDetail({ applied: true }));
  }
  const codingMatch = /^\/coding\/([^/]+)$/.exec(path);
  if (codingMatch && method === "GET") {
    return jsonResponse(codingDetail());
  }
  if (path === "/validation" && method === "GET") {
    return jsonResponse({ items: [validationSummary()], total: 1 });
  }
  if (path === "/validation/run" && method === "POST") {
    return jsonResponse(validationDetail());
  }
  const validationMatch = /^\/validation\/([^/]+)$/.exec(path);
  if (validationMatch && method === "GET") {
    return jsonResponse(validationDetail());
  }
  if (path === "/checkpoints" && method === "GET") {
    return jsonResponse([checkpointSummary()]);
  }
  const checkpointRestoreMatch = /^\/checkpoints\/([^/]+)\/restore$/.exec(path);
  if (checkpointRestoreMatch && method === "POST") {
    return jsonResponse(checkpointDetail({ restored: true }));
  }
  const checkpointMatch = /^\/checkpoints\/([^/]+)$/.exec(path);
  if (checkpointMatch && method === "GET") {
    return jsonResponse(checkpointDetail());
  }
  if (path === "/tools/actions" && method === "GET") {
    return jsonResponse([toolSummary()]);
  }
  const toolMatch = /^\/tools\/actions\/([^/]+)$/.exec(path);
  if (toolMatch && method === "GET") {
    return jsonResponse(toolDetail());
  }
  if (path === "/releases" && method === "GET") {
    return jsonResponse({ items: [releaseSummary()], total: 1 });
  }
  const releaseMatch = /^\/releases\/([^/]+)$/.exec(path);
  if (releaseMatch && method === "GET") {
    return jsonResponse(releaseDetail());
  }
  if (path === "/outcomes" && method === "GET") {
    return jsonResponse({ items: [outcomeSummary()], total: 1 });
  }
  const outcomeMatch = /^\/outcomes\/([^/]+)$/.exec(path);
  if (outcomeMatch && method === "GET") {
    return jsonResponse(outcomeDetail());
  }
  if (path === "/trust" && method === "GET") {
    return jsonResponse(trustSettings());
  }
  if (path === "/trust" && method === "PATCH") {
    const body = parseBody(init);
    return jsonResponse(trustSettings(typeof body.mode === "string" ? body.mode : "local_power_user"));
  }
  return null;
}

function status(value: string, label: string, tone: WorkbenchStatus["tone"]): WorkbenchStatus {
  return { value, label, tone };
}

function artifactSummary(
  overrides: Partial<WorkbenchArtifactSummary> & Pick<WorkbenchArtifactSummary, "id" | "kind" | "title" | "href">,
): WorkbenchArtifactSummary {
  return {
    id: overrides.id,
    kind: overrides.kind,
    title: overrides.title,
    status: overrides.status ?? status("completed", "Completed", "success"),
    repo: overrides.repo ?? "Hephaestus",
    repo_path: overrides.repo_path ?? repos[0].path,
    summary: overrides.summary ?? "2 files changed",
    files_changed: overrides.files_changed ?? 2,
    validation: overrides.validation ?? "3/3 passed",
    checkpoint: overrides.checkpoint ?? "available",
    conversation_id: overrides.conversation_id ?? "conv_1",
    created_at: overrides.created_at ?? now,
    updated_at: overrides.updated_at ?? now,
    href: overrides.href,
  };
}

function workbenchOverview(): WorkbenchOverview {
  return {
    active_coding_work: [
      artifactSummary({
        id: "coding_2",
        kind: "coding_request",
        title: "Fix provider fallback",
        status: status("validating", "Validation failed", "error"),
        validation: "2 tests failed",
        href: "/workbench/coding/coding_2",
      }),
    ],
    recent_completed_coding_work: [
      artifactSummary({
        id: "coding_1",
        kind: "coding_request",
        title: "README positioning update",
        href: "/workbench/coding/coding_1",
      }),
    ],
    recent_validation_runs: [
      artifactSummary({
        id: "validation_1",
        kind: "validation_result",
        title: "uv run pytest",
        href: "/workbench/validation/validation_1",
      }),
    ],
    failed_validation_requiring_attention: [
      artifactSummary({
        id: "validation_2",
        kind: "validation_result",
        title: "Provider fallback tests",
        status: status("failed", "Failed", "error"),
        validation: "1/3 passed",
        href: "/workbench/validation/validation_2",
      }),
    ],
    pending_decisions: [
      {
        id: "decision_1",
        kind: "patch",
        title: "Approve patch batch",
        description: "Apply the low-risk README patch and run validation.",
        repo: "Hephaestus",
        files: ["README.md"],
        risk: "low",
        rollback_available: true,
        external_side_effects: false,
        primary_label: "Apply patch",
        primary_endpoint: "/api/coding/change_1/apply",
        reject_label: "Cancel",
      },
    ],
    recent_checkpoints: [
      artifactSummary({
        id: "checkpoint_1",
        kind: "checkpoint",
        title: "Checkpoint checkpoint_1",
        href: "/workbench/checkpoints/checkpoint_1",
      }),
    ],
    latest_release_evidence: [
      artifactSummary({
        id: "release_1",
        kind: "release_plan",
        title: "Release readiness",
        href: "/workbench/releases/release_1",
      }),
    ],
  };
}

function codingSummary(overrides: Partial<CodingRequestSummary> = {}): CodingRequestSummary {
  return {
    id: overrides.id ?? "coding_1",
    title: overrides.title ?? "README positioning update",
    repo: overrides.repo ?? "Hephaestus",
    repo_path: overrides.repo_path ?? repos[0].path,
    scope: overrides.scope ?? "docs",
    risk: overrides.risk ?? "low",
    status: overrides.status ?? status("completed", "Completed", "success"),
    files_touched: overrides.files_touched ?? ["README.md", "docs/studio.md"],
    validation_result: overrides.validation_result ?? "3/3 passed",
    checkpoint_state: overrides.checkpoint_state ?? "available",
    conversation_id: overrides.conversation_id ?? "conv_1",
    conversation_title: overrides.conversation_title ?? "Validation-backed coding loop",
    created_at: overrides.created_at ?? now,
    updated_at: overrides.updated_at ?? now,
    href: overrides.href ?? "/workbench/coding/coding_1",
  };
}

function codingDetail({ applied = false }: { applied?: boolean } = {}): CodingDetailResponse {
  return {
    summary: codingSummary(),
    original_user_request: "Add the Workbench README positioning line.",
    linked_conversation: { label: "Validation-backed coding loop", href: "/conversations/conv_1" },
    policy_trust_profile: "Developer",
    plan: {
      summary: "Update product wording and validate docs.",
      steps: ["Edit README", "Update Studio docs", "Run validation"],
      expected_files: ["README.md", "docs/studio.md"],
      validation_strategy: ["uv run pytest", "pnpm test"],
      rollback_behavior: "Checkpoint restore is available before applying.",
      current_state: status("completed", "Completed", "success"),
    },
    changes: [
      {
        id: "change_1",
        status: status(applied ? "applied" : "proposed", applied ? "Applied" : "Proposed", applied ? "success" : "accent"),
        summary: "Talk in Chat. Inspect real work in Workbench.",
        files: ["README.md"],
        proposed: true,
        applied,
        diff: [
          "diff --git a/README.md b/README.md",
          "--- a/README.md",
          "+++ b/README.md",
          "@@ -1,2 +1,3 @@",
          " # Hephaestus",
          "+Talk in Chat.",
          "+Inspect real work in Workbench.",
        ].join("\n"),
        diff_stats: { additions: 2, deletions: 0, line_count: 7, large: false },
        review_result: "Low-risk documentation patch.",
        protected_files: [],
      },
    ],
    validation: [validationDetail()],
    result: "Patch applied successfully.",
    practical_next_step: "Review the linked validation evidence.",
    checkpoint_available: true,
    rollback_available: true,
    advanced_details: {
      decision_traces: ["trace_1"],
      tool_actions: ["tool_1"],
      outcomes: ["outcome_1"],
      learning_signals: ["signal_1"],
    },
  };
}

function validationSummary(overrides: Partial<ValidationSummary> = {}): ValidationSummary {
  return {
    id: overrides.id ?? "validation_1",
    repo: overrides.repo ?? "Hephaestus",
    repo_path: overrides.repo_path ?? repos[0].path,
    related_coding_request_id: overrides.related_coding_request_id ?? "coding_1",
    release_plan_id: overrides.release_plan_id ?? null,
    evidence_mode: overrides.evidence_mode ?? "real",
    total_commands: overrides.total_commands ?? 3,
    passed: overrides.passed ?? 3,
    failed: overrides.failed ?? 0,
    skipped: overrides.skipped ?? 0,
    duration_seconds: overrides.duration_seconds ?? 8.4,
    status: overrides.status ?? status("passed", "Passed", "success"),
    created_at: overrides.created_at ?? now,
    href: overrides.href ?? "/workbench/validation/validation_1",
  };
}

function validationDetail(): ValidationDetailResponse {
  return {
    summary: validationSummary(),
    commands: [
      {
        id: "command_1",
        command_type: "test",
        command: "uv run pytest",
        risk: "safe",
        status: status("passed", "Passed", "success"),
        exit_code: 0,
        duration_seconds: 8.4,
        output_summary: "All Python tests passed.",
        stdout: "162 passed",
        stderr: "",
        output_truncated: true,
        tool_action_id: "tool_1",
        outcome_id: "outcome_1",
        readiness_effect: 0.4,
      },
    ],
    linked_tool_actions: [{ label: "Ran uv run pytest", href: "/workbench/tools/tool_1" }],
    linked_outcomes: [{ label: "Validation passed", href: "/workbench/outcomes/outcome_1" }],
  };
}

function checkpointSummary(overrides: Partial<CheckpointSummary> = {}): CheckpointSummary {
  return {
    id: overrides.id ?? "checkpoint_1",
    created_at: overrides.created_at ?? now,
    associated_coding_request_id: overrides.associated_coding_request_id ?? "coding_1",
    files_covered: overrides.files_covered ?? ["README.md", "docs/studio.md"],
    availability: overrides.availability ?? "available",
    restored_at: overrides.restored_at ?? null,
    href: overrides.href ?? "/workbench/checkpoints/checkpoint_1",
  };
}

function checkpointDetail({ restored = false }: { restored?: boolean } = {}): CheckpointDetailResponse {
  return {
    summary: checkpointSummary({
      availability: restored ? "restored" : "available",
      restored_at: restored ? now : null,
    }),
    workspace_path: repos[0].path,
    files: [
      {
        path: "README.md",
        existed: true,
        original_hash: "abc123",
        protected: false,
        modified_at: now,
      },
      {
        path: "docs/studio.md",
        existed: true,
        original_hash: "def456",
        protected: false,
        modified_at: now,
      },
    ],
    related_patch_id: "change_1",
    validation_result: "3/3 passed",
    restore_warnings: [],
    restore_history: restored ? [{ label: "Restored checkpoint", href: "/workbench/tools/tool_2" }] : [],
  };
}

function toolSummary(overrides: Partial<ToolActionSummary> = {}): ToolActionSummary {
  return {
    id: overrides.id ?? "tool_1",
    action: overrides.action ?? "Ran uv run pytest",
    status: overrides.status ?? status("passed", "Passed", "success"),
    risk: overrides.risk ?? "safe",
    policy_decision: overrides.policy_decision ?? "allowed",
    result: overrides.result ?? "162 passed",
    related_coding_request_id: overrides.related_coding_request_id ?? "coding_1",
    related_validation_id: overrides.related_validation_id ?? "validation_1",
    created_at: overrides.created_at ?? now,
    href: overrides.href ?? "/workbench/tools/tool_1",
  };
}

function toolDetail(): ToolActionDetailResponse {
  return {
    summary: toolSummary(),
    workspace_path: repos[0].path,
    command: "uv run pytest",
    target_path: "",
    files_touched: [],
    stdout: "162 passed",
    stderr: "",
    exit_code: 0,
    checkpoint_id: "checkpoint_1",
    outcome_id: "outcome_1",
    observations: [],
  };
}

function releaseSummary(overrides: Partial<ReleaseSummary> = {}): ReleaseSummary {
  return {
    id: overrides.id ?? "release_1",
    repo: overrides.repo ?? "Hephaestus",
    repo_path: overrides.repo_path ?? repos[0].path,
    readiness: overrides.readiness ?? 0.92,
    evidence_mode: overrides.evidence_mode ?? "real",
    validation_status: overrides.validation_status ?? "passed",
    blockers: overrides.blockers ?? [],
    recommendation: overrides.recommendation ?? "Ready after review.",
    created_at: overrides.created_at ?? now,
    linked_work: overrides.linked_work ?? [{ label: "README positioning update", href: "/workbench/coding/coding_1" }],
    href: overrides.href ?? "/workbench/releases/release_1",
  };
}

function releaseDetail(): ReleaseDetailResponse {
  return {
    summary: releaseSummary(),
    practical_summary: "Release evidence is ready with real validation attached.",
    real_validation_evidence: [validationSummary()],
    blockers: [],
    next_actions: ["Review screenshots", "Cut release notes"],
    related_coding_requests: [codingSummary()],
    advanced_optimization_details: {
      pareto_frontier_ids: ["pareto_1"],
      qubo_problem_ids: ["qubo_1"],
    },
  };
}

function outcomeSummary(overrides: Partial<OutcomeSummary> = {}): OutcomeSummary {
  return {
    id: overrides.id ?? "outcome_1",
    what_happened: overrides.what_happened ?? "Patch applied successfully.",
    evidence: overrides.evidence ?? "All validation commands passed.",
    status: overrides.status ?? status("success", "Success", "success"),
    rollback: overrides.rollback ?? "Checkpoint available.",
    practical_lesson: overrides.practical_lesson ?? "Reuse this validation order for similar docs work.",
    related_task: overrides.related_task ?? "coding_1",
    observed_at: overrides.observed_at ?? now,
    href: overrides.href ?? "/workbench/outcomes/outcome_1",
  };
}

function outcomeDetail(): OutcomeDetailResponse {
  return {
    summary: outcomeSummary(),
    evidence_items: ["All validation commands passed."],
    reflections: ["Validation order was efficient."],
    what_hephaestus_learned: ["Reuse this validation order for similar docs work."],
    related_links: [{ label: "Coding request", href: "/workbench/coding/coding_1" }],
  };
}

function trustSettings(mode = "developer"): TrustSettingsResponse {
  return {
    mode: mode === "local_power_user" ? "local_power_user" : "developer",
    effective_policy_profile: mode === "local_power_user" ? "Local Power User" : "Developer",
    rules: [
      {
        key: "read_repo_files",
        label: "Read normal repo files",
        allowed: true,
        implemented: true,
        risk: "safe",
        hard_blocked: false,
      },
      {
        key: "apply_low_risk_documentation_patches",
        label: "Apply low-risk documentation patches",
        allowed: mode === "local_power_user",
        implemented: true,
        risk: "low",
        hard_blocked: false,
      },
      {
        key: "push_git_changes",
        label: "Push Git changes",
        allowed: false,
        implemented: false,
        risk: "external",
        hard_blocked: true,
      },
    ],
    effective_behavior: [
      "Safe analysis runs without approval spam.",
      "Medium-risk actions require meaningful confirmation.",
    ],
    hard_blocks: ["Destructive system-level actions remain blocked."],
    updated_at: now,
  };
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

function renderStudio({ onboarding = false }: { onboarding?: boolean } = {}) {
  if (!onboarding) {
    window.localStorage.setItem("heph:studio:onboardingComplete", "true");
  }
  return render(createElement(StudioApp));
}
