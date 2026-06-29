"use client";

import { Cpu, FolderGit2, Gauge, Plus, SendHorizontal } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import type { DeliberationMode, ModeOption, RecentRepo } from "@/lib/types";

interface ComposerProps {
  workflow: "chat" | "plan" | "build";
  mode: DeliberationMode;
  modes: ModeOption[];
  repoProfileId: string | null;
  repos: RecentRepo[];
  providerLabel: string;
  disabled: boolean;
  onModeChange: (mode: DeliberationMode) => void;
  onRepoChange: (repoProfileId: string | null) => void;
  onSendMessage: (message: string) => void;
  onWorkflowChange: (workflow: "chat" | "plan" | "build") => void;
}

export function Composer({
  workflow,
  mode,
  modes,
  repoProfileId,
  repos,
  providerLabel,
  disabled,
  onModeChange,
  onRepoChange,
  onSendMessage,
  onWorkflowChange,
}: ComposerProps) {
  const [draft, setDraft] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => {
    textareaRef.current?.focus();
  }, []);

  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) {
      return;
    }
    textarea.style.height = "auto";
    textarea.style.height = `${Math.min(textarea.scrollHeight, 220)}px`;
  }, [draft]);

  function send() {
    if (!draft.trim() || disabled) {
      return;
    }
    onSendMessage(draft);
    setDraft("");
  }

  return (
    <form
      aria-busy={disabled}
      className={`composer ${disabled ? "is-disabled" : ""}`}
      onSubmit={(event) => {
        event.preventDefault();
        send();
      }}
    >
      <div className="composer-panel">
        <div className="composer-controls">
          <label>
            <Gauge aria-hidden="true" size={15} />
            <span>Action</span>
            <select
              aria-label="Workflow mode"
              disabled={disabled}
              onChange={(event) =>
                onWorkflowChange(event.target.value as "chat" | "plan" | "build")
              }
              value={workflow}
            >
              <option value="chat">Chat</option>
              <option value="plan">Plan</option>
              <option value="build">Build</option>
            </select>
          </label>
          <label>
            <Gauge aria-hidden="true" size={15} />
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
            <FolderGit2 aria-hidden="true" size={15} />
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
            <Cpu aria-hidden="true" size={14} />
            {providerLabel}
          </div>
          {workflow !== "chat" ? (
            <div className="provider-pill" aria-label="Coding budget">
              3 calls · 4096 tokens · $0.05
            </div>
          ) : null}
        </div>

        <div className="composer-input-row">
          <button
            aria-label="Add context"
            className="composer-tool-button"
            disabled
            title="Reserved for future actions"
            type="button"
          >
            <Plus aria-hidden="true" size={18} />
          </button>
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
            rows={1}
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
        <div className="composer-footer" aria-label="Composer behavior">
          <span className="composer-key-hint" title="Enter sends; Shift Enter adds a line">
            <kbd>Enter</kbd>
            <kbd>Shift</kbd>
            <kbd>Enter</kbd>
          </span>
        </div>
      </div>
    </form>
  );
}
