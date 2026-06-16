"use client";

import { Menu, PanelRight, Search } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { IconButton } from "@/components/icon-button";
import { ContextDrawer } from "@/features/context/context-drawer";
import { ConversationSidebar } from "@/features/conversations/conversation-sidebar";
import { Composer } from "@/features/messages/composer";
import { MessageTimeline } from "@/features/messages/message-timeline";
import { SearchPanel } from "@/features/search/search-panel";
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
        const initialId =
          readConversationIdFromLocation() ??
          localStorage.getItem(LAST_CONVERSATION_KEY) ??
          list.conversations[0]?.id ??
          null;
        if (initialId) {
          await openConversation(initialId, {
            push: false,
            messageId: readMessageIdFromLocation(),
          });
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
      const conversationId = readConversationIdFromLocation();
      if (conversationId) {
        void openConversation(conversationId, {
          push: false,
          messageId: readMessageIdFromLocation(),
        });
      }
    }
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, [openConversation]);

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

  const headerTitle = conversationDetail?.conversation.title ?? "Hephaestus Studio";
  const providerLabel = provider?.active_label ?? config?.provider_label ?? "Local deterministic mode";

  return (
    <main className="studio-shell">
      <ConversationSidebar
        activeConversationId={activeConversationId}
        conversations={conversations}
        mobileOpen={mobileSidebarOpen}
        onArchiveConversation={(conversation) => void archiveConversation(conversation)}
        onCloseMobile={() => setMobileSidebarOpen(false)}
        onNewConversation={() => void createConversation()}
        onOpenConversation={(conversationId) => {
          void openConversation(conversationId);
          setMobileSidebarOpen(false);
        }}
        onOpenSearch={() => setSearchOpen(true)}
        onPinConversation={(conversation) => void pinConversation(conversation)}
        onQueryChange={setSidebarQuery}
        onRenameConversation={(conversationId, title) =>
          void renameConversation(conversationId, title)
        }
        onToggleArchived={() => setShowArchived((value) => !value)}
        query={sidebarQuery}
        showArchived={showArchived}
      />

      <section className="chat-column" aria-label="Message timeline">
        <header className="chat-header">
          <IconButton
            className="mobile-only"
            icon={Menu}
            label="Open conversations"
            onClick={() => setMobileSidebarOpen(true)}
          />
          <div>
            <p className="eyebrow">Persistent conversation</p>
            <h1>{headerTitle}</h1>
          </div>
          <div className="chat-header-actions">
            <IconButton icon={Search} label="Search" onClick={() => setSearchOpen(true)} />
            <IconButton
              className="mobile-only"
              icon={PanelRight}
              label="Open context"
              onClick={() => setMobileContextOpen(true)}
            />
          </div>
        </header>

        <MessageTimeline
          activeMessageId={activeMessageId}
          error={sendError}
          loading={bootLoading || messagesLoading}
          messages={messages}
          onRetry={() => void retryLastMessage()}
          onScrollPositionChange={(position) => {
            if (activeConversationId) {
              localStorage.setItem(`${SCROLL_PREFIX}${activeConversationId}`, String(position));
            }
          }}
          pending={pending}
          restoreScrollPosition={restoreScrollPosition}
        />

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
      </section>

      <ContextDrawer
        detail={conversationDetail}
        mobileOpen={mobileContextOpen}
        mode={mode}
        onCloseMobile={() => setMobileContextOpen(false)}
        policy={policy}
        provider={provider}
        repos={repos}
      />

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
    </main>
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

function readScrollPosition(conversationId: string) {
  const raw = localStorage.getItem(`${SCROLL_PREFIX}${conversationId}`);
  if (!raw) {
    return null;
  }
  const parsed = Number(raw);
  return Number.isFinite(parsed) ? parsed : null;
}
