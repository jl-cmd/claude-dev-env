# Bugteam — invariants and design rationale

## Constraints

- **Full A–N audit every loop, no exceptions.** PR size, "focused audit," "team overhead," "CODE_RULES already passed" — not valid reasons. Empty `<findings/>` for any category is a valid result. The audit agent walks all A–N rubrics each loop.
- **One run per invocation, multi-PR supported.** All PRs in a single /bugteam invocation share one `run_temp_dir`. Per-PR identity lives in the subagent name prefix (`bugfind-pr<N>-loop<L>` / `bugfix-pr<N>-loop<L>`) and the `<run_temp_dir>/pr-<N>/` subfolder containing that PR's git worktree, diff patches, and outcome XML files.
- **Grant before any spawn, revoke before any return.** Step 0 grants project `.claude/**` permissions; Step 5 revokes. Both are mandatory. Revoke runs on every exit path including error, cap-reached, and stuck.
- **Fresh subagent per loop.** Both bugfind and bugfix are spawned new each loop. Reusing a subagent across loops accumulates context inside that subagent's window — defeats clean-room.
- **One up-front confirmation = whole cycle.** The `/bugteam` invocation authorizes the entire cycle; every subsequent decision runs on that single authorization.
- **20-loop hard cap.** Counted as **AUDIT** completions (increment in Step 3). Standards-fix passes before an audit do not advance `loop_count`. Worst case includes extra clean-coder spawns for the code-rules gate.
- **Code rules gate before every AUDIT.** Run `${CLAUDE_SKILL_DIR}/scripts/bugteam_code_rules_gate.py` until exit **0** before spawning **bugfind**. Same `validate_content` logic as `hooks/blocking/code_rules_enforcer.py`.
- **Clean-room audits, every loop.** Each bugfind subagent's spawn prompt contains only the PR scope, audit rubric, and the current loop number. Prior loop history stays in the lead.
- **Targeted fixes.** Each fix subagent sees ONLY the most recent audit's findings. Prior loops are invisible to the fix subagent.
- **Fix subagent receives the latest audit as its input contract.** Each loop's fix run operates on the current audit's output and only that.
- **Lead owns the final PR description rewrite only** (Step 4.5), via the `pr-description-writer` agent.

## Why this design

The three sibling skills compose, but `/bugteam` solves a problem they cannot solve in sequence:

- `/findbugs` audits once and stops.
- `/fixbugs` fixes the findings of one audit and stops.
- A human-driven `/findbugs` → `/fixbugs` → `/findbugs` → `/fixbugs` cycle works but requires the user to drive it.

`/bugteam` automates that cycle. The clean-room property is preserved by spawning a fresh audit agent each loop with no inherited context — every audit is independent of the prior loop's verdict. The 20-loop cap is the safety: pathological cases (audit agent oscillating, fix agent regressing) cannot run away.

The single up-front confirmation is the explicit trade — `/bugteam` is more autonomous than `/findbugs`+`/fixbugs` chained manually. The user accepts that autonomy by typing the command. Stop conditions and the loop log give the user full visibility on exit.
