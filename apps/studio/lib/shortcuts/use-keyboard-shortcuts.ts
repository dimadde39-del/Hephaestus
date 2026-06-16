"use client";

import { useEffect } from "react";

interface ShortcutHandlers {
  onNewConversation: () => void;
  onSearch: () => void;
  onEscape: () => void;
}

export function useKeyboardShortcuts({
  onNewConversation,
  onSearch,
  onEscape,
}: ShortcutHandlers) {
  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      const modifier = event.metaKey || event.ctrlKey;
      if (modifier && event.key.toLowerCase() === "n") {
        event.preventDefault();
        onNewConversation();
      }
      if (modifier && event.key.toLowerCase() === "k") {
        event.preventDefault();
        onSearch();
      }
      if (event.key === "Escape") {
        onEscape();
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onEscape, onNewConversation, onSearch]);
}
