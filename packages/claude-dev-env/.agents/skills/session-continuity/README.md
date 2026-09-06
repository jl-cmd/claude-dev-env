# Session-continuity companion

This companion preserves scoped user requirements in a separate durable record. The pstack-owned Poteto Mode source stays unchanged. Full three-host acceptance remains open until installed-host checks pass. Cursor also has an identified prompt-only activation gap.

## Install

Run a full claude-dev-env install so this shared skill is published under the install's canonical agents home. For the default profile, that is `~/.agents/skills/session-continuity`. A named Claude profile uses the sibling `<profile>.agents` home, as defined by `bin/resolve-install-root.mjs`.

Then run this one-time wiring step from that installed directory:

```sh
python install.py
```

This command wires the companion hooks. The main CDE installer does not call this feature-specific installer. Selective `--only core` installation does not currently include this skill. Installing this directory directly also works, with the absolute pstack source selected below.

The installer merges its own commands into Claude's `settings.json`, Codex's `hooks.json`, and Cursor's version-1 `hooks.json`. It preserves other owners' settings and handlers. `CLAUDE_CONFIG_DIR` and `CODEX_HOME` are honored. Use `--claude-home`, `--codex-home`, and `--cursor-home` for explicit destinations, and `--hosts claude,codex` to omit the limited Cursor adapter. Run installation while those settings are not being edited elsewhere.

The pstack skill is externally owned. Default lookup accepts exactly one installed source at `skills/pstack/poteto-mode/SKILL.md` or `skills/pstack/skills/poteto-mode/SKILL.md`. An ambiguous or missing installation fails visibly. `--poteto-source /absolute/path/SKILL.md` selects the actual source the host loads, including a plugin-cache installation. This command neither copies nor edits it. Confirm that the selected source is the host's actual Poteto source before trusting the hooks.

Restart the hosts and approve the new hooks through their normal trust mechanisms. Codex requires review with `/hooks`. Claude needs a version exposing `UserPromptExpansion`; older versions do not cover direct slash-command expansion. Current capability documentation was inspected on September 6, 2026.

Remove this feature's hook entries with `python install.py --remove` before uninstalling the shared skill. Its installation manifest records only its own commands. Durable session data remains available for explicit retention or deletion. Host trust prompts still apply.

## Invocation and discovery

| Host | Initial activation wiring | Recovery wiring | Current qualification |
| --- | --- | --- | --- |
| Claude Code | `UserPromptExpansion` for `/pstack:poteto-mode` and `/poteto-mode`; `UserPromptSubmit` for recognized direct natural-language directives | `SessionStart`, including resume and compact, using `session_id` | Adapter/configuration tests only; actual host expansion, delivery, and source reads need observation |
| Codex | Synchronous `UserPromptSubmit` with a recognized first-line explicit directive | `SessionStart`, including resume and compact, using `session_id` | Actual prompt representation for the installed skill picker, native `$` tokens, and source loading needs observation |
| Cursor local IDE | `beforeSubmitPrompt` records a recognized invocation; `preToolUse` denies the first dependent tool and sends the complete companion body as `agent_message` | `sessionStart` injects existing state; `preCompact` rearms first-tool delivery; later recognized host prompts also rearm it | This is a tool-feedback adapter. Prompt-only turns, Custom Mode selection without a recognized prompt, cloud lifecycle gaps, and resume without a rearming event remain unsupported |

The parser accepts a complete first-line `Use`, `Activate`, `Enable`, or `Apply Poteto Mode` directive, optionally ending in `for this task`, `for this turn`, or `for this entire session`. `Poteto Mode applies for this entire session` is accepted. The user's spelling `Potato Mode` is accepted only in these natural-language directives; the skill is still named Poteto Mode. Upstream's bare `poteto` form is accepted. Embedded mentions, quoted lines, blockquotes, code fences, indented code, transcripts, and tool output are excluded.

Claude's real command-expansion event accepts the canonical command name with arbitrary existing arguments. Claude slash text in `UserPromptSubmit` is left to that expansion event. Codex documents `$` mentions and the `/skills` picker. The adapter parses `$poteto-mode` and `$pstack:poteto-mode` on Codex, and `/poteto-mode` and `/pstack:poteto-mode` on Cursor, when they occupy the complete first directive line, with the same optional scope. Installed picker representations are unverified. Other natural-language wording and invocation representations require observation before extending this conservative parser.

The hook loads the companion body's current bytes into its response, alongside the unchanged Poteto invocation. It reports the exact saved path, commits the record, reads it back, and includes that readback. The companion requires `load`, reconciliation, source reads, and acknowledgement before dependent work. The companion is an agent workflow. A receipt is not proof of compliance.

Records live at:

```text
<canonical-agents-home>/session-continuity/<host>/<sha256(native-session-id)>.sqlite3
```

For Cursor, the native key is `conversation_id`, not the per-turn `generation_id`. A profile's physical shared-skill location supplies its agents home. `--state-root` explicitly selects a different stable root for deployment or tests. SQLite transactions and revision checks prevent partial writes and stale updates. Separate databases isolate concurrent sessions even in one repository. Local permissions are private where the operating system supports POSIX modes; Windows deployments should verify the user's directory ACLs.

Discovery requires only the host-provided identity and the installed hook configuration. No conversation-supplied record path, repository-wide pointer, transcript parsing, or most-recent-file search is used. New identities have no state. An explicit handoff creates an independent record for the exact target identity before that target starts. Cross-machine or cross-profile transfer requires deployment of the selected state and source paths. Transfer is explicit.

## Updating and loading

The runtime actions are `show`, `load`, `update`, `acknowledge`, `deactivate`, and `handoff`. Global options are `--host`, `--session`, and optionally `--state-root`. Updates use `--data` with JSON and the current `expected_revision`. The skill body describes the record shape and workflow. The host records later direct user messages as evidence. The agent reconciles their actual directives, adds subsequently invoked skills, and replaces superseded rules. Evidence is never automatically promoted to authoritative rules.

Every source load reads the authoritative file. Changed sources return accepted and observed hashes plus a textual diff. Unavailable files return an explicit error entry and cannot be acknowledged. A source changed between load and acknowledgement requires another load. Snapshot hashes support comparison, never silent fallback to obsolete instructions. Deactivated records are tombstones and do not recover. A subsequent explicit Poteto invocation begins a fresh requirement set, preserving no ended rules from the prior activation.

## Evidence and remaining acceptance

`test_session_continuity.py` runs the actual generated hook commands as subprocesses with documented host-shaped payloads. It covers configuration installation, context response bodies, exact path/readback, separate-process discovery without a supplied record path, current source content, corrections, additional skills, changed/missing sources, repeated invocation, concurrent sessions, deactivation, explicit handoff, and negative quoting tests. It asserts Cursor's prompt-only gap.

These tests are repository adapter tests. They run without Claude, Codex, Cursor, or a model. Installed-host transcripts and UI traces are absent. The development container has Python and Node but none of those three host executables. GitHub Actions runs the existing repository checks when this draft PR opens.

For each installed host, capture its version, exact command/picker invocation, active hook configuration and trust state, native session identity, and host debug/event trace. Verify that the unchanged Poteto source expands, the hook fires during the same invocation, the full companion body reaches the agent, and the agent actually reads the record and all required sources before dependent work. Then compact and resume the same identity without putting a record path in the conversation. Observe discovery and repeated source reads. Repeat in a second concurrent session and after deactivation. Include a quoted invocation as a negative control. Reproduce Cursor's prompt-only and Custom Mode cases; keep them failed acceptance cases.

## Capability sources

- Canonical Poteto source: https://github.com/cursor/plugins/blob/main/pstack/skills/poteto-mode/SKILL.md
- Repository pstack ownership: `scripts/refresh_pstack_plugin_skills.mjs` and `bin/resolve-install-root.mjs`.
- Claude direct skill expansion, prompt context, and lifecycle: https://code.claude.com/docs/en/hooks
- Codex hook schemas, synchronous context, trust, and lifecycle: https://developers.openai.com/codex/hooks/
- Cursor prompt output limits, tool denial feedback, and lifecycle: https://cursor.com/docs/hooks
- Codex explicit skill invocation and policy: https://developers.openai.com/codex/skills/
- Cursor slash skills and persistent Custom Modes: https://cursor.com/docs/skills
