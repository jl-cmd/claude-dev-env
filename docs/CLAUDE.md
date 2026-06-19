# docs/

Persistent reference documentation for the repo's systems and architecture.

## Purpose

Stores long-lived reference material that contributors and Claude sessions read before
touching the systems they describe. Nothing here is auto-generated; all files describe
what the system **is**, not how it got there.

## Files

| File | Role |
|------|------|
| `ai-rules-sync.md` | Complete reference for the `AGENTS.md` fan-out sync system: architecture, editing rules, drift policy, opt-out, onboarding/offboarding, manual operations, GitHub App setup, reconciliation cron, and troubleshooting. Read this before changing `AGENTS.md` or the sync workflows. |

## Subdirectories

| Directory | Role |
|-----------|------|
| `records/` | One-off operator records and historical runbooks that are kept for reference but are not live entry points. |
| `references/` | Deep-reference material: third-party articles, PDFs, and internal design docs that inform architectural decisions. |
| `plans/` | Working planning documents (not committed to the published package). |
