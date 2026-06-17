"use client";

import { Menu, PanelRight, Search } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { IconButton } from "@/components/icon-button";
import { ContextDrawer } from "@/features/context/context-drawer";
import { ConversationSidebar } from "@/features/conversations/conversation-sidebar";
import { AdvancedApp, type AdvancedRoute } from "@/features/advanced/advanced-app";
import { MemoryApp, type MemoryRoute } from "@/features/memory/memory-app";
import { Composer } from "@/features/messages/composer";
import { MessageTimeline } from "@/features/messages/message-timeline";
import { Onboarding } from "@/features/onboarding/onboarding";
import { SearchPanel } from "@/features/search/search-panel";
import { SettingsApp, type SettingsRoute } from "@/features/settings/settings-app";
import { AppShell } from "@/features/studio/app-shell";
import { WorkbenchApp, type WorkbenchRoute } from "@/features/workbench/workbench-app";
import { StudioApiClient, StudioApiError } from "@/lib/api/client";
import { useKeyboardShortcuts } from "@/lib/shortcuts/use-keyboard-shortcuts";
import type {
  ConversationDetail,
  ConversationSummary,
  DeliberationMode,
  ModeOption,
  PolicyProfile,
  ProviderStatusResponse,
  RecentRepo,
  SearchResult,
  StudioConfig,
  StudioMessage,
} from "@/lib/types";

const LAST_CONVERSATION_KEY = "heph:studio:lastConversationId";
const SCROLL_PREFIX = "heph:studio:scroll:";
const APPEARANCE_KEY = "heph:studio:appearance";
const ONBOARDING_KEY = "heph:studio:onboardingComplete";

export type AppearancePreference = "system" | "light" | "dark";

type StudioRoute =
  | { section: "chat"; conversationId: string | null; messageId: string | null }
  | WorkbenchRoute
  | MemoryRoute
  | SettingsRoute
  | AdvancedRoute;

export function StudioApp() {
  const api = useMemo(() => new StudioApiClient(), []);
  const [config, setConfig] = useState<StudioConfig | null>(null);
  const [provider, setProvider] = useState<ProviderStatusResponse | null>(null);
  const [policy, setPolicy] = useState<PolicyProfile | null>(null);
  const [modes, setModes] = useState<ModeOption[]>([]);
  const [repos, setRepos] = useState<RecentRepo[]>([]);
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [conversationDetail, setConversationDetail] = useState<ConversationDetail | null>(null);
  const [messages, setMessages] = useState<StudioMessage[]>([]);
  const [mode, setMode] = useState<DeliberationMode>("balanced");
  const [repoProfileId, setRepoProfileId] = useState<string | null>(null);
  const [bootLoading, setBootLoading] = useState(true);
  const [messagesLoading, setMessagesLoading] = useState(false);
  const [pending, setPending] = useState(false);
  const [sendError, setSendError] = useState<string | null>(null);
  const [lastFailedMessage, setLastFailedMessage] = useState<string | null>(null);
  const [sidebarQuery, setSidebarQuery] = useState("");
  const [showArchived, setShowArchived] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [includeArchivedSearch, setIncludeArchivedSearch] = useState(false);
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [activeMessageId, setActiveMessageId] = useState<string | null>(null);
  const [restoreScrollPosition, setRestoreScrollPosition] = useState<number | null>(null);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [mobileContextOpen, setMobileContextOpen] = useState(false);
  const [contextCollapsed, setContextCollapsed] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [route, setRoute] = useState<StudioRoute>({
    section: "chat",
    conversationId: null,
    messageId: null,
  });
  const [appearance, setAppearance] = useState<AppearancePreference>(() =>
    readAppearancePreference(),
  );
  const [onboardingOpen, setOnboardingOpen] = useState(() => readOnboardingOpen());

  const refreshConversations = useCallback(
    async (query = sidebarQuery) => {
      const response = await api.conversations({ q: query, includeArchived: true, limit: 120 });
      setConversations(response.conversations);
      return response.conversations;
    },
    [api, sidebarQuery],
  );

  const openConversation = useCallback(
    async (
      conversationId: string,
      options: { push?: boolean; messageId?: string | null } = {},
    ) => {
      setMessagesLoading(true);
      setSendError(null);
      setActiveConversationId(conversationId);
      setActiveMessageId(options.messageId ?? null);
      setRestoreScrollPosition(readScrollPosition(conversationId));
      setRoute({ section: "chat", conversationId, messageId: options.messageId ?? null });
      localStorage.setItem(LAST_CONVERSATION_KEY, conversationId);
      if (options.push !== false) {
        const suffix = options.messageId ? `?message=${encodeURIComponent(options.messageId)}` : "";
        window.history.pushState(null, "", `/conversations/${conversationId}${suffix}`);
      }
      try {
        const [detail, nextMessages] = await Promise.all([
          api.conversation(conversationId),
          api.messages(conversationId),
        ]);
        setConversationDetail(detail);
        setMessages(nextMessages);
        setMode(detail.conversation.mode);
        setRepoProfileId(detail.conversation.repo_profile_id);
      } finally {
        setMessagesLoading(false);
      }
    },
    [api],
  );

  useEffect(() => {
    let cancelled = false;

    async function bootstrap() {
      try {
        const [nextConfig, nextProvider, nextPolicy, nextModes, nextRepos, list] =
          await Promise.all([
            api.config(),
            api.providerStatus(),
            api.activePolicy(),
            api.modes(),
            api.recentRepos(),
            api.conversations({ includeArchived: true, limit: 120 }),
          ]);
        if (cancelled) {
          return;
        }
        setConfig(nextConfig);
        setProvider(nextProvider);
        setPolicy(nextPolicy);
        setModes(nextModes);
        setRepos(nextRepos);
        setConversations(list.conversations);
        const initialRoute = readStudioRouteFromLocation();
        setRoute(initialRoute);
        if (initialRoute.section === "chat") {
          const initialId =
            initialRoute.conversationId ??
            localStorage.getItem(LAST_CONVERSATION_KEY) ??
            list.conversations[0]?.id ??
            null;
          if (initialId) {
            await openConversation(initialId, {
              push: false,
              messageId: initialRoute.messageId,
            });
          }
        }
        if (initialRoute.section === "workbench") {
          setContextCollapsed(true);
        }
        if (initialRoute.section !== "chat") {
          setContextCollapsed(true);
        }
      } finally {
        if (!cancelled) {
          setBootLoading(false);
        }
      }
    }

    void bootstrap();
    return () => {
      cancelled = true;
    };
  }, [api, openConversation]);

  useEffect(() => {
    function handlePopState() {
      const nextRoute = readStudioRouteFromLocation();
      if (nextRoute.section === "chat" && nextRoute.conversationId) {
        void openConversation(nextRoute.conversationId, {
          push: false,
          messageId: nextRoute.messageId,
        });
        return;
      }
      setRoute(nextRoute);
      if (nextRoute.section === "workbench") {
        setContextCollapsed(true);
      }
      if (nextRoute.section !== "chat") {
        setContextCollapsed(true);
      }
    }
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, [openConversation]);

  function navigateToHref(href: string) {
    if (href === "/" || href === "/conversations") {
      openChatHome();
      return;
    }
    if (href.startsWith("/conversations/")) {
      const url = new URL(href, window.location.origin);
      const id = decodeURIComponent(url.pathname.split("/")[2] ?? "");
      if (id) {
        void openConversation(id, {
          messageId: url.searchParams.get("message"),
        });
        setContextCollapsed(false);
      }
      return;
    }
    if (href.startsWith("/workbench")) {
      window.history.pushState(null, "", href);
      setRoute(parseWorkbenchRoute(href));
      setContextCollapsed(true);
      setMobileSidebarOpen(false);
      return;
    }
    if (href.startsWith("/memory")) {
      window.history.pushState(null, "", href);
      setRoute(parseMemoryRoute(href));
      setContextCollapsed(true);
      setMobileSidebarOpen(false);
      return;
    }
    if (href.startsWith("/settings")) {
      window.history.pushState(null, "", href);
      setRoute(parseSettingsRoute(href));
      setContextCollapsed(true);
      setMobileSidebarOpen(false);
      return;
    }
    if (href.startsWith("/advanced")) {
      window.history.pushState(null, "", href);
      setRoute(parseAdvancedRoute(href));
      setContextCollapsed(true);
      setMobileSidebarOpen(false);
      return;
    }
    window.history.pushState(null, "", href);
  }

  function openChatHome() {
    const target = activeConversationId ?? conversations[0]?.id ?? null;
    if (target) {
      void openConversation(target);
      setContextCollapsed(false);
    } else {
      window.history.pushState(null, "", "/");
      setRoute({ section: "chat", conversationId: null, messageId: null });
      setContextCollapsed(false);
    }
    setMobileSidebarOpen(false);
  }

  function openWorkbenchHome() {
    navigateToHref("/workbench");
  }

  function openMemoryHome() {
    navigateToHref("/memory");
  }

  function openSettingsHome() {
    navigateToHref("/settings");
  }

  function openAdvancedHome() {
    navigateToHref("/advanced/decisions");
  }

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void refreshConversations(sidebarQuery);
    }, 180);
    return () => window.clearTimeout(timer);
  }, [refreshConversations, sidebarQuery]);

  useEffect(() => {
    if (!searchOpen || !searchQuery.trim()) {
      setSearchResults([]);
      return;
    }
    const timer = window.setTimeout(async () => {
      setSearchLoading(true);
      try {
        const response = await api.search(searchQuery, includeArchivedSearch);
        setSearchResults(response.results);
      } finally {
        setSearchLoading(false);
      }
    }, 160);
    return () => window.clearTimeout(timer);
  }, [api, includeArchivedSearch, searchOpen, searchQuery]);

  useEffect(() => {
    localStorage.setItem(APPEARANCE_KEY, appearance);
    const root = document.documentElement;
    root.dataset.appearance = appearance;

    function applyResolvedTheme() {
      const resolved =
        appearance === "system" ? (prefersDarkMode() ? "dark" : "light") : appearance;
      root.dataset.theme = resolved;
    }

    applyResolvedTheme();
    if (appearance !== "system" || typeof window.matchMedia !== "function") {
      return;
    }
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    media.addEventListener("change", applyResolvedTheme);
    return () => media.removeEventListener("change", applyResolvedTheme);
  }, [appearance]);

  const createConversation = useCallback(async () => {
    const created = await api.createConversation({
      mode,
      repo_profile_id: repoProfileId,
    });
    setConversations((previous) => sortConversations([created, ...previous]));
    await openConversation(created.id);
    setMobileSidebarOpen(false);
  }, [api, mode, openConversation, repoProfileId]);

  useKeyboardShortcuts({
    onNewConversation: () => void createConversation(),
    onSearch: () => setSearchOpen(true),
    onEscape: () => {
      setSearchOpen(false);
      setMobileSidebarOpen(false);
      setMobileContextOpen(false);
    },
  });

  async function sendMessage(content: string) {
    setPending(true);
    setSendError(null);
    setLastFailedMessage(null);
    try {
      const conversationId =
        activeConversationId ??
        (
          await api.createConversation({
            mode,
            repo_profile_id: repoProfileId,
          })
        ).id;
      if (!activeConversationId) {
        setActiveConversationId(conversationId);
        window.history.pushState(null, "", `/conversations/${conversationId}`);
      }
      const response = await api.postMessage(conversationId, {
        content,
        mode,
        repo_profile_id: repoProfileId,
        provider: "auto",
      });
      setMessages(response.messages);
      setConversationDetail((previous) =>
        previous
          ? { ...previous, conversation: response.conversation }
          : {
              conversation: response.conversation,
              linked_artifact_count: 0,
              regular_memory_count: 0,
              strategic_memory_count: 0,
            },
      );
      setConversations((previous) => sortConversations([response.conversation, ...previous]));
      localStorage.setItem(LAST_CONVERSATION_KEY, conversationId);
      await refreshConversations();
    } catch (error) {
      const message =
        error instanceof StudioApiError ? error.message : "The message could not be sent.";
      setSendError(message);
      setLastFailedMessage(content);
    } finally {
      setPending(false);
    }
  }

  async function retryLastMessage() {
    if (lastFailedMessage) {
      await sendMessage(lastFailedMessage);
    }
  }

  async function updateMode(nextMode: DeliberationMode) {
    setMode(nextMode);
    if (!activeConversationId) {
      return;
    }
    const updated = await api.updateConversation(activeConversationId, { mode: nextMode });
    setConversations((previous) => replaceConversation(previous, updated));
  }

  async function updateRepo(nextRepoProfileId: string | null) {
    setRepoProfileId(nextRepoProfileId);
    if (!activeConversationId) {
      return;
    }
    const updated = await api.updateConversation(activeConversationId, {
      repo_profile_id: nextRepoProfileId,
    });
    setConversations((previous) => replaceConversation(previous, updated));
    setConversationDetail((previous) =>
      previous ? { ...previous, conversation: updated } : previous,
    );
  }

  async function renameConversation(conversationId: string, title: string) {
    const updated = await api.updateConversation(conversationId, { title });
    setConversations((previous) => replaceConversation(previous, updated));
    if (conversationId === activeConversationId) {
      setConversationDetail((previous) =>
        previous ? { ...previous, conversation: updated } : previous,
      );
    }
  }

  async function pinConversation(conversation: ConversationSummary) {
    const updated = await api.pinConversation(conversation.id, !conversation.is_pinned);
    setConversations((previous) => replaceConversation(previous, updated));
  }

  async function archiveConversation(conversation: ConversationSummary) {
    const updated = await api.archiveConversation(conversation.id, !conversation.is_archived);
    setConversations((previous) => replaceConversation(previous, updated));
  }

  function openSearchResult(result: SearchResult) {
    setSearchOpen(false);
    void openConversation(result.conversation_id, {
      messageId: result.message_id,
    });
  }

  const isChat = route.section === "chat";
  const headerTitle = conversationDetail?.conversation.title ?? "Hephaestus Studio";
  const providerLabel = provider?.active_label ?? config?.provider_label ?? "Local deterministic mode";
  const activeRepoName =
    conversationDetail?.conversation.repo_name ??
    repos.find((repo) => repo.id === repoProfileId)?.name ??
    null;

  return (
    <>
    <AppShell
      composer={
        isChat ? (
          <Composer
            disabled={pending || bootLoading}
            mode={mode}
            modes={modes}
            onModeChange={(nextMode) => void updateMode(nextMode)}
            onRepoChange={(nextRepoId) => void updateRepo(nextRepoId)}
            onSendMessage={(message) => void sendMessage(message)}
            providerLabel={providerLabel}
            repoProfileId={repoProfileId}
            repos={repos}
          />
        ) : null
      }
      context={
        <ContextDrawer
          collapsed={contextCollapsed}
          detail={conversationDetail}
          mobileOpen={mobileContextOpen}
          mode={mode}
          onCloseMobile={() => setMobileContextOpen(false)}
          onToggleCollapsed={() => setContextCollapsed((value) => !value)}
          policy={policy}
          provider={provider}
          repos={repos}
        />
      }
      contextCollapsed={isChat ? contextCollapsed : true}
      sidebarCollapsed={sidebarCollapsed}
      header={
        !isChat ? (
          <header className="chat-header">
            <IconButton
              className="mobile-only"
              icon={Menu}
              label="Open navigation"
              onClick={() => {
                setSidebarCollapsed(false);
                setMobileSidebarOpen(true);
              }}
            />
            <div className="chat-title">
              <p>{routeHeader(route).eyebrow}</p>
              <h1>{routeHeader(route).title}</h1>
              <span>{routeHeader(route).subtitle}</span>
            </div>
          </header>
        ) : (
          <header className="chat-header">
            <IconButton
              className="mobile-only"
              icon={Menu}
              label="Open conversations"
              onClick={() => {
                setSidebarCollapsed(false);
                setMobileSidebarOpen(true);
              }}
            />
            <div className="chat-title">
              <p>Conversation</p>
              <h1>{headerTitle}</h1>
              {activeRepoName ? <span>{activeRepoName}</span> : null}
            </div>
            <div className="chat-header-actions">
              <IconButton icon={Search} label="Search" onClick={() => setSearchOpen(true)} />
              <IconButton
                className="desktop-only"
                icon={PanelRight}
                label={contextCollapsed ? "Open context" : "Collapse context"}
                onClick={() => setContextCollapsed((value) => !value)}
              />
              <IconButton
                className="mobile-only"
                icon={PanelRight}
                label="Open context"
                onClick={() => {
                  setContextCollapsed(false);
                  setMobileContextOpen(true);
                }}
              />
            </div>
          </header>
        )
      }
      search={
        <SearchPanel
          includeArchived={includeArchivedSearch}
          loading={searchLoading}
          onClose={() => setSearchOpen(false)}
          onOpenResult={openSearchResult}
          onQueryChange={setSearchQuery}
          onToggleArchived={() => setIncludeArchivedSearch((value) => !value)}
          open={searchOpen}
          query={searchQuery}
          results={searchResults}
        />
      }
      sidebar={
        <ConversationSidebar
          activeConversationId={activeConversationId}
          activeSection={route.section}
          activeRepoName={activeRepoName}
          appearance={appearance}
          collapsed={sidebarCollapsed}
          conversations={conversations}
          mobileOpen={mobileSidebarOpen}
          onAppearanceChange={setAppearance}
          onArchiveConversation={(conversation) => void archiveConversation(conversation)}
          onCloseMobile={() => setMobileSidebarOpen(false)}
          onNewConversation={() => void createConversation()}
          onOpenChat={openChatHome}
          onOpenConversation={(conversationId) => {
            void openConversation(conversationId);
            setMobileSidebarOpen(false);
          }}
          onOpenSearch={() => setSearchOpen(true)}
          onOpenWorkbench={openWorkbenchHome}
          onOpenMemory={openMemoryHome}
          onOpenSettings={openSettingsHome}
          onOpenAdvanced={openAdvancedHome}
          onPinConversation={(conversation) => void pinConversation(conversation)}
          onQueryChange={setSidebarQuery}
          onRenameConversation={(conversationId, title) =>
            void renameConversation(conversationId, title)
          }
          onToggleCollapsed={() => setSidebarCollapsed((value) => !value)}
          onToggleArchived={() => setShowArchived((value) => !value)}
          providerLabel={providerLabel}
          query={sidebarQuery}
          showArchived={showArchived}
        />
      }
      timeline={
        route.section === "workbench" ? (
          <WorkbenchApp
            api={api}
            conversations={conversations}
            onNavigate={navigateToHref}
            repos={repos}
            route={route.section === "workbench" ? route : { section: "workbench", area: "overview", id: null }}
          />
        ) : route.section === "memory" ? (
          <MemoryApp api={api} onNavigate={navigateToHref} repos={repos} route={route} />
        ) : route.section === "settings" ? (
          <SettingsApp
            api={api}
            conversations={conversations}
            onAppearanceChange={setAppearance}
            onNavigate={navigateToHref}
            policy={policy}
            providerStatus={provider}
            route={route}
          />
        ) : route.section === "advanced" ? (
          <AdvancedApp api={api} onNavigate={navigateToHref} route={route} />
        ) : (
          <MessageTimeline
            activeMessageId={activeMessageId}
            error={sendError}
            loading={bootLoading || messagesLoading}
            messages={messages}
            onOpenArtifact={navigateToHref}
            onRetry={() => void retryLastMessage()}
            onScrollPositionChange={(position) => {
              if (activeConversationId) {
                localStorage.setItem(`${SCROLL_PREFIX}${activeConversationId}`, String(position));
              }
            }}
            pending={pending}
            restoreScrollPosition={restoreScrollPosition}
          />
        )
      }
    />
    {onboardingOpen ? (
      <Onboarding
        onComplete={() => {
          localStorage.setItem(ONBOARDING_KEY, "true");
          setOnboardingOpen(false);
        }}
        onNavigate={navigateToHref}
        repos={repos}
      />
    ) : null}
    </>
  );
}

function sortConversations(conversations: ConversationSummary[]) {
  const unique = new Map(conversations.map((conversation) => [conversation.id, conversation]));
  return [...unique.values()].sort((left, right) => {
    if (left.is_pinned !== right.is_pinned) {
      return left.is_pinned ? -1 : 1;
    }
    return new Date(right.updated_at).getTime() - new Date(left.updated_at).getTime();
  });
}

function replaceConversation(
  conversations: ConversationSummary[],
  conversation: ConversationSummary,
) {
  return sortConversations([
    conversation,
    ...conversations.filter((item) => item.id !== conversation.id),
  ]);
}

function readConversationIdFromLocation() {
  if (typeof window === "undefined") {
    return null;
  }
  const match = /^\/conversations\/([^/?#]+)/.exec(window.location.pathname);
  return match?.[1] ? decodeURIComponent(match[1]) : null;
}

function readMessageIdFromLocation() {
  if (typeof window === "undefined") {
    return null;
  }
  return new URLSearchParams(window.location.search).get("message");
}

function readStudioRouteFromLocation(): StudioRoute {
  if (typeof window === "undefined") {
    return { section: "chat", conversationId: null, messageId: null };
  }
  if (window.location.pathname.startsWith("/workbench")) {
    return parseWorkbenchRoute(window.location.href);
  }
  if (window.location.pathname.startsWith("/memory")) {
    return parseMemoryRoute(window.location.href);
  }
  if (window.location.pathname.startsWith("/settings")) {
    return parseSettingsRoute(window.location.href);
  }
  if (window.location.pathname.startsWith("/advanced")) {
    return parseAdvancedRoute(window.location.href);
  }
  return {
    section: "chat",
    conversationId: readConversationIdFromLocation(),
    messageId: readMessageIdFromLocation(),
  };
}

function parseMemoryRoute(href: string): MemoryRoute {
  const url = parseStudioUrl(href);
  const [, root, rawId] = url.pathname.split("/");
  if (root !== "memory") {
    return { section: "memory", id: null };
  }
  return { section: "memory", id: rawId ? decodeURIComponent(rawId) : null };
}

const settingsAreas = new Set<SettingsRoute["area"]>([
  "general",
  "models",
  "policy",
  "data",
  "appearance",
  "advanced",
]);

function parseSettingsRoute(href: string): SettingsRoute {
  const url = parseStudioUrl(href);
  const [, root, rawArea] = url.pathname.split("/");
  if (root !== "settings") {
    return { section: "settings", area: "general" };
  }
  const area =
    rawArea && settingsAreas.has(rawArea as SettingsRoute["area"])
      ? (rawArea as SettingsRoute["area"])
      : "general";
  return { section: "settings", area };
}

function parseAdvancedRoute(href: string): AdvancedRoute {
  const url = parseStudioUrl(href);
  const [, root, rawArea, rawId] = url.pathname.split("/");
  if (root !== "advanced") {
    return { section: "advanced", area: "decisions", id: null };
  }
  if (rawArea === "pareto") {
    return { section: "advanced", area: "pareto", id: rawId ? decodeURIComponent(rawId) : null };
  }
  if (rawArea === "qubo") {
    return { section: "advanced", area: "qubo", id: rawId ? decodeURIComponent(rawId) : null };
  }
  return {
    section: "advanced",
    area: "decisions",
    id: rawId ? decodeURIComponent(rawId) : null,
  };
}

function parseStudioUrl(href: string) {
  return typeof window === "undefined"
    ? new URL(href, "http://localhost")
    : new URL(href, window.location.origin);
}

const workbenchAreas = new Set<WorkbenchRoute["area"]>([
  "overview",
  "coding",
  "validation",
  "checkpoints",
  "tools",
  "releases",
  "outcomes",
  "trust",
]);

function parseWorkbenchRoute(href: string): WorkbenchRoute {
  const url = parseStudioUrl(href);
  const [, root, rawArea, rawId] = url.pathname.split("/");
  if (root !== "workbench") {
    return { section: "workbench", area: "overview", id: null };
  }
  const area = rawArea && workbenchAreas.has(rawArea as WorkbenchRoute["area"])
    ? (rawArea as WorkbenchRoute["area"])
    : "overview";
  return {
    section: "workbench",
    area,
    id: rawId ? decodeURIComponent(rawId) : null,
  };
}

function routeHeader(route: StudioRoute) {
  if (route.section === "workbench") {
    return {
      eyebrow: "Workbench",
      title: "Agent Workbench",
      subtitle: "Real work, validation, checkpoints, and approvals",
    };
  }
  if (route.section === "memory") {
    return {
      eyebrow: "Memory",
      title: "Memory",
      subtitle: "See, correct, and scope what Hephaestus remembers",
    };
  }
  if (route.section === "settings") {
    return {
      eyebrow: "Settings",
      title: "Settings",
      subtitle: "Models, trust, appearance, and local data controls",
    };
  }
  if (route.section === "advanced") {
    return {
      eyebrow: "Advanced",
      title: "Advanced Internals",
      subtitle: "Decision traces, Pareto tradeoffs, and QUBO formulations",
    };
  }
  return {
    eyebrow: "Conversation",
    title: "Hephaestus Studio",
    subtitle: "Chat remains the main workspace",
  };
}

function readScrollPosition(conversationId: string) {
  const raw = localStorage.getItem(`${SCROLL_PREFIX}${conversationId}`);
  if (!raw) {
    return null;
  }
  const parsed = Number(raw);
  return Number.isFinite(parsed) ? parsed : null;
}

function readAppearancePreference(): AppearancePreference {
  if (typeof window === "undefined") {
    return "system";
  }
  const stored = localStorage.getItem(APPEARANCE_KEY);
  return stored === "light" || stored === "dark" || stored === "system" ? stored : "system";
}

function readOnboardingOpen() {
  if (typeof window === "undefined") {
    return false;
  }
  return localStorage.getItem(ONBOARDING_KEY) !== "true";
}

function prefersDarkMode() {
  return typeof window.matchMedia === "function"
    ? window.matchMedia("(prefers-color-scheme: dark)").matches
    : true;
}
