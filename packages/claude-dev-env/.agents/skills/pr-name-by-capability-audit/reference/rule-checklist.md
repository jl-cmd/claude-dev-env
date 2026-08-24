# Name-by-capability rule (skill-local)

Prefer `docs/agents/name-by-capability.md` when that file exists in the worktree. This file is the fallback so audits still run when the docs PR has not merged yet.

## Rule

Name packages and modules for the **reusable work they perform**. Put a workflow or motive word (`cert`, `portal`, `export`, a product name, …) in the name only when that surface exists **solely** for that driver.

1. **Capability name first.** Prefer names that say the operation (replace an asset slot, rewrite a color UID, send an email, locate a folder on disk, …).
2. **Drivers stay at the edge.** Queue drains, report parsers, and other workflow-only shells may keep the workflow word. Libraries they call use capability names.
3. **Orchestrators apply capabilities.** When several operations run on one artifact, one apply/orchestrator module owns stage → apply in order → result. Callers that know *why* map intents onto a registry of capability adapters.
4. **Extend the capability, then wire the driver.** New use cases add or extend a capability adapter, then teach the driver which inputs map to it.

## Checklist before accepting a new or renamed path

A driver word in the name plus reuse by another workflow is a **violation**.

1. Would another workflow reuse this? When yes, name the package/module for the shared action.
2. Does the name state the action or artifact change?
3. Is any motive word reserved for driver-only code?

## Driver / motive words (non-exhaustive)

Treat these as driver words when they appear in a package or module name for reusable library code:

- `cert`, `cert_fix`, `cert_closeout`
- `portal`, `export`, `submission`, `discount`
- Product or campaign names used as a motive rather than an operation

## What to score on a PR

| Signal | Score when |
|--------|------------|
| New package/dir | Path segment carries a driver word |
| Renamed package/module | Old or new name carries a driver word on capability code |
| New module under an existing package | File/module stem carries a driver word for a general op |
| PR title / scope | Frames a general shared capability change with a driver/motive word |
| Unchanged misnamed package | Score when this PR **expands** the offense (new public API, new callers); otherwise list under Notes as out-of-diff context |
