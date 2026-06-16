import type { ReactNode } from "react";

interface AppShellProps {
  sidebar: ReactNode;
  header: ReactNode;
  timeline: ReactNode;
  composer: ReactNode;
  context: ReactNode;
  search: ReactNode;
  contextCollapsed: boolean;
  sidebarCollapsed: boolean;
}

export function AppShell({
  sidebar,
  header,
  timeline,
  composer,
  context,
  search,
  contextCollapsed,
  sidebarCollapsed,
}: AppShellProps) {
  return (
    <main
      className={`studio-shell ${contextCollapsed ? "has-collapsed-context" : ""} ${
        sidebarCollapsed ? "has-collapsed-sidebar" : ""
      }`}
    >
      {sidebar}
      <section className="chat-column" aria-label="Message timeline">
        {header}
        {timeline}
        {composer}
      </section>
      {context}
      {search}
    </main>
  );
}
