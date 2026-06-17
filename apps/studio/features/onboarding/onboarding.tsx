"use client";

import { MessageSquare, MonitorCheck, PlugZap, X } from "lucide-react";
import { useState } from "react";

import { IconButton } from "@/components/icon-button";
import type { RecentRepo } from "@/lib/types";

interface OnboardingProps {
  repos: RecentRepo[];
  onComplete: () => void;
  onNavigate: (href: string) => void;
}

export function Onboarding({ repos, onComplete, onNavigate }: OnboardingProps) {
  const [step, setStep] = useState(0);
  const repoName = repos[0]?.name ?? "a repo";

  function finish(href?: string) {
    onComplete();
    if (href) {
      onNavigate(href);
    }
  }

  return (
    <div className="onboarding-backdrop" role="dialog" aria-modal="true" aria-labelledby="onboarding-title">
      <section className="onboarding-panel">
        <IconButton className="onboarding-close" icon={X} label="Skip onboarding" onClick={() => finish()} />
        {step === 0 ? (
          <>
            <div className="talos-quiet-mark" />
            <h1 id="onboarding-title">Welcome to Hephaestus Studio</h1>
            <p>
              Hephaestus remembers your conversations and project context, helps you think and
              code, and validates its work.
            </p>
            <div className="onboarding-actions">
              <button className="workbench-primary-button" onClick={() => setStep(1)} type="button">
                Start
              </button>
              <button className="workbench-secondary-button" onClick={() => finish()} type="button">
                Skip
              </button>
            </div>
          </>
        ) : null}
        {step === 1 ? (
          <>
            <h1 id="onboarding-title">Choose how to start</h1>
            <div className="onboarding-choice-grid">
              <button onClick={() => finish("/conversations")} type="button">
                <MonitorCheck aria-hidden="true" size={20} />
                <strong>Start in local mode</strong>
                <span>No API key required.</span>
              </button>
              <button onClick={() => finish("/settings/models")} type="button">
                <PlugZap aria-hidden="true" size={20} />
                <strong>Configure a model</strong>
                <span>Add DeepSeek or OpenAI-compatible settings.</span>
              </button>
              <button onClick={() => finish("/workbench")} type="button">
                <MessageSquare aria-hidden="true" size={20} />
                <strong>Open {repoName}</strong>
                <span>Attach repo context when you are ready.</span>
              </button>
              <button onClick={() => finish("/conversations")} type="button">
                <MessageSquare aria-hidden="true" size={20} />
                <strong>Start chatting</strong>
                <span>Continue with normal Chat.</span>
              </button>
            </div>
          </>
        ) : null}
      </section>
    </div>
  );
}
