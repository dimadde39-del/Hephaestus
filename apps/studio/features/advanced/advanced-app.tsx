"use client";

import { GitBranch, Network, Sigma, SlidersHorizontal } from "lucide-react";
import { useEffect, useState } from "react";

import { StatusBadge } from "@/components/status-badge";
import {
  WorkbenchError,
  WorkbenchLoading,
  formatDate,
} from "@/features/workbench/workbench-shared";
import { StudioApiClient, StudioApiError } from "@/lib/api/client";
import type {
  AdvancedDecisionDetail,
  AdvancedDecisionListResponse,
  AdvancedDecisionSummary,
  AdvancedParetoCandidate,
  AdvancedParetoDetail,
  AdvancedQuboDetail,
} from "@/lib/types";

export type AdvancedRoute =
  | { section: "advanced"; area: "decisions"; id: string | null }
  | { section: "advanced"; area: "pareto"; id: string | null }
  | { section: "advanced"; area: "qubo"; id: string | null };

interface AdvancedAppProps {
  api: StudioApiClient;
  route: AdvancedRoute;
  onNavigate: (href: string) => void;
}

const decisionFilters = ["all", "conversation", "coding", "validation", "release", "policy", "tool"];

export function AdvancedApp({ api, route, onNavigate }: AdvancedAppProps) {
  const [list, setList] = useState<AdvancedDecisionListResponse | null>(null);
  const [decision, setDecision] = useState<AdvancedDecisionDetail | null>(null);
  const [pareto, setPareto] = useState<AdvancedParetoDetail | null>(null);
  const [qubo, setQubo] = useState<AdvancedQuboDetail | null>(null);
  const [category, setCategory] = useState("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        if (route.area === "decisions" && route.id) {
          const next = await api.advancedDecision(route.id);
          if (!cancelled) setDecision(next);
        } else if (route.area === "pareto" && route.id) {
          const next = await api.advancedPareto(route.id);
          if (!cancelled) setPareto(next);
        } else if (route.area === "qubo" && route.id) {
          const next = await api.advancedQubo(route.id);
          if (!cancelled) setQubo(next);
        } else {
          const next = await api.advancedDecisions({
            category: category === "all" ? undefined : category,
            limit: 120,
          });
          if (!cancelled) setList(next);
        }
      } catch (nextError) {
        if (!cancelled) setError(errorMessage(nextError, "Advanced artifact could not load."));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [api, category, route.area, route.id]);

  return (
    <div className="workbench-scroll">
      <nav className="workbench-tabs" aria-label="Advanced sections">
        <button
          className={route.area === "decisions" ? "is-active" : ""}
          onClick={() => onNavigate("/advanced/decisions")}
          type="button"
        >
          <GitBranch aria-hidden="true" size={15} />
          Decisions
        </button>
        <button
          className={route.area === "pareto" ? "is-active" : ""}
          onClick={() => onNavigate(list?.pareto_frontiers[0] ? `/advanced/pareto/${list.pareto_frontiers[0].id}` : "/advanced/decisions")}
          type="button"
        >
          <Network aria-hidden="true" size={15} />
          Pareto
        </button>
        <button
          className={route.area === "qubo" ? "is-active" : ""}
          onClick={() => onNavigate(list?.qubo_problems[0] ? `/advanced/qubo/${list.qubo_problems[0].id}` : "/advanced/decisions")}
          type="button"
        >
          <Sigma aria-hidden="true" size={15} />
          QUBO
        </button>
      </nav>
      <div className="workbench-inner">
        <header className="workbench-page-heading">
          <p>Advanced Internals</p>
          <h1>{titleForRoute(route)}</h1>
        </header>

        {loading ? <WorkbenchLoading label="Loading advanced artifact" /> : null}
        {error ? <WorkbenchError label={error} /> : null}

        {!loading && !error ? (
          <>
            {route.area === "decisions" && !route.id && list ? (
              <DecisionListView
                category={category}
                list={list}
                onCategory={setCategory}
                onNavigate={onNavigate}
              />
            ) : null}
            {route.area === "decisions" && route.id && decision ? (
              <DecisionDetailView decision={decision} onNavigate={onNavigate} />
            ) : null}
            {route.area === "pareto" && route.id && pareto ? (
              <ParetoView detail={pareto} />
            ) : null}
            {route.area === "qubo" && route.id && qubo ? <QuboView detail={qubo} /> : null}
            {route.area !== "decisions" && !route.id ? (
              <div className="workbench-state">
                <SlidersHorizontal aria-hidden="true" size={18} />
                <span>Advanced artifact not selected. Data is safe; open one from Decisions.</span>
              </div>
            ) : null}
          </>
        ) : null}
      </div>
    </div>
  );
}

function DecisionListView({
  list,
  category,
  onCategory,
  onNavigate,
}: {
  list: AdvancedDecisionListResponse;
  category: string;
  onCategory: (category: string) => void;
  onNavigate: (href: string) => void;
}) {
  return (
    <div className="studio-two-column">
      <section className="workbench-detail">
        <div className="workbench-filter-row">
          <label>
            Filter
            <select onChange={(event) => onCategory(event.target.value)} value={category}>
              {decisionFilters.map((filter) => (
                <option key={filter} value={filter}>
                  {labelize(filter)}
                </option>
              ))}
            </select>
          </label>
        </div>
        {list.decisions.length === 0 ? (
          <div className="workbench-state">
            <span>No decision traces match this filter. Data is safe; advanced artifacts appear after real work creates them.</span>
          </div>
        ) : (
          <div className="workbench-table" role="list" aria-label="Decision traces">
            <div className="workbench-table-row is-heading">
              <span>Decision</span>
              <span>Selected</span>
              <span>Confidence</span>
              <span>Date</span>
            </div>
            {list.decisions.map((decision) => (
              <DecisionRow decision={decision} key={decision.id} onNavigate={onNavigate} />
            ))}
          </div>
        )}
      </section>
      <section className="workbench-launch-panel">
        <h2>Optimization artifacts</h2>
        <p>
          These are secondary views for deliberate inspection. They do not prove a decision is
          objectively correct.
        </p>
        <h3>Pareto</h3>
        {list.pareto_frontiers.length === 0 ? <p className="workbench-muted">No Pareto frontier recorded.</p> : null}
        {list.pareto_frontiers.map((frontier) => (
          <button
            className="workbench-linked-row"
            key={frontier.id}
            onClick={() => onNavigate(`/advanced/pareto/${frontier.id}`)}
            type="button"
          >
            <span>{frontier.title}</span>
            <small>{formatDate(frontier.created_at)}</small>
          </button>
        ))}
        <h3>QUBO</h3>
        {list.qubo_problems.length === 0 ? <p className="workbench-muted">No QUBO problem recorded.</p> : null}
        {list.qubo_problems.map((problem) => (
          <button
            className="workbench-linked-row"
            key={problem.id}
            onClick={() => onNavigate(`/advanced/qubo/${problem.id}`)}
            type="button"
          >
            <span>{problem.title}</span>
            <small>{formatDate(problem.created_at)}</small>
          </button>
        ))}
      </section>
    </div>
  );
}

function DecisionRow({
  decision,
  onNavigate,
}: {
  decision: AdvancedDecisionSummary;
  onNavigate: (href: string) => void;
}) {
  return (
    <button className="workbench-table-row" onClick={() => onNavigate(decision.href)} type="button">
      <span>
        <strong>{decision.decision}</strong>
        <small>{labelize(decision.decision_type)}</small>
      </span>
      <span>{decision.selected_option}</span>
      <span>{Math.round(decision.confidence * 100)}%</span>
      <span>{formatDate(decision.occurred_at)}</span>
    </button>
  );
}

function DecisionDetailView({
  decision,
  onNavigate,
}: {
  decision: AdvancedDecisionDetail;
  onNavigate: (href: string) => void;
}) {
  return (
    <section className="workbench-detail">
      <div className="workbench-detail-hero">
        <div>
          <StatusBadge tone="accent">{labelize(decision.decision_type)}</StatusBadge>
          <h2>{decision.decision}</h2>
          <p className="workbench-muted">Selected {decision.selected_option}</p>
        </div>
        <strong>{Math.round(decision.confidence * 100)}%</strong>
      </div>
      <DetailList title="Reasons" items={decision.reasons} />
      <DetailList title="Alternatives" items={decision.alternatives} />
      <DetailList title="Assumptions" items={decision.assumptions} />
      <DetailList title="Evidence" items={decision.evidence} />
      <section className="workbench-detail-section">
        <h2>Outcome</h2>
        <p className="workbench-muted">{decision.later_evidence_supported}</p>
        {decision.linked_work.map((link) => (
          <button className="workbench-linked-row" key={link.href} onClick={() => onNavigate(link.href)} type="button">
            {link.label}
          </button>
        ))}
      </section>
      <details className="workbench-advanced">
        <summary>Developer details</summary>
        <pre>{JSON.stringify(decision.developer_payload, null, 2)}</pre>
      </details>
    </section>
  );
}

function ParetoView({ detail }: { detail: AdvancedParetoDetail }) {
  return (
    <section className="workbench-detail">
      <div className="workbench-detail-hero">
        <div>
          <StatusBadge tone="accent">Pareto frontier</StatusBadge>
          <h2>{detail.title}</h2>
          <p className="workbench-muted">{detail.explanation}</p>
        </div>
        <small>{detail.preference_profile}</small>
      </div>
      <ParetoChart candidates={detail.candidates} xLabel={detail.objective_x} yLabel={detail.objective_y} />
      <DetailList title="Tradeoffs" items={detail.tradeoffs} />
      <section className="workbench-detail-section">
        <h2>Accessible table</h2>
        <div className="workbench-table">
          <div className="workbench-table-row is-heading">
            <span>Candidate</span>
            <span>{labelize(detail.objective_x)}</span>
            <span>{labelize(detail.objective_y)}</span>
            <span>Status</span>
          </div>
          {detail.candidates.map((candidate) => (
            <div className="workbench-table-row" key={candidate.id}>
              <span>{candidate.label}</span>
              <span>{candidate.x.toFixed(3)}</span>
              <span>{candidate.y.toFixed(3)}</span>
              <span>{candidate.selected ? "Selected" : candidate.is_frontier ? "Non-dominated" : "Dominated"}</span>
            </div>
          ))}
        </div>
      </section>
    </section>
  );
}

function ParetoChart({
  candidates,
  xLabel,
  yLabel,
}: {
  candidates: AdvancedParetoCandidate[];
  xLabel: string;
  yLabel: string;
}) {
  const xs = candidates.map((candidate) => candidate.x);
  const ys = candidates.map((candidate) => candidate.y);
  const minX = Math.min(...xs, 0);
  const maxX = Math.max(...xs, 1);
  const minY = Math.min(...ys, 0);
  const maxY = Math.max(...ys, 1);
  function x(value: number) {
    return 44 + ((value - minX) / Math.max(0.0001, maxX - minX)) * 300;
  }
  function y(value: number) {
    return 244 - ((value - minY) / Math.max(0.0001, maxY - minY)) * 200;
  }
  return (
    <figure className="pareto-chart">
      <svg aria-labelledby="pareto-title pareto-desc" role="img" viewBox="0 0 380 280">
        <title id="pareto-title">Pareto frontier chart</title>
        <desc id="pareto-desc">
          Candidate scatter plot comparing {labelize(xLabel)} and {labelize(yLabel)}.
        </desc>
        <line x1="44" x2="344" y1="244" y2="244" />
        <line x1="44" x2="44" y1="44" y2="244" />
        {candidates.map((candidate, index) => {
          const labelOffsetY = (index % 3) * 13 - 9;
          return (
          <g key={candidate.id}>
            <circle
              className={`${candidate.is_frontier ? "is-frontier" : "is-dominated"} ${candidate.selected ? "is-selected" : ""}`}
              cx={x(candidate.x)}
              cy={y(candidate.y)}
              r={candidate.selected ? 7 : 5}
            />
            <text x={x(candidate.x) + 10} y={y(candidate.y) + labelOffsetY}>{candidate.label}</text>
          </g>
          );
        })}
      </svg>
      <figcaption>
        {labelize(xLabel)} versus {labelize(yLabel)}. Frontier points are emphasized; dominated
        points stay visible for comparison.
      </figcaption>
    </figure>
  );
}

function QuboView({ detail }: { detail: AdvancedQuboDetail }) {
  return (
    <section className="workbench-detail">
      <div className="workbench-detail-hero">
        <div>
          <StatusBadge tone="accent">QUBO</StatusBadge>
          <h2>{detail.purpose}</h2>
          <p className="workbench-muted">{detail.explanation}</p>
        </div>
        <small>{detail.solver_used}</small>
      </div>
      <dl className="workbench-definition-grid">
        <div>
          <dt>Selected solution</dt>
          <dd>{detail.selected_solution}</dd>
        </div>
        <div>
          <dt>Objective value</dt>
          <dd>{detail.objective_value ?? "No solution"}</dd>
        </div>
        <div>
          <dt>Feasible</dt>
          <dd>{detail.feasible === null ? "unknown" : detail.feasible ? "yes" : "no"}</dd>
        </div>
        <div>
          <dt>Problem type</dt>
          <dd>{labelize(detail.problem_type)}</dd>
        </div>
      </dl>
      <section className="workbench-detail-section">
        <h2>Variables</h2>
        <div className="workbench-chip-row">
          {detail.variables.map((variable) => (
            <code key={variable.id}>{variable.selected ? "1" : "0"} {variable.label}</code>
          ))}
        </div>
      </section>
      <DetailList title="Constraints" items={detail.constraints} />
      {detail.comparison_with_heuristic ? (
        <section className="workbench-detail-section">
          <h2>Comparison</h2>
          <p className="workbench-muted">{detail.comparison_with_heuristic}</p>
        </section>
      ) : null}
      <details className="workbench-advanced">
        <summary>Mathematical details</summary>
        <pre>{JSON.stringify(detail.mathematical_details, null, 2)}</pre>
      </details>
    </section>
  );
}

function DetailList({ title, items }: { title: string; items: string[] }) {
  return (
    <section className="workbench-detail-section">
      <h2>{title}</h2>
      {items.length === 0 ? (
        <p className="workbench-muted">No {title.toLowerCase()} recorded.</p>
      ) : (
        <ul className="workbench-list">
          {items.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      )}
    </section>
  );
}

function titleForRoute(route: AdvancedRoute) {
  if (route.area === "pareto") return "Pareto Frontier";
  if (route.area === "qubo") return "QUBO Problem";
  return route.id ? "Decision Trace" : "Decision Traces";
}

function labelize(value: string) {
  return value.replaceAll("_", " ").replace(/^\w/, (letter) => letter.toUpperCase());
}

function errorMessage(error: unknown, fallback: string) {
  return error instanceof StudioApiError ? error.message : fallback;
}
