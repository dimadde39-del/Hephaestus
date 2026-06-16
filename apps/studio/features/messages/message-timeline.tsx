"use client";

import { Check, Copy, RefreshCw } from "lucide-react";
import { motion, useReducedMotion } from "framer-motion";
import ReactMarkdown, { type Components } from "react-markdown";
import rehypeHighlight from "rehype-highlight";
import remarkGfm from "remark-gfm";
import { useEffect, useRef, useState } from "react";

import { IconButton } from "@/components/icon-button";
import type { StudioMessage } from "@/lib/types";

interface MessageTimelineProps {
  messages: StudioMessage[];
  loading: boolean;
  pending: boolean;
  error: string | null;
  activeMessageId: string | null;
  restoreScrollPosition: number | null;
  onRetry: () => void;
  onScrollPositionChange: (position: number) => void;
}

export function MessageTimeline({
  messages,
  loading,
  pending,
  error,
  activeMessageId,
  restoreScrollPosition,
  onRetry,
  onScrollPositionChange,
}: MessageTimelineProps) {
  const scrollerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!activeMessageId) {
      return;
    }
    const element = scrollerRef.current?.querySelector(
      `[data-message-id="${CSS.escape(activeMessageId)}"]`,
    );
    element?.scrollIntoView({ block: "center", behavior: "smooth" });
  }, [activeMessageId, messages]);

  useEffect(() => {
    if (activeMessageId || restoreScrollPosition === null || !scrollerRef.current) {
      return;
    }
    scrollerRef.current.scrollTop = restoreScrollPosition;
  }, [activeMessageId, messages, restoreScrollPosition]);

  if (loading) {
    return (
      <div className="timeline-scroll" aria-label="Loading messages">
        <div className="message-skeleton" />
        <div className="message-skeleton assistant" />
        <div className="message-skeleton short" />
      </div>
    );
  }

  return (
    <div
      className="timeline-scroll"
      onScroll={(event) => onScrollPositionChange(event.currentTarget.scrollTop)}
      ref={scrollerRef}
    >
      {messages.length === 0 ? <EmptyConversation /> : null}
      <div className="message-stack" aria-live="polite">
        {messages.map((message) => (
          <MessageBlock
            highlighted={message.id === activeMessageId}
            key={message.id}
            message={message}
          />
        ))}
        {pending ? <PendingMessage /> : null}
        {error ? <ErrorMessage message={error} onRetry={onRetry} /> : null}
      </div>
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
}

function MessageBlock({ message, highlighted }: MessageBlockProps) {
  const [copied, setCopied] = useState(false);
  const reduceMotion = useReducedMotion();
  const isUser = message.role === "user";

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
    </motion.article>
  );
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
