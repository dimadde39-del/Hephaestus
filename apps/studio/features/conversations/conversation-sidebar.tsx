"use client";

import { Archive, Edit3, PanelLeftClose, Pin, PinOff, Plus, Search } from "lucide-react";
import Image from "next/image";
import { useMemo, useState } from "react";

import { IconButton } from "@/components/icon-button";
import type { ConversationSummary } from "@/lib/types";

interface ConversationSidebarProps {
  conversations: ConversationSummary[];
  activeConversationId: string | null;
  query: string;
  showArchived: boolean;
  mobileOpen: boolean;
  onQueryChange: (value: string) => void;
  onNewConversation: () => void;
  onOpenConversation: (conversationId: string) => void;
  onPinConversation: (conversation: ConversationSummary) => void;
  onArchiveConversation: (conversation: ConversationSummary) => void;
  onRenameConversation: (conversationId: string, title: string) => void;
  onOpenSearch: () => void;
  onToggleArchived: () => void;
  onCloseMobile: () => void;
}

export function ConversationSidebar({
  conversations,
  activeConversationId,
  query,
  showArchived,
  mobileOpen,
  onQueryChange,
  onNewConversation,
  onOpenConversation,
  onPinConversation,
  onArchiveConversation,
  onRenameConversation,
  onOpenSearch,
  onToggleArchived,
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

  return (
    <aside className={`conversation-sidebar ${mobileOpen ? "is-open" : ""}`} aria-label="Conversations">
      <div className="sidebar-top">
        <div className="studio-brand">
          <Image alt="" height={30} priority src="/talos-mark.svg" width={30} />
          <div>
            <span>Hephaestus</span>
            <strong>Studio</strong>
          </div>
        </div>
        <IconButton
          className="mobile-only"
          icon={PanelLeftClose}
          label="Close conversations"
          onClick={onCloseMobile}
        />
      </div>

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
          placeholder="Search conversations"
          value={query}
        />
      </label>

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
        <button className="archive-toggle" onClick={onToggleArchived} type="button">
          <Archive aria-hidden="true" size={15} />
          {showArchived ? "Hide archived" : "Show archived"}
          <span>{archived.length}</span>
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
    </aside>
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
    <article className={`conversation-row ${active ? "is-active" : ""}`} role="listitem">
      <button
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
          {conversation.repo_name ? <b>{conversation.repo_name}</b> : null}
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
