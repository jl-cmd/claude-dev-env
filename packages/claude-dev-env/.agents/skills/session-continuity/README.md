# Session continuity companion

Status: draft implementation. Claude and Codex adapters have repository-level
contract tests. Installed-host activation, reload, and agent compliance remain
unverified. Cursor automatic activation is unsupported by this implementation.
All three hosts remain part of the requested outcome.

## The persistence failure

A skill invocation can remain only in conversation context. Compaction can then
lose its duration, later corrections, or the instruction to reload it. This
companion saves user-scoped requirements under a stable host-session key and
returns the current skill contents during supported recovery callbacks.

## Ownership and setup

Pstack owns `Poteto Mode`, directory `poteto-mode`. Its source description names
`poteto`, `/poteto-mode`, and requests to work in that style. This repository's
pstack manifest refresher exposes namespaced Claude skills and leaves pstack
content with its existing owner. The companion edits none of that source,
manifest, invocation code, or model policy.

From this checkout, run the full existing installer, then the focused hook setup:

```sh
node packages/claude-dev-env/bin/install.mjs
node packages/claude-dev-env/bin/install-session-continuity.mjs
```

The full installer publishes this skill under the canonical agents home. This
setup is required once for each selected host/profile, not once per invocation.
The existing selective `--only core` list does not include the companion in this
draft. Use the full install above. Plugin-only installations need the same
canonical installed skill before this setup can run.

The setup defaults to `claude codex`. Pass either host name to configure it alone.
It uses `bin/resolve-install-root.mjs`, including `CLAUDE_CONFIG_DIR` and
`CODEX_HOME`. It merges only its own hook groups into Claude `settings.json` and
Codex `hooks.json`, preserves other settings, writes a one-time backup before
changing an existing config, and reads each result back. Re-running setup is
idempotent. Another profile's continuity command in the same host config causes
an explicit refusal that keeps its existing registration in place.

Review and trust the new hooks in each installed host. Codex requires explicit
hook trust; configuration alone does not make an untrusted hook run. Restart an
already-open host when needed to load its new configuration. `node` must be on
the host's PATH. Setup does not bypass trust or claim a minimum host version
that has not been tested. Use builds exposing the documented events below.

## Trigger forms and source selection

| Host | Adapter input | Forms recognized by the companion |
| --- | --- | --- |
| Claude Code | `UserPromptExpansion`, `expansion_type=slash_command` | Existing `poteto-mode` and `pstack:poteto-mode` command names |
| Claude Code | `UserPromptSubmit` | A leading `/poteto-mode` or `/pstack:poteto-mode`; exact natural forms below |
| Codex | `UserPromptSubmit` | A leading `$poteto-mode`, `$pstack:poteto-mode`, or `[$pstack:poteto-mode](path)` skill reference; exact natural forms below |
| Cursor | No automatic adapter installed | The inspected prompt and lifecycle hooks do not establish the required timing |

Natural forms include bare `poteto`, `Use Poteto Mode`, `Activate Poteto Mode`,
`Invoke Poteto Mode`, and `Poteto Mode applies for this entire session`. Exact
natural forms can end with `for this task` or `for this entire session`. A leading
command can have task text after it. Only an exact scope suffix changes automatic
scope; the agent records more complex user scope through the update workflow.
Free-form style requests and host UI forms that omit the skill token from the
prompt remain unverified. The adapter's recognition is not proof that every host
resolves every form as a native skill invocation.

The companion does not define a `/potato-mode` alias or rename `poteto-mode`.
Quotations, fenced examples, indented code, discussion, imported transcripts, and
tool-result callbacks do not independently activate the companion. Subsequent
user prompts become pending evidence, not automatic rules. The agent commits
only explicit user directions. The update command also rejects evidence found
only inside marked quotations, code, or imported blocks. Semantic interpretation
of unmarked prose remains an agent responsibility, not a proven security boundary.

The default Poteto source is one of these installed locations:

```text
<agents-home>/skills/pstack/poteto-mode/SKILL.md
<agents-home>/skills/pstack/skills/poteto-mode/SKILL.md
```

Two different existing sources cause an explicit error. Set `CDE_POTETO_SOURCE`
in the host environment to select the exact authoritative installed file when
needed, including shadowed or plugin-cache installations. Setup and tests do not
verify the host's actual native skill resolution. Additional named skills use
their absolute local source paths. Unavailable local sources are reported during
reload. Remote-only sources need an explicit supported loading step; the helper
performs no network fetch and claims no remote source was loaded.

## Storage and discovery

```text
<agents-home>/state/session-continuity/<host>/<sha256(host-session-id)>.json
```

The default agents home is `~/.agents`. Named profiles use the agents home from
the existing install-root resolver. `CDE_CONTINUITY_ROOT` explicitly overrides
the state root for an isolated test or selected shared installation. The helper
uses the host's callback `session_id`, never a recent-file search, current
working-directory guess, or path carried only in conversation messages.

Writes use a per-record exclusive lock, a private temporary file, file sync, and
atomic replacement. Each write reads the record back. Revision checks reject
stale agent writes. Separate sessions in one repository have separate records.
A failed or interrupted write leaves prior state intact. A leftover lock requires
confirmation that its writer has ended before removal. Files use mode `0600`
and directories use `0700` where the filesystem honors those modes; Windows
access follows the user's profile ACLs. Runtime records contain pending user
messages and source comparison snapshots and stay outside the repository.

| Situation | Discovery and restoration |
| --- | --- |
| First recognized invocation | Hook creates the record, returns its exact path and read-back, and includes the complete companion instructions |
| Later user prompt | Same session key; pending evidence is saved and the companion directs the agent to reconcile it before dependent work |
| Claude/Codex startup or resume | `SessionStart` with the same id finds the active record and reads current active skill sources |
| Claude/Codex compaction | `SessionStart` with source `compact` reloads the same record and sources |
| New unrelated conversation | A new id has no record and inherits nothing |
| Clear | The same-id record is deactivated; a new id starts empty |
| Explicit handoff | The source command binds a snapshot to a known destination host/id; its next supported start callback discovers that record |
| Explicit deactivation | An inactive tombstone suppresses recovery until another explicit invocation creates a fresh active set |

Handoff requires a known target id supplied by the host or coordinator. Automatic
creation of that target conversation and capture of its id are not implemented.
Resuming a different conversation without an explicit handoff binding does not
restore this record. Concurrent source and target sessions write independent
snapshots after handoff.

## Host delivery and its limits

Claude's expansion event handles directly typed slash commands, which bypass
`PreToolUse` on the Skill tool. Codex uses its documented prompt callback. Both
adapters emit `hookSpecificOutput.additionalContext`, including actual current
source text. They do not call a host-native Skill tool. The agent must read any
host-truncated source in full before dependent work. Missing sources produce an
explicit unavailable message. Changed sources include current contents and a
bounded before/after comparison. Stored snapshots are for comparison only.

Cursor's `beforeSubmitPrompt` returns `continue` and a blocked-user message, not
agent context. Its `preToolUse` can send agent context by denying a pending tool,
and `postToolUse` can inject context after a tool runs. That does not cover a
reply-only invocation before dependent work. `sessionStart` is fire-and-forget
when a composer conversation is created; `preCompact` cannot block or modify
compaction. Startup reminders, first-tool-only gates, or stop-hook follow-ups
would weaken the requested contract. This draft installs none of those as a
substitute. Shared storage accepts a `cursor` namespace for explicit operations;
that is not automatic Cursor support.

Automatic prompt capture and source emission are code paths. Selecting actual
user rules, checkpointing, loading shortened sources, and following instructions
are agent obligations. This implementation does not prove or force agent
compliance merely because a callback ran.

## Validation and remaining installed-host proof

Run the repository contract tests:

```sh
node --test packages/claude-dev-env/.agents/skills/session-continuity/continuity.test.mjs \
  packages/claude-dev-env/bin/install-session-continuity.test.mjs
```

The existing JavaScript GitHub Actions job discovers the same test file through
its `.agents/skills/**/*.test.mjs` pattern. Tests install copies in isolated
fixtures, read generated hook configurations, execute their actual command lines
with independently authored documented event payloads, and check emitted skill
contents, read-back, identity-only recovery, scope changes, new skills,
corrections, source failures, concurrent sessions, handoff, and deactivation.
Fixtures contain small synthetic skill sources. These are repository adapter
tests, not Claude, Codex, or Cursor runtime transcripts.

For each supported installed host, record its version, effective trusted hook
configuration, native Poteto source hash, the user's normal invocation, actual
callback delivery, the agent's source reads, and the first dependent action.
Capture the exact saved path and read-back. Then remove earlier context through
real compaction and a same-conversation restart, supply no record path, and
capture discovery plus source reload before dependent work. Repeat with a later
correction, a new skill, changed/missing sources, simultaneous sessions,
quoted-only mentions, explicit handoff, deactivation, and reactivation. Keep
Poteto's source hash unchanged throughout. Cursor needs a supported pre-work
loading mechanism before equivalent installed-host acceptance can be run.

## Primary references checked on 2026-09-06

- [Pstack Poteto Mode source](https://github.com/cursor/plugins/blob/main/pstack/skills/poteto-mode/SKILL.md)
- [Claude Code hooks](https://code.claude.com/docs/en/hooks)
- [Codex hooks](https://developers.openai.com/codex/hooks)
- [Cursor hooks](https://cursor.com/docs/hooks)
- Repository ownership: `scripts/refresh_pstack_plugin_skills.mjs` and `bin/resolve-install-root.mjs`.
