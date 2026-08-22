# pr-loop

Shared infrastructure for autoconverge PR convergence: XML prompt templates,
portable-driver phase machine scripts under `skills/_shared/pr-loop/scripts/`,
and runtime convergence/Codex scripts under `~/.claude/_shared/pr-loop/scripts/`.
Retired entry skills (`bugteam`, `pr-converge`, and others) are archived under
`packages/claude-dev-env/.agents/skills-archived/` for reference only.

## Subdirectories

| Directory | Role |
|---|---|
| `prompts/` | XML agent prompt templates for internal lenses. |
| `scripts/` | Portable pacer scripts: pacer selection, loop state, portable driver, prompt builders, handoff. |

## Canonical-path stubs (`~/.claude/_shared/pr-loop/`)

Open a stub, then load the `@` target:

| Stub here | Load |
|---|---|
| `audit-contract.md` | `@~/.claude/_shared/pr-loop/audit-contract.md` |
| `audit-reply-template.md` | `@~/.claude/_shared/pr-loop/audit-reply-template.md` |
| `code-rules-gate.md` | `@~/.claude/_shared/pr-loop/code-rules-gate.md` |
| `fix-protocol.md` | `@~/.claude/_shared/pr-loop/fix-protocol.md` |
| `gh-payloads.md` | `@~/.claude/_shared/pr-loop/gh-payloads.md` |
| `post-audit-thread-contract.md` | `@~/.claude/_shared/pr-loop/post-audit-thread-contract.md` |
| `precatch-rubric.md` | `@~/.claude/_shared/pr-loop/precatch-rubric.md` |
| `state-schema.md` | `@~/.claude/_shared/pr-loop/state-schema.md` |
| `worker-spawn.md` | `@~/.claude/_shared/pr-loop/worker-spawn.md` |
| `scripts/RUNTIME_SCRIPTS.md` | `@~/.claude/_shared/pr-loop/scripts/` |

## Key files (live in this tree)

| File | Role |
|---|---|
| `portable-driver.md` | Continuous in-session pacer when Workflow / ScheduleWakeup are absent. |
| `prompts/pr-consistency-audit.xml` | Cross-file consistency audit prompt for autoconverge self-review lanes. |
| `scripts/select_converge_pacer.py` | Maps entry skill + host tool flags to `workflow`, `schedule_wakeup`, or `portable`. |
| `scripts/build_audit_prompt.py` | Assembles audit agent prompts from loop state (portable pacer). |
| `scripts/build_fix_prompt.py` | Assembles fix agent prompts from loop state and findings. |
| `scripts/init_loop_state.py` | Initializes per-PR loop state JSON for portable runs. |
| `scripts/write_audit_outcomes.py` | Writes per-loop audit outcome XML into the workspace. |
| `scripts/write_fix_outcomes.py` | Writes per-loop fix outcome XML into the workspace. |
| `scripts/preflight_worktree.py` | Verifies the working directory is a healthy worktree for the target PR. |
| `scripts/teardown_worktrees.py` | Removes loop worktrees on clean exit. |
| `scripts/write_handoff.py` | Writes durable resume-handoff files under `~/.claude/runtime/pr-loop/<run-name>/`. |
| `scripts/portable_converge_driver.py` | Portable phase machine for autoconverge when `pacer=portable`. |
| `scripts/build_converge_task_list.py` | Step-1 task list for portable runs. |
| `scripts/_path_resolver.py` | Resolves workspace and worktree paths from PR metadata. |
| `scripts/_cli_utils.py` | Shared CLI argument parsing helpers. |
| `scripts/_xml_utils.py` | XML serialization helpers. |
| `scripts/skills_pr_loop_constants/` | Named constants for portable-driver scripts. |

Runtime convergence checks, Codex review, and shared gates live in
`packages/claude-dev-env/_shared/pr-loop/scripts/` (installed to
`~/.claude/_shared/pr-loop/scripts/`).
