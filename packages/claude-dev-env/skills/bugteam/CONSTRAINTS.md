# Bugteam — invariants and design rationale

## Constraints

- **One run per invocation, multi-PR supported.** All PRs in a single /bugteam invocation share one `run_temp_dir`. Per-PR identity lives in the subagent name prefix (`bugfind-pr<N>-loop<L>` / `bugfix-pr<N>-loop<L>`) and the `<run_temp_dir>/pr-<N>/` subfolder containing that PR's git worktree, diff patches, and outcome XML files.
- **Grant before any spawn, revoke before any return.** Step 0 grants project `.claude/**` permissions; Step 5 revokes. Both are mandatory. Revoke runs on every exit path including error, cap-reached, and stuck.
- **Fresh subagent per loop.** Both bugfind and bugfix are spawned new each loop. Reusing a subagent across loops accumulates context inside that subagent's window — defeats clean-room.
- **One up-front confirmation = whole cycle.** The `/bugteam` invocation authorizes the entire cycle; every subsequent decision runs on that single authorization.
- **10-loop hard cap.** Counted as **AUDIT** completions (increment in Step 3). Standards-fix passes before an audit do not advance `loop_count`. Worst case includes extra clean-coder spawns for the code-rules gate.
- **Code rules gate before every AUDIT.** Run `_shared/pr-loop/scripts/code_rules_gate.py` (resolved via `${CLAUDE_SKILL_DIR}/../../_shared/pr-loop/scripts/code_rules_gate.py`) until exit **0** before spawning **bugfind**. Same `validate_content` logic as `hooks/blocking/code_rules_enforcer.py`.
- **Clean-room audits, every loop.** Each bugfind subagent's spawn prompt contains only the PR scope, audit rubric, and the current loop number. Prior loop history stays in the lead.
- **Targeted fixes.** Each fix subagent sees ONLY the most recent audit's findings. Prior loops are invisible to the fix subagent.
- **Opus 4.7 at xhigh effort for validator and fix subagents.** Single-auditor mode, validator, and fix spawns pass `model="opus"`; parallel-auditor siblings (`-b` through `-k`) pass `model="haiku"`. Opus 4.7's default effort level in Claude Code is `xhigh` (https://code.claude.com/docs/en/model-config — *"On Opus 4.7, the default effort is `xhigh` for all plans and providers."*), so no `effort` override is needed at spawn time. Effort is set per-subagent in YAML frontmatter, not via the `Agent` tool's parameters; `code-quality-agent` and `clean-coder` rely on the model default. The trade vs Sonnet is higher per-loop cost in exchange for deeper audit recall and stronger fix correctness on bug-hunting work, which the per-PR loop economics tolerate (10-loop hard cap bounds total spend).
- **Fix subagent receives the latest audit as its input contract.** Passing the audit's findings to the fix subagent is the input contract — each loop's fix run operates on the current audit's output and only that.
- **One commit per fix action.** Loops produce one commit per loop, not one per bug.
- **Linear branch, fixed PR base.** Every loop appends one forward-only commit; existing commits and the PR base stay intact throughout the cycle.
- **Lead-only cleanup.** Cleanup runs in the lead (this session) only. Step 4 removes the full `<run_temp_dir>` so no loop patches leak between runs.
- **Cleanup all `.bugteam-*` files on exit.** The per-run `<run_temp_dir>` is removed entirely by Step 4, which covers `<run_temp_dir>/pr-<N>/loop-<L>.patch` and `<run_temp_dir>/pr-<N>/loop-<L>-<letter>.outcomes.xml`. The per-loop outcomes XML at `<worktree_path>/.bugteam-pr<N>-loop<L>.outcomes.xml` is removed with the worktree. Step 4.5 deletes `.bugteam-final.diff`, `.bugteam-original-body.md`, and `.bugteam-final-body.md`. Working directory ends clean.
- **Audit/fix comment posting.** The bugfind subagent posts ONE per-loop review (parent body + child finding comments in a single batched POST, with review-fallback to a top-level issue comment). The bugfix subagent posts the fix replies after committing. All comment, review, and reply POSTs belong to the subagents; the lead's single PR-write action is the final description rewrite at Step 4.5.
- **Lead owns the final PR description rewrite only** (Step 4.5), and only via the `pr-description-writer` agent. The lead does not compose the description inline.
- **One review per loop, findings as child comments of that review.** Each loop posts a single pull-request review whose body is the loop header and whose `comments[]` are the anchored findings. Each loop's review stands alone — one review created per loop, fully self-contained on the PR conversation.
- **PR description rewrite on every exit.** Step 4.5 runs on `converged`, `cap reached`, and `stuck`. On `error`, the rewrite is best-effort; if it fails, surface the error in the final report and continue to revoke.
- **Outcome XML, not JSON.** Both subagents write structured outcome data (findings or fix outcomes) to `.bugteam-pr<N>-loop<L>.outcomes.xml`. The lead reads these files between actions. XML chosen for parser robustness against multi-line, special-character, and quoted reason fields.

## Why this design

The three sibling skills compose, but `/bugteam` solves a problem they cannot solve in sequence:

- `/findbugs` audits once and stops.
- `/fixbugs` fixes the findings of one audit and stops.
- A human-driven `/findbugs` → `/fixbugs` → `/findbugs` → `/fixbugs` cycle works but requires the user to drive it.

`/bugteam` automates that cycle. The clean-room property is preserved by spawning a fresh audit agent each loop with no inherited context — every audit is independent of the prior loop's verdict. The 10-loop cap is the safety: pathological cases (audit agent oscillating, fix agent regressing) cannot run away.

The single up-front confirmation is the explicit trade — `/bugteam` is more autonomous than `/findbugs`+`/fixbugs` chained manually. The user accepts that autonomy by typing the command. Stop conditions and the loop log give the user full visibility on exit.
