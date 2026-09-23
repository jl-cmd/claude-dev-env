# Hook lifecycle

The installed package registers SessionStart, UserPromptSubmit, PreToolUse, PostToolUse, SubagentStart, SessionEnd, and InstructionsLoaded hooks, and no Stop hook. A hook adds context or rewrites a tool input. Policy checks run as linters and continuous-integration jobs.

## Sub-features

- `hook-roster` puts every `hooks/hooks.json` entry into the installed `settings.json`, with paths under the installed hooks tree.
- `session-start-envelope` returns a `SessionStart` envelope with `additionalContext` from `working_style_prompt.py`.
- `bash-rewrite` returns a `PreToolUse` envelope that allows a `git show <rev>:<path>` call and prefixes `MSYS2_ARG_CONV_EXCL`.
- `poteto-spawn` opens an `Agent` or `Task` prompt with the poteto-mode invocation.
- `poteto-codex-spawn` opens a Codex `spawn_agent` message with `$pstack:poteto-mode`.
- `poteto-reminder` tells a session to load poteto-mode after a compaction, at a workflow helper start, and on a user turn before the skill loads.
- `policy-lint-timing` runs policy checks from `cde lint` and CI only.

## How to get to it (user POV)

- Install the package, then start a Claude Code or Codex session.
- Spawn a subagent through `Agent`, `Task`, or Codex `spawn_agent`.
- Compact a session, start a Workflow helper, or submit a prompt.
- Run a Bash `git show` command with a `<rev>:<path>` argument.

## Driving it with the install playtest

Preconditions:

- `node` and `python3` are on `PATH`.
- `<scratch>` is an empty directory under the OS temporary root or the session scratchpad.

- **Install and start two hooks.** Run `node packages/claude-dev-env/scripts/ci/install-playtest.mjs --home <scratch> --evidence <scratch>-evidence` from the repository root. Exit code `0`. Three `[PASS] playtest` lines name `install`, `session_start_hook`, and `blocking_hook`, each with an evidence path and a `sha256=` digest.
- **Read the roster.** Open `<scratch>/.claude/settings.json`. `hooks.PreToolUse` has an `Agent|Task` group, `hooks.SessionStart` has a `compact` group, and `hooks.SubagentStart` has a `workflow-subagent` group. Each group runs `<scratch>/.claude/hooks/session/skill_loaded_reminder.py`. No `Stop` key is present.
- **Spawn rewrite.** Pipe `{"hook_event_name":"PreToolUse","tool_name":"Agent","tool_input":{"prompt":"Reply leaf."}}` into `python3 <scratch>/.claude/hooks/session/skill_loaded_reminder.py`. Stdout is one envelope with `permissionDecision` `allow` and an `updatedInput.prompt` that starts `Before any other work, invoke the pstack:poteto-mode skill`.
- **Self-loading agent.** Add `"subagent_type":"pstack:poteto-agent"` to the same `tool_input`. Stdout is empty and the exit code is `0`.
- **Codex spawn.** Pipe `{"hook_event_name":"PreToolUse","tool_name":"spawn_agent","tool_input":{"message":"Fix it."}}` into `python3 <scratch>/.codex/hooks/session/skill_loaded_reminder.py`. `updatedInput.message` is `$pstack:poteto-mode` followed by a blank line and `Fix it.`.
- **Compaction reminder.** Pipe `{"hook_event_name":"SessionStart","source":"compact"}`. The `SessionStart` envelope's `additionalContext` starts `The context was just compacted`. The same payload with `"source":"startup"` prints nothing.
- **Workflow helper.** Pipe `{"hook_event_name":"SubagentStart","agent_type":"workflow-subagent"}`. The `SubagentStart` envelope's `additionalContext` starts `The pstack:poteto-mode skill is not loaded`.
- **User turn.** Pipe `{"hook_event_name":"UserPromptSubmit","transcript_path":"<file>"}`. A transcript without a `Skill` call for `pstack:poteto-mode` returns the not-loaded reminder. A transcript whose last such call follows its last `compact_boundary` prints nothing.
- **Proof.** Keep `<scratch>-evidence`, the three playtest lines, and the stdout of each piped payload. Remove `<scratch>` after the run.

## Gotchas

- A hook never returns `deny`, `block`, or `ask`. A rewrite is `allow` with `updatedInput`. A linter fails only its own command.
- Empty stdout with exit `0` is the pass for a quiet branch. Check the exit code before you read silence as a pass.
- A missing or unreadable transcript counts as not loaded, so `UserPromptSubmit` prints the reminder.
- `--home` keeps the scratch home after the run. Without `--home`, the playtest removes its own scratch home.
- `--skip-install` grades the tree already in `--home`. Use it to read back a broken install. A fresh run without it reinstalls over the break.
- A roster line that names `test_failure_recorder.py` or `msys_path_conversion_advisor.py` comes from a stale install. A reinstall removes every path in `RETIRED_HOOK_REGISTRATION_RELATIVE_PATHS`.
