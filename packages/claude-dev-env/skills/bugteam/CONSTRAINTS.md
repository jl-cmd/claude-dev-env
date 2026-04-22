# Bugteam — invariants and design rationale

## Constraints

- **Agent teams required, not parallel subagents.** The skill MUST use Claude Code's agent teams feature (`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`). Spawning `code-quality-agent` and `clean-coder` as parallel subagents from the lead's context = fail; the clean-room property requires independent teammate sessions.
- **Orchestrator-only `TeamCreate`.** Only the lead session (this session, when `/bugteam` is invoked) calls `TeamCreate`. Teammates never call `TeamCreate` — if a teammate's spawn prompt instructs it to, that is a skill defect. When additional parallel work is needed (e.g., parallel auditors from loop 4 onward, supplementary audit of adjacent files), the lead spawns additional teammates into the EXISTING team by passing the current `team_name` to every `Agent(...)` call. Multiple teammate "sets" live inside one team under one orchestrator. The runtime enforces this: `TeamCreate` called while the session already leads a team returns the error `Already leading team "<name>". A leader can only manage one team at a time. Use TeamDelete to end the current team before creating a new one.` — direct quote from the runtime's response when this invariant is violated.
- **One team per invocation, multi-PR supported.** All PRs in a single /bugteam invocation share one team created by the orchestrator. Per-PR identity lives in the teammate name prefix (`bugfind-pr<N>-loop<L>` / `bugfix-pr<N>-loop<L>`) and the `<team_temp_dir>/pr-<N>/` subfolder containing that PR's git worktree, diff patches, and outcome XML files.
- **Grant before any spawn, revoke before any return.** Step 0 grants project `.claude/**` permissions; Step 5 revokes. Both are mandatory. Revoke runs on every exit path including error, cap-reached, and stuck.
- **Fresh teammate per loop.** Both bugfind and bugfix are spawned new each loop and shut down after their action. Reusing a teammate across loops accumulates context inside that teammate's window — defeats clean-room.
- **One up-front confirmation = whole cycle.** The `/bugteam` invocation authorizes the entire cycle; every subsequent decision runs on that single authorization.
- **10-loop hard cap.** Counted as **AUDIT** completions (increment in Step 3). Standards-fix passes before an audit do not advance `loop_count`. Worst case includes extra clean-coder spawns for the code-rules gate.
- **Code rules gate before every AUDIT.** Run `scripts/bugteam_code_rules_gate.py` until exit **0** before spawning **bugfind**. Same `validate_content` logic as `hooks/blocking/code_rules_enforcer.py`.
- **Clean-room audits, every loop.** Each bugfind teammate's spawn prompt contains only the PR scope, audit rubric, and the current loop number. Prior loop history stays in the lead.
- **Targeted fixes.** Each fix teammate sees ONLY the most recent audit's findings. Prior loops are invisible to the fix teammate.
- **Opus 4.7 at xhigh effort for both teammates.** Both `Agent(...)` spawns pass `model="opus"`, which resolves to Opus 4.7 on the Anthropic API. Opus 4.7's default effort level in Claude Code is `xhigh` (https://code.claude.com/docs/en/model-config — *"On Opus 4.7, the default effort is `xhigh` for all plans and providers."*), so no `effort` override is needed at spawn time. Effort is set per-subagent in YAML frontmatter, not via the `Agent` tool's parameters; `code-quality-agent` and `clean-coder` rely on the model default. The trade vs Sonnet is higher per-loop cost in exchange for deeper audit recall and stronger fix correctness on bug-hunting work, which the per-PR loop economics tolerate (10-loop hard cap bounds total spend).
- **Fix teammate receives the latest audit as its input contract.** Passing the audit's findings to the fix teammate is the input contract — each loop's fix run operates on the current audit's output and only that.
- **One commit per fix action.** Loops produce one commit per loop, not one per bug.
- **Linear branch, fixed PR base.** Every loop appends one forward-only commit; existing commits and the PR base stay intact throughout the cycle.
- **Lead-only cleanup.** Per the docs: *"Always use the lead to clean up. Teammates should not run cleanup because their team context may not resolve correctly, potentially leaving resources in an inconsistent state."* This session is the lead, and cleanup runs here only.
- **Cleanup the per-team scoped temp directory on exit.** The resolved `<team_temp_dir>` (absolute literal captured in Step 2) is deleted entirely so no loop patches leak between runs.
- **Cleanup all `.bugteam-*` files on exit.** `.bugteam-loop-*.patch`, `.bugteam-loop-*.outcomes.xml`, `.bugteam-final.diff`, `.bugteam-original-body.md`, `.bugteam-final-body.md`. Working directory ends clean.
- **Teammates own audit/fix comment posting.** Bugfind posts ONE per-loop review (parent body + child finding comments in a single batched POST, with review-fallback to a top-level issue comment). Bugfix posts the fix replies after committing. All comment, review, and reply POSTs belong to the teammates; the lead's single PR-write action is the final description rewrite at Step 4.5.
- **Lead owns the final PR description rewrite only** (Step 4.5), and only via the `pr-description-writer` agent. The lead does not compose the description inline.
- **One review per loop, findings as child comments of that review.** Each loop posts a single pull-request review whose body is the loop header and whose `comments[]` are the anchored findings. Each loop's review stands alone — one review created per loop, fully self-contained on the PR conversation.
- **PR description rewrite on every exit.** Step 4.5 runs on `converged`, `cap reached`, and `stuck`. On `error`, the rewrite is best-effort; if it fails, surface the error in the final report and continue to revoke.
- **Outcome XML, not JSON.** Both teammates write structured outcome data (findings or fix outcomes) to `.bugteam-loop-<N>.outcomes.xml`. The lead reads these files between actions. XML chosen for parser robustness against multi-line, special-character, and quoted reason fields.

## Why this design

The three sibling skills compose, but `/bugteam` solves a problem they cannot solve in sequence:

- `/findbugs` audits once and stops.
- `/fixbugs` fixes the findings of one audit and stops.
- A human-driven `/findbugs` → `/fixbugs` → `/findbugs` → `/fixbugs` cycle works but requires the user to drive it.

`/bugteam` automates that cycle. The clean-room property is preserved by spawning a fresh audit agent each loop with no inherited context — every audit is independent of the prior loop's verdict. The 10-loop cap is the safety: pathological cases (audit agent oscillating, fix agent regressing) cannot run away.

The single up-front confirmation is the explicit trade — `/bugteam` is more autonomous than `/findbugs`+`/fixbugs` chained manually. The user accepts that autonomy by typing the command. Stop conditions and the loop log give the user full visibility on exit.
