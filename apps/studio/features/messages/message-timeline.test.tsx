import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { MessageTimeline } from "./message-timeline";
import type { StudioMessage } from "@/lib/types";

const scrollTo = vi.fn(function (this: HTMLElement, options: ScrollToOptions) {
  this.scrollTop = Number(options.top ?? 0);
});

beforeEach(() => {
  scrollTo.mockClear();
  Object.defineProperties(HTMLElement.prototype, {
    clientHeight: { configurable: true, get: () => 200 },
    scrollHeight: { configurable: true, get: () => 1000 },
    scrollTo: { configurable: true, value: scrollTo },
  });
  global.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
});

describe("MessageTimeline", () => {
  it("opens at the bottom and remains keyboard scrollable", () => {
    renderTimeline([message("one")]);
    const transcript = screen.getByRole("region", { name: "Message transcript" });
    expect(transcript).toHaveAttribute("tabindex", "0");
    expect(scrollTo).toHaveBeenCalledWith({ top: 1000, behavior: "auto" });

    fireEvent.keyDown(transcript, { key: "Home" });
    expect(scrollTo).toHaveBeenLastCalledWith({ top: 0, behavior: "auto" });
    fireEvent.keyDown(transcript, { key: "End" });
    expect(scrollTo).toHaveBeenLastCalledWith({ top: 1000, behavior: "auto" });
  });

  it("does not force scroll while reading history and offers a return action", () => {
    const view = renderTimeline([message("one")]);
    const transcript = screen.getByRole("region", { name: "Message transcript" });
    Object.defineProperty(transcript, "scrollTop", { configurable: true, writable: true, value: 100 });
    fireEvent.scroll(transcript);
    scrollTo.mockClear();

    view.rerender(component([message("one"), message("two")]));
    expect(scrollTo).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Jump to latest" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Jump to latest" }));
    expect(scrollTo).toHaveBeenCalledWith({ top: 1000, behavior: "smooth" });
  });
});

function renderTimeline(messages: StudioMessage[]) {
  return render(component(messages));
}

function component(messages: StudioMessage[]) {
  return (
    <MessageTimeline
      activeMessageId={null}
      conversationId="conv-scroll"
      error={null}
      loading={false}
      messages={messages}
      onRetry={() => undefined}
      pending={false}
    />
  );
}

function message(content: string): StudioMessage {
  return {
    id: `message-${content}`,
    session_id: "conv-scroll",
    role: "assistant",
    content,
    intent: "general",
    mode: "balanced",
    provider_model: null,
    metadata: {},
    created_at: "2026-06-29T00:00:00Z",
  };
}
