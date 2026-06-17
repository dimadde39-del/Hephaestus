"use client";

import { ShieldCheck } from "lucide-react";

import type { TrustMode, TrustRuleKey, TrustSettingsResponse } from "@/lib/types";

interface TrustSettingsProps {
  settings: TrustSettingsResponse;
  onUpdate: (payload: { mode?: TrustMode; rules?: Partial<Record<TrustRuleKey, boolean>> }) => void;
}

const modes: { value: TrustMode; label: string }[] = [
  { value: "manual", label: "Manual" },
  { value: "developer", label: "Developer" },
  { value: "local_power_user", label: "Local Power User" },
  { value: "strict", label: "Strict" },
];

export function TrustSettings({ settings, onUpdate }: TrustSettingsProps) {
  return (
    <article className="workbench-detail">
      <header className="workbench-detail-hero">
        <div>
          <p>Trust</p>
          <h1>Autonomy and approvals</h1>
          <div className="workbench-status-row">
            <span>{settings.effective_policy_profile}</span>
          </div>
        </div>
      </header>

      <section className="trust-mode-control" aria-label="Trust mode">
        {modes.map((mode) => (
          <button
            aria-pressed={settings.mode === mode.value}
            className={settings.mode === mode.value ? "is-active" : ""}
            key={mode.value}
            onClick={() => onUpdate({ mode: mode.value })}
            type="button"
          >
            {mode.label}
          </button>
        ))}
      </section>

      <section className="trust-rule-list" aria-label="Trust rules">
        {settings.rules.map((rule) => (
          <label className={rule.hard_blocked ? "is-disabled" : ""} key={rule.key}>
            <input
              checked={rule.allowed}
              disabled={rule.hard_blocked}
              onChange={(event) => onUpdate({ rules: { [rule.key]: event.target.checked } })}
              type="checkbox"
            />
            <span>
              <strong>{rule.label}</strong>
              <small>
                {rule.hard_blocked
                  ? "Hard blocked"
                  : rule.implemented
                    ? rule.risk
                    : "Not implemented in this phase"}
              </small>
            </span>
          </label>
        ))}
      </section>

      <section className="trust-effective">
        <h2>
          <ShieldCheck aria-hidden="true" size={16} />
          Effective behavior
        </h2>
        <ul className="workbench-list">
          {settings.effective_behavior.map((item) => (
            <li key={item}>{item}</li>
          ))}
          {settings.hard_blocks.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </section>
    </article>
  );
}
