"use client";

import { SendHorizontal } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import type { DeliberationMode, ModeOption, RecentRepo } from "@/lib/types";

interface ComposerProps {
  mode: DeliberationMode;
  modes: ModeOption[];
  repoProfileId: string | null;
  repos: RecentRepo[];
  providerLabel: string;
  disabled: boolean;
  onModeChange: (mode: DeliberationMode) => void;
  onRepoChange: (repoProfileId: string | null) => void;
  onSendMessage: (message: string) => void;
}

export function Composer({
  mode,
  modes,
  repoProfileId,
  repos,
  providerLabel,
  disabled,
  onModeChange,
  onRepoChange,
  onSendMessage,
}: ComposerProps) {
  const [draft, setDraft] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => {
    textareaRef.current?.focus();
  }, []);

  function send() {
    if (!draft.trim() || disabled) {
      return;
    }
    onSendMessage(draft);
    setDraft("");
  }

  return (
    <form
      className="composer"
      onSubmit={(event) => {
        event.preventDefault();
        send();
      }}
    >
      <div className="composer-controls">
        <label>
          <span>Mode</span>
          <select
            aria-label="Conversation mode"
            disabled={disabled}
            onChange={(event) => onModeChange(event.target.value as DeliberationMode)}
            value={mode}
          >
            {modes.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>Repo</span>
          <select
            aria-label="Repository context"
            disabled={disabled}
            onChange={(event) => onRepoChange(event.target.value || null)}
            value={repoProfileId ?? ""}
          >
            <option value="">No repo</option>
            {repos.map((repo) => (
              <option key={repo.id} value={repo.id}>
                {repo.name}
              </option>
            ))}
          </select>
        </label>
        <div className="provider-pill" aria-label={`Provider: ${providerLabel}`}>
          {providerLabel}
        </div>
      </div>
      <div className="composer-input-row">
        <textarea
          aria-label="Message Hephaestus"
          disabled={disabled}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              send();
            }
          }}
          placeholder="Message Hephaestus..."
          ref={textareaRef}
          rows={3}
          value={draft}
        />
        <button
          aria-label="Send message"
          className="send-button"
          disabled={disabled || !draft.trim()}
          type="submit"
        >
          <SendHorizontal aria-hidden="true" size={19} />
        </button>
      </div>
    </form>
  );
}
