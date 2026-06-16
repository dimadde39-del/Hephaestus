"use client";

import { Archive, MessageSquareText, Search, X } from "lucide-react";
import { useEffect, useRef } from "react";

import { IconButton } from "@/components/icon-button";
import type { SearchResult } from "@/lib/types";

interface SearchPanelProps {
  open: boolean;
  query: string;
  includeArchived: boolean;
  loading: boolean;
  results: SearchResult[];
  onQueryChange: (query: string) => void;
  onToggleArchived: () => void;
  onOpenResult: (result: SearchResult) => void;
  onClose: () => void;
}

export function SearchPanel({
  open,
  query,
  includeArchived,
  loading,
  results,
  onQueryChange,
  onToggleArchived,
  onOpenResult,
  onClose,
}: SearchPanelProps) {
  const inputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    if (open) {
      window.setTimeout(() => inputRef.current?.focus(), 20);
    }
  }, [open]);

  if (!open) {
    return null;
  }

  return (
    <div className="search-backdrop" role="presentation">
      <section aria-label="Search conversations" className="search-panel" role="dialog">
        <div className="search-panel-input">
          <Search aria-hidden="true" size={18} />
          <input
            aria-label="Search past conversations and messages"
            onChange={(event) => onQueryChange(event.target.value)}
            placeholder="Search titles, user messages, and agent replies"
            ref={inputRef}
            value={query}
          />
          <IconButton icon={X} label="Close search" onClick={onClose} />
        </div>
        <button
          className={`archived-filter ${includeArchived ? "is-active" : ""}`}
          onClick={onToggleArchived}
          type="button"
        >
          <Archive aria-hidden="true" size={15} />
          Include archived
        </button>
        <div className="search-results">
          {loading ? <p className="muted-line">Searching local history...</p> : null}
          {!loading && query.trim() && results.length === 0 ? (
            <p className="muted-line">No matches.</p>
          ) : null}
          {results.map((result) => (
            <button
              className="search-result"
              key={`${result.conversation_id}:${result.message_id ?? result.match_type}`}
              onClick={() => onOpenResult(result)}
              type="button"
            >
              <MessageSquareText aria-hidden="true" size={17} />
              <span>
                <strong>{result.conversation_title}</strong>
                <small>
                  {result.match_type}
                  {result.role ? ` · ${result.role}` : ""}
                  {result.is_archived ? " · archived" : ""}
                </small>
                <em>{result.snippet}</em>
              </span>
            </button>
          ))}
        </div>
      </section>
    </div>
  );
}
