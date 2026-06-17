"use client";

import { DetailSection, WorkbenchStatusBadge, formatDate } from "@/features/workbench/workbench-shared";
import type { OutcomeDetailResponse, OutcomeSummary } from "@/lib/types";

interface OutcomeListProps {
  items: OutcomeSummary[];
  onOpen: (href: string) => void;
}

export function OutcomeList({ items, onOpen }: OutcomeListProps) {
  if (items.length === 0) {
    return <p className="workbench-empty">No outcomes yet.</p>;
  }
  return (
    <div className="workbench-table" role="table" aria-label="Outcomes">
      <div className="workbench-table-row is-heading" role="row">
        <span>Outcome</span>
        <span>Status</span>
        <span>Lesson</span>
        <span>Date</span>
      </div>
      {items.map((item) => (
        <button className="workbench-table-row" key={item.id} onClick={() => onOpen(item.href)} role="row" type="button">
          <span>
            <strong>{item.what_happened}</strong>
            <small>{item.rollback}</small>
          </span>
          <span>
            <WorkbenchStatusBadge status={item.status} />
          </span>
          <span>{item.practical_lesson || "No reusable lesson yet"}</span>
          <span>{formatDate(item.observed_at)}</span>
        </button>
      ))}
    </div>
  );
}

export function OutcomeDetailView({ detail }: { detail: OutcomeDetailResponse }) {
  return (
    <article className="workbench-detail">
      <header className="workbench-detail-hero">
        <div>
          <p>Outcome</p>
          <h1>{detail.summary.what_happened}</h1>
          <div className="workbench-status-row">
            <WorkbenchStatusBadge status={detail.summary.status} />
            <span>{formatDate(detail.summary.observed_at)}</span>
          </div>
        </div>
      </header>

      <DetailSection title="Evidence">
        {detail.evidence_items.length === 0 ? (
          <p className="workbench-empty">No evidence text recorded.</p>
        ) : (
          detail.evidence_items.map((item) => <p key={item}>{item}</p>)
        )}
      </DetailSection>

      <DetailSection title="Rollback">
        <p>{detail.summary.rollback}</p>
      </DetailSection>

      {detail.what_hephaestus_learned.length > 0 ? (
        <DetailSection title="What Hephaestus Learned">
          <ul className="workbench-list">
            {detail.what_hephaestus_learned.map((lesson) => (
              <li key={lesson}>{lesson}</li>
            ))}
          </ul>
        </DetailSection>
      ) : null}

      {detail.reflections.length > 0 ? (
        <details className="workbench-advanced">
          <summary>Reflections</summary>
          <ul className="workbench-list">
            {detail.reflections.map((reflection) => (
              <li key={reflection}>{reflection}</li>
            ))}
          </ul>
        </details>
      ) : null}
    </article>
  );
}
