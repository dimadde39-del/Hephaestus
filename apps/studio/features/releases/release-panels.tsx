"use client";

import { DetailSection, formatDate } from "@/features/workbench/workbench-shared";
import type { ReleaseDetailResponse, ReleaseSummary } from "@/lib/types";

interface ReleaseListProps {
  items: ReleaseSummary[];
  onOpen: (href: string) => void;
}

export function ReleaseList({ items, onOpen }: ReleaseListProps) {
  if (items.length === 0) {
    return <p className="workbench-empty">No release evidence yet.</p>;
  }
  return (
    <div className="workbench-table" role="table" aria-label="Release evidence">
      <div className="workbench-table-row is-heading" role="row">
        <span>Repo</span>
        <span>Readiness</span>
        <span>Validation</span>
        <span>Created</span>
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
            <small>{item.recommendation}</small>
          </span>
          <span>{item.readiness}</span>
          <span>{item.validation_status}</span>
          <span>{formatDate(item.created_at)}</span>
        </button>
      ))}
    </div>
  );
}

interface ReleaseDetailProps {
  detail: ReleaseDetailResponse;
  onNavigate: (href: string) => void;
}

export function ReleaseDetailView({ detail, onNavigate }: ReleaseDetailProps) {
  return (
    <article className="workbench-detail">
      <header className="workbench-detail-hero">
        <div>
          <p>Release evidence</p>
          <h1>{detail.summary.repo}</h1>
          <div className="workbench-status-row">
            <span>Readiness {detail.summary.readiness}</span>
            <span>{detail.summary.evidence_mode}</span>
          </div>
        </div>
      </header>

      <DetailSection title="Summary">
        <p>{detail.practical_summary}</p>
      </DetailSection>

      <DetailSection title="Validation Evidence">
        {detail.real_validation_evidence.length === 0 ? (
          <p className="workbench-empty">No real validation evidence is linked.</p>
        ) : (
          detail.real_validation_evidence.map((item) => (
            <button className="workbench-linked-row" key={item.id} onClick={() => onNavigate(item.href)} type="button">
              <span>{item.repo}</span>
              <strong>{item.passed}/{item.total_commands} passed</strong>
            </button>
          ))
        )}
      </DetailSection>

      <DetailSection title="Blockers">
        {detail.blockers.length === 0 ? (
          <p className="workbench-empty">No blockers recorded.</p>
        ) : (
          <ul className="workbench-list">
            {detail.blockers.map((blocker) => <li key={blocker}>{blocker}</li>)}
          </ul>
        )}
      </DetailSection>

      <DetailSection title="Next Actions">
        <ul className="workbench-list">
          {detail.next_actions.map((action) => <li key={action}>{action}</li>)}
        </ul>
      </DetailSection>

      <details className="workbench-advanced">
        <summary>Advanced optimization details</summary>
        <div className="workbench-advanced-grid">
          <section>
            <h3>Pareto</h3>
            {detail.advanced_optimization_details.pareto_frontier_ids.map((id) => (
              <code key={id}>{id}</code>
            ))}
          </section>
          <section>
            <h3>QUBO</h3>
            {detail.advanced_optimization_details.qubo_problem_ids.map((id) => (
              <code key={id}>{id}</code>
            ))}
          </section>
        </div>
      </details>
    </article>
  );
}
