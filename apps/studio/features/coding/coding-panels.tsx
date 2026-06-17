"use client";

import { ExternalLink, GitPullRequest, Play, RotateCcw } from "lucide-react";
import { useState } from "react";

import { StatusBadge } from "@/components/status-badge";
import { DiffViewer } from "@/features/diffs/diff-viewer";
import { DetailSection, WorkbenchStatusBadge, formatDate } from "@/features/workbench/workbench-shared";
import type { CodingDetailResponse, CodingRequestSummary } from "@/lib/types";

interface CodingListProps {
  items: CodingRequestSummary[];
  onOpen: (href: string) => void;
}

export function CodingRequestList({ items, onOpen }: CodingListProps) {
  if (items.length === 0) {
    return <p className="workbench-empty">No coding requests match this view.</p>;
  }
  return (
    <div className="workbench-table" role="table" aria-label="Coding requests">
      <div className="workbench-table-row is-heading" role="row">
        <span>Request</span>
        <span>Scope</span>
        <span>Status</span>
        <span>Validation</span>
        <span>Updated</span>
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
            <strong>{item.title}</strong>
            <small>{item.repo}</small>
          </span>
          <span>{item.scope}</span>
          <span>
            <WorkbenchStatusBadge status={item.status} />
          </span>
          <span>{item.validation_result}</span>
          <span>{formatDate(item.updated_at)}</span>
        </button>
      ))}
    </div>
  );
}

interface CodingDetailProps {
  detail: CodingDetailResponse;
  onNavigate: (href: string) => void;
  onApply: (changeId: string, approved: boolean) => void;
}

export function CodingDetailView({ detail, onNavigate, onApply }: CodingDetailProps) {
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const primaryPatch = detail.changes[0] ?? null;

  return (
    <article className="workbench-detail">
      <header className="workbench-detail-hero">
        <div>
          <p>Coding request</p>
          <h1>{detail.summary.title}</h1>
          <div className="workbench-status-row">
            <WorkbenchStatusBadge status={detail.summary.status} />
            <StatusBadge tone="neutral">{detail.summary.risk} risk</StatusBadge>
            <StatusBadge tone="neutral">{detail.summary.scope}</StatusBadge>
          </div>
        </div>
        <div className="workbench-action-row">
          {detail.linked_conversation ? (
            <button
              className="workbench-secondary-button"
              onClick={() => onNavigate(detail.linked_conversation?.href ?? "/")}
              type="button"
            >
              <ExternalLink aria-hidden="true" size={15} />
              Open linked conversation
            </button>
          ) : null}
          {primaryPatch ? (
            <button
              className="workbench-primary-button"
              onClick={() => onApply(primaryPatch.id, true)}
              type="button"
            >
              <Play aria-hidden="true" size={15} />
              Apply patch
            </button>
          ) : null}
        </div>
      </header>

      <DetailSection title="Request">
        <p>{detail.original_user_request}</p>
        <dl className="workbench-definition-grid">
          <div>
            <dt>Repo</dt>
            <dd>{detail.summary.repo_path}</dd>
          </div>
          <div>
            <dt>Policy / trust</dt>
            <dd>{detail.policy_trust_profile}</dd>
          </div>
        </dl>
      </DetailSection>

      {detail.plan ? (
        <DetailSection title="Plan">
          <p>{detail.plan.summary}</p>
          <ul className="workbench-list">
            {detail.plan.steps.map((step) => (
              <li key={step}>{step}</li>
            ))}
          </ul>
          <div className="workbench-chip-row">
            {detail.plan.expected_files.map((file) => (
              <code key={file}>{file}</code>
            ))}
          </div>
          <p className="workbench-muted">{detail.plan.rollback_behavior}</p>
        </DetailSection>
      ) : null}

      <DetailSection title="Changes">
        {detail.changes.length === 0 ? (
          <p className="workbench-empty">No patch proposal yet.</p>
        ) : (
          detail.changes.map((patch) => (
            <div className="workbench-change" key={patch.id}>
              <div className="workbench-subheading">
                <GitPullRequest aria-hidden="true" size={16} />
                <div>
                  <strong>{patch.summary}</strong>
                  <small>{patch.review_result}</small>
                </div>
              </div>
              <DiffViewer patch={patch} />
            </div>
          ))
        )}
      </DetailSection>

      <DetailSection title="Validation">
        {detail.validation.length === 0 ? (
          <p className="workbench-empty">Validation has not run for this request.</p>
        ) : (
          detail.validation.map((validation) => (
            <button
              className="workbench-linked-row"
              key={validation.summary.id}
              onClick={() => onNavigate(validation.summary.href)}
              type="button"
            >
              <span>{validation.summary.repo}</span>
              <WorkbenchStatusBadge status={validation.summary.status} />
              <strong>{validation.summary.passed}/{validation.summary.total_commands} passed</strong>
            </button>
          ))
        )}
      </DetailSection>

      <DetailSection title="Result">
        <p>{detail.result}</p>
        <p className="workbench-muted">{detail.practical_next_step}</p>
        <div className="workbench-status-row">
          {detail.checkpoint_available ? (
            <StatusBadge icon={RotateCcw} tone={detail.rollback_available ? "success" : "warning"}>
              {detail.rollback_available ? "Rollback available" : "Checkpoint restored"}
            </StatusBadge>
          ) : null}
        </div>
      </DetailSection>

      <details className="workbench-advanced" open={advancedOpen}>
        <summary onClick={(event) => {
          event.preventDefault();
          setAdvancedOpen((value) => !value);
        }}>
          Advanced details
        </summary>
        <div className="workbench-advanced-grid">
          {Object.entries(detail.advanced_details).map(([label, values]) => (
            <section key={label}>
              <h3>{label.replaceAll("_", " ")}</h3>
              {values.length === 0 ? (
                <p className="workbench-muted">None</p>
              ) : (
                values.map((value) => <code key={value}>{value}</code>)
              )}
            </section>
          ))}
        </div>
      </details>
    </article>
  );
}
