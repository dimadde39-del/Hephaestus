# Studio Trust And Approvals

Studio trust settings are local preferences for how much low-risk Workbench
work can proceed without approval spam.

They do not override hard runtime blocks.

## Modes

```text
Manual
Developer
Local Power User
Strict
```

Each mode maps to an existing policy profile and an explicit set of implemented
Workbench rules. The effective profile is displayed in Studio.

## Rules

Rules shown in Studio include:

- read normal repo files;
- search repo;
- inspect repo metadata;
- create coding plans;
- create patch proposals;
- create checkpoints;
- run safe validation;
- apply low-risk documentation patches;
- apply low-risk code patches with validation;
- restore checkpoints;
- install dependencies;
- push Git changes;
- send external messages.

Rules that are not implemented in Phase 5.5B are marked as such. Hard-blocked
rules are disabled.

## Approval Behavior

Safe analysis should not ask permission. Examples:

- normal repo reads;
- repo search;
- repo metadata inspection;
- coding plan creation;
- patch proposal creation;
- checkpoint creation;
- safe validation planning or execution when allowed.

Medium-risk actions require meaningful confirmation. Examples:

- applying a patch batch when trust does not auto-allow it;
- retrying failed validation;
- restoring a checkpoint.

External side effects require explicit confirmation or remain unavailable in
Studio:

- dependency installation;
- Git push;
- deploy/publish;
- external messages.

Destructive/system-level actions remain blocked.

## Pending Decisions

Workbench pending decisions show only meaningful actions:

- approve patch batch;
- retry failed validation;
- restore checkpoint;
- narrow an oversized coding request;
- choose between explicit alternatives.

They do not show file reads, searches, internal memory retrieval, or harmless
planning passes.

Each decision states what will happen, affected repo/files, risk, rollback
availability, external side effects, one primary action, and one cancel action.

## Persistence

Preferences are stored locally in `studio_trust_settings`. The frontend updates
them through:

```text
GET   /api/trust
PATCH /api/trust
```

The backend maps settings to currently supported runtime actions and the active
policy profile. It never lets trust settings bypass destructive blocks.

## Settings Integration

Phase 5.5C surfaces these controls under Settings -> Policy and Trust as well
as the Workbench trust view. The Settings page shows:

- active policy profile;
- current autonomy mode;
- effective permissions;
- hard-blocked actions such as dependency installation, Git push, deployment,
  and external messaging.

Changing trust settings remains local. It does not enable daemon behavior,
unrestricted terminal access, or autonomous coding loops.
