# Hephaestus Phase 1 Foundation

## Product Vision

Hephaestus is an open-source forge for always-on, self-improving AI agents. It
explores optimization-first execution: what to do next, which model to use, what
context to include, which tools to call, and when to ask for approval.

## Core Architecture Decisions

- Python package with typed Pydantic schemas.
- Typer/Rich CLI for a useful local demo.
- Spec layer separates goals, constraints, tasks, and plans.
- Optimization modules are first-class, not helper functions hidden in the CLI.
- Safety policy evaluates tools and shell commands before execution.
- Memory starts in-memory but uses durable record shapes.

## Why Python

Python is cheap to run locally, familiar for AI/runtime experiments, easy to test,
and has strong data modeling and CLI libraries. It is also a good fit for later
optimization libraries and local storage.

## Why Fake / Mock Models Are Required

The project must work without paid APIs. Fake models make tests deterministic,
keep CI cheap, and force the architecture to route by provider-agnostic
capabilities instead of one vendor SDK.

## Why Quantum-Inspired Optimization Is Central

Agent execution is a sequence of constrained choices. Task ordering, model
routing, context packing, tool selection, autonomy, and token budget allocation
all have tradeoffs. Treating those choices as optimization problems is the core
differentiator.

## Current Limitations

- No persistent runtime database yet.
- No live daemon.
- No real tool execution sandbox.
- No vector or graph memory.
- No self-generated skill promotion.
- No benchmark suite for optimizer quality.

## Next Recommended Tasks

- Add SQLite persistence for memory and run history.
- Add richer task graph validation and cycle handling.
- Build optimizer benchmarks and compare against naive baselines.
- Add an approval queue and audit log persistence.
- Add model catalog configuration instead of hardcoded provider examples.

