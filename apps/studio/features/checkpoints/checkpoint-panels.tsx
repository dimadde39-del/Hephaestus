"use client";

import { RotateCcw, ShieldAlert } from "lucide-react";
import { useState } from "react";

import { DetailSection, formatDate } from "@/features/workbench/workbench-shared";
import type { CheckpointDetailResponse, CheckpointSummary } from "@/lib/types";

interface CheckpointListProps {
  items: CheckpointSummary[];
  onOpen: (href: string) => void;
}

export function CheckpointList({ items, onOpen }: CheckpointListProps) {
  if (items.length === 0) {
    return <p className="workbench-empty">No checkpoints yet.</p>;
  }
  return (
    <div className="workbench-table" role="table" aria-label="Checkpoints">
      <div className="workbench-table-row is-heading" role="row">
        <span>Checkpoint</span>
        <span>Files</span>
        <span>Availability</span>
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
            <strong>{item.id}</strong>
            <small>{item.associated_coding_request_id ?? "Tool runtime"}</small>
          </span>
          <span>{item.files_covered.length}</span>
          <span>{item.availability}</span>
          <span>{formatDate(item.created_at)}</span>
        </button>
      ))}
    </div>
  );
}

interface CheckpointDetailProps {
  detail: CheckpointDetailResponse;
  onRestore: (checkpointId: string) => void;
}

export function CheckpointDetailView({ detail, onRestore }: CheckpointDetailProps) {
  const [confirmOpen, setConfirmOpen] = useState(false);
  const canRestore = detail.summary.availability === "available";

  return (
    <article className="workbench-detail">
      <header className="workbench-detail-hero">
        <div>
          <p>Checkpoint</p>
          <h1>{detail.summary.id}</h1>
          <div className="workbench-status-row">
            <span>{detail.summary.files_covered.length} file(s)</span>
            <span>{detail.summary.availability}</span>
            <span>{formatDate(detail.summary.created_at)}</span>
          </div>
        </div>
        <button
          className="workbench-primary-button"
          disabled={!canRestore}
          onClick={() => setConfirmOpen(true)}
          type="button"
        >
          <RotateCcw aria-hidden="true" size={15} />
          Restore checkpoint
        </button>
      </header>

      <DetailSection title="Files">
        <div className="checkpoint-file-list">
          {detail.files.map((file) => (
            <section className="checkpoint-file" key={file.path}>
              <strong>{file.path}</strong>
              <small>{file.existed ? "Existed before patch" : "Created by patch"}</small>
              <code>{file.original_hash || "no original hash"}</code>
              {file.protected ? (
                <span>
                  <ShieldAlert aria-hidden="true" size={14} />
                  protected path
                </span>
              ) : null}
            </section>
          ))}
        </div>
      </DetailSection>

      <DetailSection title="Restore History">
        {detail.restore_history.length === 0 ? (
          <p className="workbench-empty">This checkpoint has not been restored.</p>
        ) : (
          detail.restore_history.map((link) => <code key={link.href}>{link.label}</code>)
        )}
      </DetailSection>

      {confirmOpen ? (
        <div className="workbench-dialog-backdrop" role="presentation">
          <section
            aria-labelledby="restore-title"
            aria-modal="true"
            className="workbench-dialog"
            role="dialog"
          >
            <h2 id="restore-title">Restore checkpoint?</h2>
            <p>
              Restore {detail.summary.files_covered.length} file(s) in {detail.workspace_path}.
            </p>
            {detail.restore_warnings.length > 0 ? (
              <ul className="workbench-list">
                {detail.restore_warnings.map((warning) => (
                  <li key={warning}>{warning}</li>
                ))}
              </ul>
            ) : (
              <p className="workbench-muted">Later changes in these files may be overwritten.</p>
            )}
            <div className="workbench-action-row">
              <button
                className="workbench-secondary-button"
                onClick={() => setConfirmOpen(false)}
                type="button"
              >
                Cancel
              </button>
              <button
                className="workbench-primary-button"
                onClick={() => {
                  setConfirmOpen(false);
                  onRestore(detail.summary.id);
                }}
                type="button"
              >
                Restore
              </button>
            </div>
          </section>
        </div>
      ) : null}
    </article>
  );
}
