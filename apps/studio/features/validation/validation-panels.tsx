"use client";

import { ChevronDown, FileCheck2, TerminalSquare } from "lucide-react";
import { useState } from "react";

import { DetailSection, WorkbenchStatusBadge, formatDate } from "@/features/workbench/workbench-shared";
import type { ValidationDetailResponse, ValidationSummary } from "@/lib/types";

interface ValidationListProps {
  items: ValidationSummary[];
  onOpen: (href: string) => void;
}

export function ValidationList({ items, onOpen }: ValidationListProps) {
  if (items.length === 0) {
    return <p className="workbench-empty">No validation results yet.</p>;
  }
  return (
    <div className="workbench-table" role="table" aria-label="Validation results">
      <div className="workbench-table-row is-heading" role="row">
        <span>Repo</span>
        <span>Status</span>
        <span>Commands</span>
        <span>Evidence</span>
        <span>Date</span>
      </div>
      {items.map((item) => (
        <button
          className="workbench-table-row"
          key={item.id}
          onClick={() => onOpen(item.href)}
          role="row"
          type="button"
        >
          <span>
            <strong>{item.repo}</strong>
            <small>{item.related_coding_request_id ?? item.release_plan_id ?? item.repo_path}</small>
          </span>
          <span>
            <WorkbenchStatusBadge status={item.status} />
          </span>
          <span>{item.total_commands}</span>
          <span>{item.evidence_mode}</span>
          <span>{formatDate(item.created_at)}</span>
        </button>
      ))}
    </div>
  );
}

interface ValidationDetailProps {
  detail: ValidationDetailResponse;
  onNavigate: (href: string) => void;
}

export function ValidationDetailView({ detail, onNavigate }: ValidationDetailProps) {
  return (
    <article className="workbench-detail">
      <header className="workbench-detail-hero">
        <div>
          <p>Validation</p>
          <h1>{detail.summary.repo}</h1>
          <div className="workbench-status-row">
            <WorkbenchStatusBadge status={detail.summary.status} />
            <span>{detail.summary.passed}/{detail.summary.total_commands} passed</span>
            <span>{detail.summary.duration_seconds.toFixed(2)}s</span>
          </div>
        </div>
      </header>

      <DetailSection title="Commands">
        <div className="validation-command-list">
          {detail.commands.map((command) => (
            <ValidationCommandRow
              command={command}
              key={command.id}
              onNavigate={onNavigate}
            />
          ))}
        </div>
      </DetailSection>
    </article>
  );
}

type ValidationCommand = ValidationDetailResponse["commands"][number];

function ValidationCommandRow({
  command,
  onNavigate,
}: {
  command: ValidationCommand;
  onNavigate: (href: string) => void;
}) {
  const [open, setOpen] = useState(false);
  return (
    <section className="validation-command">
      <button className="validation-command-heading" onClick={() => setOpen((value) => !value)} type="button">
        <TerminalSquare aria-hidden="true" size={16} />
        <span>
          <strong>{command.command}</strong>
          <small>{command.command_type} / exit {command.exit_code ?? "n/a"} / {command.duration_seconds.toFixed(2)}s</small>
        </span>
        <WorkbenchStatusBadge status={command.status} />
        <ChevronDown aria-hidden="true" size={15} />
      </button>
      <p className="workbench-muted">{command.output_summary || "No output summary."}</p>
      {open ? (
        <div className="validation-output">
          {command.stdout ? (
            <details>
              <summary>stdout</summary>
              <pre>{command.stdout}</pre>
            </details>
          ) : null}
          {command.stderr ? (
            <details>
              <summary>stderr</summary>
              <pre>{command.stderr}</pre>
            </details>
          ) : null}
          {command.output_truncated ? <p className="workbench-muted">Output was truncated.</p> : null}
          <div className="workbench-action-row">
            {command.tool_action_id ? (
              <button
                className="workbench-secondary-button"
                onClick={() => onNavigate(`/workbench/tools/${command.tool_action_id}`)}
                type="button"
              >
                <FileCheck2 aria-hidden="true" size={15} />
                Linked tool action
              </button>
            ) : null}
            {command.outcome_id ? (
              <button
                className="workbench-secondary-button"
                onClick={() => onNavigate(`/workbench/outcomes/${command.outcome_id}`)}
                type="button"
              >
                Linked outcome
              </button>
            ) : null}
          </div>
        </div>
      ) : null}
    </section>
  );
}
