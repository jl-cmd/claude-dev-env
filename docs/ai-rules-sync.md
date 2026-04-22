# AI Rules Sync

`jl-cmd/claude-code-config` is the single source of truth for AI code-review rules.
Every push to `AGENTS.md` on `main` runs the fan-out dispatcher, which
notifies every target repository (including **this** repo) to run the listener.

In **downstream** repos, the listener writes both:

- `AGENTS.md` — read by tooling that consumes AGENTS.md (including Copilot)
- `.cursor/BUGBOT.md` — read by Cursor Bugbot ([docs](https://cursor.com/docs/bugbot))

In **`jl-cmd/claude-code-config` only**, the canonical AGENTS file is edited on `main` directly;
the listener updates **`.cursor/BUGBOT.md` only** so it never overwrites the headerless source
with a generated header.

The two mirrored files are always byte-identical modulo their auto-generated headers.
The source repo always wins; manual edits to any destination are treated as errors.

---

## Architecture

```
jl-cmd/claude-code-config
  AGENTS.md  ← edit only here
           │
           │  push to main
           ▼
  .github/workflows/fan-out-ai-rules.yml  (dispatcher)
           │
           │  POST /repos/{owner}/{repo}/dispatches  (one per target)
           ▼
  Each target repo (including jl-cmd/claude-code-config):
  .github/workflows/sync-ai-rules.yml  (listener)
           │
           ├─▶  AGENTS.md  (downstream repos only)
           └─▶  .cursor/BUGBOT.md  (all targets; canonical repo: this path only)
                        │
                        │  ~60s later
                        ▼
  Dispatcher reconciliation poll
  → per-repo summary: synced / drift-failed / listener-missing / opted-out
```

---

## Editing rules

**Always edit `AGENTS.md` in `jl-cmd/claude-code-config`.**
Never edit destination files directly — any manual change is detected as drift, fails the
next sync run, and opens a GitHub Issue in the affected repo.

---

## Drift policy

When a destination file's body (header stripped) no longer matches the SHA recorded in the
most recent bot commit touching that file, the listener:

1. Annotates the run with `::error::` per drifted path.
2. Writes the diff to `$GITHUB_STEP_SUMMARY`.
3. Opens a GitHub Issue in the affected repo titled
   `AI rules sync: drift detected in <path>`.
4. Leaves both destination files unmodified.

No overwrite happens until a human resolves the conflict and re-runs the sync.

---

## Opt-out

Create `.github/sync-ai-rules.optout` in any repo to exclude it from the sync.
The file content is free-form (use it to document why the repo is excluded).

- The dispatcher skips opted-out repos and records them as `opted-out` in the summary.
- If the listener is triggered directly (e.g., via `workflow_dispatch`) while the sentinel
  exists, it exits cleanly with no changes.

Deleting the listener workflow file is **not** the recommended opt-out mechanism — it is
invisible to the dispatcher, which would then flag the repo as `listener-missing`.
The sentinel file is auditable and appears cleanly in reconciliation summaries.

---

## Onboarding a new repo

Run the bootstrap script (idempotent; safe to re-run):

```bash
./scripts/bootstrap-listeners.sh
```

Or, for a single repo:

```bash
./scripts/bootstrap-listeners.sh --owner JonEcho --skip all-other-repos
```

Or copy manually:

```bash
# From the root of claude-code-config:
gh repo clone owner/target-repo /tmp/target
mkdir -p /tmp/target/.github/workflows /tmp/target/.github/scripts
cp .github/workflows/sync-ai-rules.yml /tmp/target/.github/workflows/
cp .github/scripts/sync_ai_rules.py    /tmp/target/.github/scripts/
```

Then commit and push a PR in the target repo.

---

## Offboarding a repo

Preferred: create `.github/sync-ai-rules.optout`.
Alternative: delete `.github/workflows/sync-ai-rules.yml`
(the dispatcher will flag the repo as `listener-missing` on the next run).

---

## Rollback

Revert the source file in `jl-cmd/claude-code-config` and push to `main`.
The dispatcher will fan out the reverted content. Drift detection does **not** fire on the
revert because the bot authored the previous version and the stored SHA matches.

---

## Manual operations

**Sync a single repo:**

```bash
gh workflow run sync-ai-rules.yml -R owner/repo
```

**Force-sync over existing human content (first-sync override):**

```bash
gh workflow run sync-ai-rules.yml -R owner/repo -f force_initial_overwrite=true
```

**Full re-sync of all repos:**

```bash
gh workflow run fan-out-ai-rules.yml -R jl-cmd/claude-code-config
```

---

## GitHub App setup

The dispatcher workflow authenticates as a GitHub App to obtain installation tokens with
`contents: write`, `metadata: read`, `actions: read`, and `issues: write` permissions.
Target repos use only the default `GITHUB_TOKEN` — no secrets are needed there.

### Steps

1. Create a GitHub App owned by `JonEcho`.
   - Permissions: `Contents: Read and write`, `Metadata: Read-only`,
     `Actions: Read-only`, `Issues: Read and write`.
2. Install the App on the **JonEcho** user account.
3. Install the App on the **jl-cmd** organization.
4. Generate a private key for the App.
5. In `jl-cmd/claude-code-config` repository secrets, set:
   - `APP_ID` — the numeric App ID shown on the App's settings page.
   - `APP_PRIVATE_KEY` — the full PEM private key content.

To regenerate the private key: go to the App's settings page → Private keys →
Generate a private key. Update the `APP_PRIVATE_KEY` secret with the new PEM content.

---

## Weekly reconciliation cron

Every Monday at 12:00 UTC the dispatcher workflow re-dispatches to all targets.
This catches any missed syncs (e.g., repos that were offline or rate-limited) and flags:

- Repos whose most recent `sync-ai-rules.yml` run is older than 14 days.
- Repos where the listener workflow file is missing.

These appear in the "Stale listeners" section of the dispatcher's job summary.

---

## Troubleshooting

**Drift error in a target repo**
Open the failed `sync-ai-rules` run in that repo. The summary shows which file drifted
and the differing SHA256 values. Either revert the manual change or delete the file and
re-run with `force_initial_overwrite=true`.

**Permission error dispatching**
Ensure the GitHub App is installed on both `JonEcho` and `jl-cmd` with `Contents: write`
permission. Check that `APP_ID` and `APP_PRIVATE_KEY` secrets are set correctly in
`jl-cmd/claude-code-config`.

**Listener not installed**
The dispatcher records `listener-missing` for repos that have no `sync-ai-rules.yml`
workflow. Run `scripts/bootstrap-listeners.sh` to install it.

**Dispatch fires but listener never runs**
`repository_dispatch` events only trigger workflows on the default branch. Confirm the
listener workflow is merged to the default branch (not only on a PR branch).

**GitHub App token expires during a long dispatch run**
Installation tokens are valid for one hour. If the dispatcher has more than ~4,000 repos
to process (unlikely), it may need to re-mint the token. At normal scale this is not an
issue.

**Agent-gate blocks `mcp__obsidian__*` tools during a session**
Run `/mcp` to reconnect the agent-gate MCP server.
