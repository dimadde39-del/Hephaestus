"use client";

import {
  Archive,
  Edit3,
  Monitor,
  Moon,
  PanelLeftClose,
  PanelLeftOpen,
  Pin,
  PinOff,
  Plus,
  Search,
  Settings,
  Sun,
} from "lucide-react";
import { useMemo, useState } from "react";

import { IconButton } from "@/components/icon-button";
import { WorkspaceSwitcher } from "@/features/studio/workspace-switcher";
import type { AppearancePreference } from "@/features/studio/studio-app";
import type { ConversationSummary } from "@/lib/types";

interface ConversationSidebarProps {
  conversations: ConversationSummary[];
  activeConversationId: string | null;
  activeRepoName: string | null;
  query: string;
  showArchived: boolean;
  mobileOpen: boolean;
  collapsed: boolean;
  appearance: AppearancePreference;
  providerLabel: string;
  onQueryChange: (value: string) => void;
  onNewConversation: () => void;
  onOpenConversation: (conversationId: string) => void;
  onPinConversation: (conversation: ConversationSummary) => void;
  onArchiveConversation: (conversation: ConversationSummary) => void;
  onRenameConversation: (conversationId: string, title: string) => void;
  onOpenSearch: () => void;
  onToggleArchived: () => void;
  onToggleCollapsed: () => void;
  onAppearanceChange: (appearance: AppearancePreference) => void;
  onCloseMobile: () => void;
}

export function ConversationSidebar({
  conversations,
  activeConversationId,
  activeRepoName,
  query,
  showArchived,
  mobileOpen,
  collapsed,
  appearance,
  providerLabel,
  onQueryChange,
  onNewConversation,
  onOpenConversation,
  onPinConversation,
  onArchiveConversation,
  onRenameConversation,
  onOpenSearch,
  onToggleArchived,
  onToggleCollapsed,
  onAppearanceChange,
  onCloseMobile,
}: ConversationSidebarProps) {
  const pinned = useMemo(
    () =>
      conversations.filter(
        (conversation) => conversation.is_pinned && !conversation.is_archived,
      ),
    [conversations],
  );
  const recent = useMemo(
    () =>
      conversations.filter(
        (conversation) => !conversation.is_pinned && !conversation.is_archived,
      ),
    [conversations],
  );
  const archived = useMemo(
    () => conversations.filter((conversation) => conversation.is_archived),
    [conversations],
  );

  if (collapsed) {
    return (
      <aside className="conversation-sidebar is-collapsed" aria-label="Conversations">
        <div className="sidebar-top">
          <WorkspaceSwitcher collapsed providerLabel={providerLabel} repoName={activeRepoName} />
          <IconButton
            className="desktop-only"
            icon={PanelLeftOpen}
            label="Expand sidebar"
            onClick={onToggleCollapsed}
          />
        </div>
        <nav className="sidebar-rail-actions" aria-label="Primary">
          <IconButton icon={Plus} label="New chat" onClick={onNewConversation} />
          <IconButton icon={Search} label="Search" onClick={onOpenSearch} />
        </nav>
      </aside>
    );
  }

  return (
    <aside
      className={`conversation-sidebar ${mobileOpen ? "is-open" : ""}`}
      aria-label="Conversations"
    >
      <div className="sidebar-top">
        <WorkspaceSwitcher providerLabel={providerLabel} repoName={activeRepoName} />
        <IconButton
          className="desktop-only"
          icon={PanelLeftClose}
          label="Collapse sidebar"
          onClick={onToggleCollapsed}
        />
        <IconButton
          className="mobile-only"
          icon={PanelLeftClose}
          label="Close conversations"
          onClick={onCloseMobile}
        />
      </div>

      <div className="sidebar-actions">
        <button className="new-chat-button" onClick={onNewConversation} type="button">
          <Plus aria-hidden="true" size={17} />
          New chat
        </button>

        <label className="sidebar-search">
          <Search aria-hidden="true" size={16} />
          <input
            aria-label="Search conversations"
            onChange={(event) => onQueryChange(event.target.value)}
            onFocus={onOpenSearch}
            placeholder="Search history"
            value={query}
          />
        </label>
      </div>

      <div className="conversation-list" role="list">
        <ConversationSection
          activeConversationId={activeConversationId}
          conversations={pinned}
          emptyLabel="No pinned chats"
          onArchiveConversation={onArchiveConversation}
          onOpenConversation={onOpenConversation}
          onPinConversation={onPinConversation}
          onRenameConversation={onRenameConversation}
          title="Pinned"
        />
        <ConversationSection
          activeConversationId={activeConversationId}
          conversations={recent}
          emptyLabel="No recent chats"
          onArchiveConversation={onArchiveConversation}
          onOpenConversation={onOpenConversation}
          onPinConversation={onPinConversation}
          onRenameConversation={onRenameConversation}
          title="Recent"
        />
        <button
          aria-label={showArchived ? "Hide archived conversations" : "Show archived conversations"}
          className={`archive-toggle ${showArchived ? "is-active" : ""}`}
          onClick={onToggleArchived}
          type="button"
        >
          <span>
            <Archive aria-hidden="true" size={15} />
            Archived
          </span>
          <strong>{archived.length}</strong>
        </button>
        {showArchived ? (
          <ConversationSection
            activeConversationId={activeConversationId}
            conversations={archived}
            emptyLabel="No archived chats"
            onArchiveConversation={onArchiveConversation}
            onOpenConversation={onOpenConversation}
            onPinConversation={onPinConversation}
            onRenameConversation={onRenameConversation}
            title="Archived"
          />
        ) : null}
      </div>
      <section className="sidebar-settings" aria-label="Settings">
        <div className="settings-title">
          <Settings aria-hidden="true" size={15} />
          <span>Settings</span>
        </div>
        <div className="appearance-control" aria-label="Appearance">
          <AppearanceButton
            active={appearance === "system"}
            icon={Monitor}
            label="System"
            onClick={() => onAppearanceChange("system")}
          />
          <AppearanceButton
            active={appearance === "light"}
            icon={Sun}
            label="Light"
            onClick={() => onAppearanceChange("light")}
          />
          <AppearanceButton
            active={appearance === "dark"}
            icon={Moon}
            label="Dark"
            onClick={() => onAppearanceChange("dark")}
          />
        </div>
      </section>
    </aside>
  );
}

interface AppearanceButtonProps {
  active: boolean;
  icon: typeof Monitor;
  label: string;
  onClick: () => void;
}

function AppearanceButton({ active, icon: Icon, label, onClick }: AppearanceButtonProps) {
  return (
    <button
      aria-pressed={active}
      className={active ? "is-active" : ""}
      onClick={onClick}
      type="button"
    >
      <Icon aria-hidden="true" size={14} />
      {label}
    </button>
  );
}

interface ConversationSectionProps {
  title: string;
  emptyLabel: string;
  conversations: ConversationSummary[];
  activeConversationId: string | null;
  onOpenConversation: (conversationId: string) => void;
  onPinConversation: (conversation: ConversationSummary) => void;
  onArchiveConversation: (conversation: ConversationSummary) => void;
  onRenameConversation: (conversationId: string, title: string) => void;
}

function ConversationSection({
  title,
  emptyLabel,
  conversations,
  activeConversationId,
  onOpenConversation,
  onPinConversation,
  onArchiveConversation,
  onRenameConversation,
}: ConversationSectionProps) {
  return (
    <section className="conversation-section" aria-label={title}>
      <h2>{title}</h2>
      {conversations.length === 0 ? <p className="section-empty">{emptyLabel}</p> : null}
      {conversations.map((conversation) => (
        <ConversationRow
          active={conversation.id === activeConversationId}
          conversation={conversation}
          key={conversation.id}
          onArchiveConversation={onArchiveConversation}
          onOpenConversation={onOpenConversation}
          onPinConversation={onPinConversation}
          onRenameConversation={onRenameConversation}
        />
      ))}
    </section>
  );
}

interface ConversationRowProps {
  conversation: ConversationSummary;
  active: boolean;
  onOpenConversation: (conversationId: string) => void;
  onPinConversation: (conversation: ConversationSummary) => void;
  onArchiveConversation: (conversation: ConversationSummary) => void;
  onRenameConversation: (conversationId: string, title: string) => void;
}

function ConversationRow({
  conversation,
  active,
  onOpenConversation,
  onPinConversation,
  onArchiveConversation,
  onRenameConversation,
}: ConversationRowProps) {
  const [renaming, setRenaming] = useState(false);
  const [draftTitle, setDraftTitle] = useState(conversation.title);

  function submitRename() {
    const nextTitle = draftTitle.trim();
    if (nextTitle && nextTitle !== conversation.title) {
      onRenameConversation(conversation.id, nextTitle);
    }
    setRenaming(false);
  }

  return (
    <article
      className={`conversation-row ${active ? "is-active" : ""}`}
      role="listitem"
    >
      <button
        aria-current={active ? "page" : undefined}
        className="conversation-row-main"
        onClick={() => onOpenConversation(conversation.id)}
        type="button"
      >
        {renaming ? (
          <input
            aria-label="Conversation title"
            autoFocus
            onBlur={submitRename}
            onChange={(event) => setDraftTitle(event.target.value)}
            onClick={(event) => event.stopPropagation()}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.preventDefault();
                submitRename();
              }
              if (event.key === "Escape") {
                event.preventDefault();
                setDraftTitle(conversation.title);
                setRenaming(false);
              }
            }}
            value={draftTitle}
          />
        ) : (
          <span className="conversation-title">{conversation.title}</span>
        )}
        <span className="conversation-meta">
          <time dateTime={conversation.updated_at}>{formatConversationTime(conversation.updated_at)}</time>
        </span>
        {conversation.last_message_preview ? (
          <span className="conversation-preview">{conversation.last_message_preview}</span>
        ) : null}
      </button>
      <div className="conversation-row-actions">
        <IconButton
          active={conversation.is_pinned}
          icon={conversation.is_pinned ? PinOff : Pin}
          label={conversation.is_pinned ? "Unpin conversation" : "Pin conversation"}
          onClick={() => onPinConversation(conversation)}
        />
        <IconButton
          icon={Edit3}
          label="Rename conversation"
          onClick={() => setRenaming(true)}
        />
        <IconButton
          icon={Archive}
          label={conversation.is_archived ? "Restore conversation" : "Archive conversation"}
          onClick={() => onArchiveConversation(conversation)}
        />
      </div>
    </article>
  );
}

function formatConversationTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}
