"use client";

import { Check, Copy, FileText, ShieldAlert } from "lucide-react";
import { useMemo, useState } from "react";

import { StatusBadge } from "@/components/status-badge";
import type { CodingPatchView } from "@/lib/types";

interface DiffViewerProps {
  patch: CodingPatchView;
}

interface DiffLine {
  kind: "context" | "addition" | "deletion" | "meta";
  oldNumber: number | null;
  newNumber: number | null;
  content: string;
}

interface DiffFile {
  path: string;
  lines: DiffLine[];
  additions: number;
  deletions: number;
}

export function DiffViewer({ patch }: DiffViewerProps) {
  const files = useMemo(() => parseUnifiedDiff(patch.diff), [patch.diff]);
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const [copied, setCopied] = useState(false);

  async function copyPatch() {
    await navigator.clipboard?.writeText(patch.diff);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1200);
  }

  function toggleFile(path: string) {
    setCollapsed((previous) => {
      const next = new Set(previous);
      if (next.has(path)) {
        next.delete(path);
      } else {
        next.add(path);
      }
      return next;
    });
  }

  return (
    <section className="diff-viewer" aria-label="Patch diff">
      <div className="diff-toolbar">
        <div>
          <StatusBadge tone={patch.applied ? "success" : "accent"}>
            {patch.applied ? "Applied" : "Proposed"}
          </StatusBadge>
          <StatusBadge tone={patch.diff_stats.large ? "warning" : "neutral"}>
            +{patch.diff_stats.additions} / -{patch.diff_stats.deletions}
          </StatusBadge>
        </div>
        <button className="workbench-secondary-button" onClick={() => void copyPatch()} type="button">
          {copied ? <Check aria-hidden="true" size={15} /> : <Copy aria-hidden="true" size={15} />}
          {copied ? "Copied" : "Copy patch"}
        </button>
      </div>
      {patch.protected_files.length > 0 ? (
        <div className="workbench-warning">
          <ShieldAlert aria-hidden="true" size={16} />
          Protected file warning: {patch.protected_files.join(", ")}
        </div>
      ) : null}
      {patch.diff_stats.large ? (
        <p className="workbench-muted">
          Large diff protection is active. Studio is showing a truncated patch excerpt.
        </p>
      ) : null}
      <div className="diff-file-list" aria-label="Changed files">
        {files.map((file) => (
          <button
            className={collapsed.has(file.path) ? "is-collapsed" : ""}
            key={file.path}
            onClick={() => toggleFile(file.path)}
            type="button"
          >
            <FileText aria-hidden="true" size={15} />
            <span>{file.path}</span>
            <strong>+{file.additions} / -{file.deletions}</strong>
          </button>
        ))}
      </div>
      <div className="diff-files">
        {files.map((file) => (
          <section className="diff-file" key={file.path}>
            <button
              className="diff-file-heading"
              onClick={() => toggleFile(file.path)}
              type="button"
            >
              <span>{file.path}</span>
              <strong>{collapsed.has(file.path) ? "Show" : "Hide"}</strong>
            </button>
            {collapsed.has(file.path) ? null : (
              <div className="diff-lines" role="table" aria-label={`Diff for ${file.path}`}>
                {file.lines.map((line, index) => (
                  <div className={`diff-line diff-${line.kind}`} key={`${file.path}-${index}`}>
                    <span className="diff-line-number">{line.oldNumber ?? ""}</span>
                    <span className="diff-line-number">{line.newNumber ?? ""}</span>
                    <code>{line.content}</code>
                  </div>
                ))}
              </div>
            )}
          </section>
        ))}
      </div>
    </section>
  );
}

function parseUnifiedDiff(diff: string): DiffFile[] {
  const lines = diff.split(/\r?\n/);
  const files: DiffFile[] = [];
  let current: DiffFile | null = null;
  let oldNumber = 0;
  let newNumber = 0;

  for (const rawLine of lines) {
    if (rawLine.startsWith("--- ")) {
      continue;
    }
    if (rawLine.startsWith("+++ ")) {
      const path = rawLine.replace(/^\+\+\+\s+b\//, "").replace(/^\+\+\+\s+/, "");
      current = { path, lines: [], additions: 0, deletions: 0 };
      files.push(current);
      continue;
    }
    if (!current) {
      continue;
    }
    if (rawLine.startsWith("@@")) {
      const match = /@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@/.exec(rawLine);
      oldNumber = match?.[1] ? Number(match[1]) : oldNumber;
      newNumber = match?.[2] ? Number(match[2]) : newNumber;
      current.lines.push({ kind: "meta", oldNumber: null, newNumber: null, content: rawLine });
      continue;
    }
    if (rawLine.startsWith("+")) {
      current.additions += 1;
      current.lines.push({
        kind: "addition",
        oldNumber: null,
        newNumber,
        content: rawLine,
      });
      newNumber += 1;
      continue;
    }
    if (rawLine.startsWith("-")) {
      current.deletions += 1;
      current.lines.push({
        kind: "deletion",
        oldNumber,
        newNumber: null,
        content: rawLine,
      });
      oldNumber += 1;
      continue;
    }
    current.lines.push({
      kind: "context",
      oldNumber,
      newNumber,
      content: rawLine ? ` ${rawLine}` : "",
    });
    oldNumber += 1;
    newNumber += 1;
  }

  if (files.length === 0 && diff.trim()) {
    return [
      {
        path: "patch.diff",
        additions: 0,
        deletions: 0,
        lines: diff.split(/\r?\n/).map((line) => ({
          kind: "context",
          oldNumber: null,
          newNumber: null,
          content: line,
        })),
      },
    ];
  }
  return files;
}
