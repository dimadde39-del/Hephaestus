"use client";

import { TerminalSquare } from "lucide-react";

import { DetailSection, WorkbenchStatusBadge, formatDate } from "@/features/workbench/workbench-shared";
import type { ToolActionDetailResponse, ToolActionSummary } from "@/lib/types";

interface ToolActionListProps {
  items: ToolActionSummary[];
  onOpen: (href: string) => void;
}

export function ToolActionList({ items, onOpen }: ToolActionListProps) {
  if (items.length === 0) {
    return <p className="workbench-empty">No tool actions yet.</p>;
  }
  return (
    <div className="tool-timeline" aria-label="Tool action timeline">
      {items.map((item) => (
        <button className="tool-event" key={item.id} onClick={() => onOpen(item.href)} type="button">
          <span className="tool-event-dot" />
          <span>
            <strong>{item.action}</strong>
            <small>{formatDate(item.created_at)} / {item.risk} / {item.policy_decision}</small>
          </span>
          <WorkbenchStatusBadge status={item.status} />
        </button>
      ))}
    </div>
  );
}

interface ToolDetailProps {
  detail: ToolActionDetailResponse;
  onNavigate: (href: string) => void;
}

export function ToolActionDetailView({ detail, onNavigate }: ToolDetailProps) {
  return (
    <article className="workbench-detail">
      <header className="workbench-detail-hero">
        <div>
          <p>Tool action</p>
          <h1>{detail.summary.action}</h1>
          <div className="workbench-status-row">
            <WorkbenchStatusBadge status={detail.summary.status} />
            <span>{detail.summary.risk}</span>
            <span>{detail.summary.policy_decision}</span>
          </div>
        </div>
      </header>

      <DetailSection title="Result">
        <p>{detail.summary.result}</p>
        <dl className="workbench-definition-grid">
          <div>
            <dt>Workspace</dt>
            <dd>{detail.workspace_path}</dd>
          </div>
          <div>
            <dt>Exit code</dt>
            <dd>{detail.exit_code ?? "n/a"}</dd>
          </div>
        </dl>
      </DetailSection>

      <DetailSection title="Technical Details">
        {detail.command ? (
          <div className="workbench-command-line">
            <TerminalSquare aria-hidden="true" size={16} />
            <code>{detail.command}</code>
          </div>
        ) : null}
        {detail.target_path ? <code>{detail.target_path}</code> : null}
        <div className="workbench-chip-row">
          {detail.files_touched.map((file) => <code key={file}>{file}</code>)}
        </div>
        {detail.stdout ? (
          <details className="workbench-output">
            <summary>stdout</summary>
            <pre>{detail.stdout}</pre>
          </details>
        ) : null}
        {detail.stderr ? (
          <details className="workbench-output">
            <summary>stderr</summary>
            <pre>{detail.stderr}</pre>
          </details>
        ) : null}
      </DetailSection>

      <DetailSection title="Links">
        <div className="workbench-action-row">
          {detail.checkpoint_id ? (
            <button
              className="workbench-secondary-button"
              onClick={() => onNavigate(`/workbench/checkpoints/${detail.checkpoint_id}`)}
              type="button"
            >
              Checkpoint
            </button>
          ) : null}
          {detail.outcome_id ? (
            <button
              className="workbench-secondary-button"
              onClick={() => onNavigate(`/workbench/outcomes/${detail.outcome_id}`)}
              type="button"
            >
              Outcome
            </button>
          ) : null}
        </div>
      </DetailSection>
    </article>
  );
}
