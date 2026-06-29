"use client";

import {
  Check,
  Copy,
  FileCheck2,
  FileCode2,
  GitPullRequest,
  RefreshCw,
  RotateCcw,
  ShieldCheck,
  type LucideIcon,
} from "lucide-react";
import { motion, useReducedMotion } from "framer-motion";
import ReactMarkdown, { type Components } from "react-markdown";
import rehypeHighlight from "rehype-highlight";
import remarkGfm from "remark-gfm";
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";

import { IconButton } from "@/components/icon-button";
import { isNearBottom, keyboardScrollTop } from "@/features/messages/scroll-policy";
import type { StudioMessage } from "@/lib/types";

interface MessageTimelineProps {
  messages: StudioMessage[];
  loading: boolean;
  pending: boolean;
  error: string | null;
  activeMessageId: string | null;
  conversationId: string | null;
  onOpenArtifact?: (href: string) => void;
  onRetry: () => void;
}

export function MessageTimeline({
  messages,
  loading,
  pending,
  error,
  activeMessageId,
  conversationId,
  onOpenArtifact,
  onRetry,
}: MessageTimelineProps) {
  const scrollerRef = useRef<HTMLDivElement | null>(null);
  const stackRef = useRef<HTMLDivElement | null>(null);
  const pinnedRef = useRef(true);
  const frameRef = useRef<number | null>(null);
  const [showJump, setShowJump] = useState(false);
  const contentSignature = useMemo(
    () => `${pending}:${messages.map((message) => `${message.id}:${message.content.length}`).join("|")}`,
    [messages, pending],
  );

  function scrollToLatest(behavior: ScrollBehavior = "auto") {
    const scroller = scrollerRef.current;
    if (!scroller) return;
    scroller.scrollTo({ top: scroller.scrollHeight, behavior });
    pinnedRef.current = true;
    setShowJump(false);
  }

  function schedulePinnedScroll() {
    if (!pinnedRef.current || frameRef.current !== null) return;
    frameRef.current = window.requestAnimationFrame(() => {
      frameRef.current = null;
      scrollToLatest("auto");
    });
  }

  useEffect(() => {
    if (!activeMessageId) {
      return;
    }
    const element = scrollerRef.current?.querySelector(
      `[data-message-id="${CSS.escape(activeMessageId)}"]`,
    );
    element?.scrollIntoView({ block: "center", behavior: "smooth" });
  }, [activeMessageId, messages]);

  useLayoutEffect(() => {
    if (!activeMessageId && conversationId && !loading) {
      scrollToLatest("auto");
    }
    // Opening a conversation always starts at the latest message.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [conversationId, loading]);

  useEffect(() => {
    if (activeMessageId) return;
    if (pinnedRef.current) schedulePinnedScroll();
    else setShowJump(true);
    // contentSignature intentionally represents streaming growth.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeMessageId, contentSignature]);

  useEffect(() => {
    const stack = stackRef.current;
    if (!stack || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(() => {
      if (pinnedRef.current) schedulePinnedScroll();
      else setShowJump(true);
    });
    observer.observe(stack);
    return () => observer.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(
    () => () => {
      if (frameRef.current !== null) window.cancelAnimationFrame(frameRef.current);
    },
    [],
  );

  if (loading) {
    return (
      <div className="timeline-frame">
      <div className="timeline-scroll" aria-label="Loading messages">
        <div className="message-skeleton" />
        <div className="message-skeleton assistant" />
        <div className="message-skeleton short" />
      </div>
      </div>
    );
  }

  return (
    <div className="timeline-frame">
    <div
      aria-label="Message transcript"
      className="timeline-scroll"
      onKeyDown={(event) => {
        const target = event.currentTarget;
        const next = keyboardScrollTop(event.key, target);
        if (next === null) return;
        event.preventDefault();
        target.scrollTo({ top: next, behavior: "auto" });
        pinnedRef.current = event.key === "End";
        setShowJump(event.key !== "End");
      }}
      onScroll={(event) => {
        const nearBottom = isNearBottom(event.currentTarget);
        pinnedRef.current = nearBottom;
        if (nearBottom) setShowJump(false);
      }}
      ref={scrollerRef}
      role="region"
      tabIndex={0}
    >
      {messages.length === 0 ? <EmptyConversation /> : null}
      <div className="message-stack" aria-live="polite" ref={stackRef}>
        {messages.map((message) => (
          <MessageBlock
            highlighted={message.id === activeMessageId}
            key={message.id}
            message={message}
            onOpenArtifact={onOpenArtifact}
          />
        ))}
        {pending ? <PendingMessage /> : null}
        {error ? <ErrorMessage message={error} onRetry={onRetry} /> : null}
      </div>
    </div>
    {showJump ? (
      <button className="jump-to-latest" onClick={() => scrollToLatest("smooth")} type="button">
        Jump to latest
      </button>
    ) : null}
    </div>
  );
}

function EmptyConversation() {
  return (
    <section className="empty-conversation" aria-label="Empty conversation">
      <div className="talos-quiet-mark" />
      <h1>What are we working on?</h1>
      <p>Start with a question, a repo, or a change you want to think through.</p>
      <div className="starter-actions" aria-label="Starter prompts">
        <span>Discuss an idea</span>
        <span>Open a repo</span>
        <span>Plan a change</span>
        <span>Review recent work</span>
      </div>
    </section>
  );
}

interface MessageBlockProps {
  message: StudioMessage;
  highlighted: boolean;
  onOpenArtifact?: (href: string) => void;
}

function MessageBlock({ message, highlighted, onOpenArtifact }: MessageBlockProps) {
  const [copied, setCopied] = useState(false);
  const reduceMotion = useReducedMotion();
  const isUser = message.role === "user";
  const artifacts = collectArtifacts(message.metadata);

  async function copyMessage() {
    await navigator.clipboard?.writeText(message.content);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1200);
  }

  return (
    <motion.article
      animate={{ opacity: 1, y: 0 }}
      className={`message-block ${isUser ? "user" : "assistant"} ${highlighted ? "is-highlighted" : ""}`}
      data-message-id={message.id}
      data-role={message.role}
      initial={reduceMotion ? false : { opacity: 0, y: 6 }}
      transition={reduceMotion ? { duration: 0 } : { duration: 0.16, ease: "easeOut" }}
    >
      <header>
        <span className="message-author">{isUser ? "You" : "Hephaestus"}</span>
        <time dateTime={message.created_at}>{formatMessageTime(message.created_at)}</time>
        <IconButton
          icon={copied ? Check : Copy}
          label="Copy message"
          onClick={() => void copyMessage()}
        />
      </header>
      <div className="markdown-body">
        <ReactMarkdown
          components={markdownComponents}
          rehypePlugins={[rehypeHighlight]}
          remarkPlugins={[remarkGfm]}
        >
          {message.content}
        </ReactMarkdown>
      </div>
      {artifacts.length > 0 ? (
        <div className="chat-artifact-stack" aria-label="Linked Workbench artifacts">
          {artifacts.map((artifact) => (
            <ChatArtifactCard
              artifact={artifact}
              key={`${artifact.kind}:${artifact.id}`}
              onOpen={onOpenArtifact}
            />
          ))}
        </div>
      ) : null}
    </motion.article>
  );
}

type ChatArtifactKind =
  | "coding_request"
  | "patch_proposal"
  | "validation_result"
  | "checkpoint"
  | "release_plan";

interface ChatArtifact {
  kind: ChatArtifactKind;
  id: string;
  title: string;
  summary: string | null;
  status: string | null;
  href: string;
  filesChanged: number | null;
  validation: string | null;
}

const chatArtifactKinds = new Set<ChatArtifactKind>([
  "coding_request",
  "patch_proposal",
  "validation_result",
  "checkpoint",
  "release_plan",
]);

function ChatArtifactCard({
  artifact,
  onOpen,
}: {
  artifact: ChatArtifact;
  onOpen?: (href: string) => void;
}) {
  const Icon = artifactIcon(artifact.kind);
  const facts = [
    artifact.filesChanged === null ? null : `${artifact.filesChanged} files changed`,
    artifact.validation,
    artifact.summary,
  ].filter((item): item is string => Boolean(item));

  return (
    <button
      className="chat-artifact-card"
      onClick={() => onOpen?.(artifact.href)}
      type="button"
    >
      <span className="chat-artifact-icon">
        <Icon aria-hidden="true" size={16} />
      </span>
      <span className="chat-artifact-copy">
        <span>{artifactLabel(artifact.kind, artifact.status)}</span>
        <strong>{artifact.title}</strong>
        {facts.length > 0 ? <small>{facts.slice(0, 2).join(" / ")}</small> : null}
      </span>
      <span className="chat-artifact-link">Open in Workbench</span>
    </button>
  );
}

function collectArtifacts(metadata: Record<string, unknown>): ChatArtifact[] {
  const raw = metadata.workbench_artifacts ?? metadata.artifacts;
  if (!Array.isArray(raw)) {
    return [];
  }
  return raw
    .map((item) => parseArtifact(item))
    .filter((item): item is ChatArtifact => item !== null);
}

function parseArtifact(value: unknown): ChatArtifact | null {
  if (!isRecord(value)) {
    return null;
  }
  const rawKind = stringValue(value.kind ?? value.type);
  if (!rawKind || !chatArtifactKinds.has(rawKind as ChatArtifactKind)) {
    return null;
  }
  const kind = rawKind as ChatArtifactKind;
  const id = stringValue(value.id ?? value.request_id ?? value.result_id ?? value.checkpoint_id);
  if (!id) {
    return null;
  }
  const href = stringValue(value.href) ?? hrefForArtifact(kind, id);
  const title = stringValue(value.title) ?? artifactDefaultTitle(kind);
  return {
    kind,
    id,
    title,
    href,
    summary: stringValue(value.summary),
    status: stringValue(value.status),
    filesChanged: numberValue(value.files_changed),
    validation: stringValue(value.validation),
  };
}

function artifactIcon(kind: ChatArtifactKind): LucideIcon {
  if (kind === "coding_request") return GitPullRequest;
  if (kind === "patch_proposal") return FileCode2;
  if (kind === "validation_result") return FileCheck2;
  if (kind === "checkpoint") return RotateCcw;
  return ShieldCheck;
}

function artifactLabel(kind: ChatArtifactKind, status: string | null) {
  const base = {
    coding_request: "Coding request",
    patch_proposal: "Patch proposal",
    validation_result: "Validation result",
    checkpoint: "Checkpoint",
    release_plan: "Release plan",
  }[kind];
  return status ? `${base} ${status.replaceAll("_", " ")}` : base;
}

function artifactDefaultTitle(kind: ChatArtifactKind) {
  return {
    coding_request: "Coding work",
    patch_proposal: "Patch proposal",
    validation_result: "Validation run",
    checkpoint: "Checkpoint",
    release_plan: "Release evidence",
  }[kind];
}

function hrefForArtifact(kind: ChatArtifactKind, id: string) {
  if (kind === "validation_result") return `/workbench/validation/${encodeURIComponent(id)}`;
  if (kind === "checkpoint") return `/workbench/checkpoints/${encodeURIComponent(id)}`;
  if (kind === "release_plan") return `/workbench/releases/${encodeURIComponent(id)}`;
  return `/workbench/coding/${encodeURIComponent(id)}`;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function stringValue(value: unknown) {
  return typeof value === "string" && value.trim() ? value : null;
}

function numberValue(value: unknown) {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function PendingMessage() {
  return (
    <article className="message-block assistant pending" aria-label="Hephaestus is responding">
      <header>
        <span className="message-author">Hephaestus</span>
      </header>
      <div className="typing-line">
        <i />
        <i />
        <i />
      </div>
    </article>
  );
}

function ErrorMessage({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <article className="message-error" role="alert">
      <div>
        <strong>Message failed</strong>
        <p>{message}</p>
      </div>
      <button onClick={onRetry} type="button">
        <RefreshCw aria-hidden="true" size={16} />
        Retry
      </button>
    </article>
  );
}

function CodeBlock({ code, language }: { code: string; language: string }) {
  const [copied, setCopied] = useState(false);

  async function copyCode() {
    await navigator.clipboard?.writeText(code);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1200);
  }

  return (
    <div className="code-block">
      <div className="code-block-top">
        <span>{language || "code"}</span>
        <button onClick={() => void copyCode()} type="button">
          {copied ? <Check aria-hidden="true" size={15} /> : <Copy aria-hidden="true" size={15} />}
          Copy
        </button>
      </div>
      <pre>
        <code className={language ? `language-${language}` : undefined}>{code}</code>
      </pre>
    </div>
  );
}

const markdownComponents = {
  code(props) {
    const { children, className } = props;
    const match = /language-(\w+)/.exec(className ?? "");
    const code = String(children).replace(/\n$/, "");
    if (!className) {
      return (
        <code className="inline-code">{children}</code>
      );
    }
    return <CodeBlock code={code} language={match?.[1] ?? ""} />;
  },
} satisfies Components;

function formatMessageTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  return new Intl.DateTimeFormat(undefined, {
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}
