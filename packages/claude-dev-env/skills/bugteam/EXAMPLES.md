# Bugteam — end-to-end examples

<example>
User: `/bugteam`
Claude: [resolves PR #42, runs loop]

`Loop 1 audit: 1P0 / 2P1 / 0P2`
`Loop 1 fix: commit a1b2c3d (3 files, +18/-7)`
`Loop 2 audit: 0P0 / 1P1 / 0P2`
`Loop 2 fix: commit e4f5g6h (1 file, +5/-2)`
`Loop 3 audit: 0P0 / 0P1 / 0P2 → converged`

`/bugteam exit: converged`
`Loops: 3`
`Starting commit: 9d8c7b6`
`Final commit: e4f5g6h`
`Net change: 4 files, +23/-9`
</example>

<example>
User: `/bugteam`
Claude: [runs 10 loops without convergence]

`Loop 10 audit: 0P0 / 1P1 / 2P2`

`/bugteam exit: cap reached`
`Loops: 10`
`Remaining: 0P0 / 1P1 / 2P2 — run /findbugs for human triage`
</example>

<example>
User: `/bugteam`
Claude: [loop 4 fix produces no commit]

`Loop 4 fix: clean-coder reported no changes (could not address remaining bugs)`
`/bugteam exit: stuck`
`Unresolved findings (3): src/cache.py:88 (P0 race condition); ...`
</example>

<example>
User: `/bugteam` (mixed-outcome path: some findings fixed, others skipped)
Claude: [resolves PR #99, runs loop with partial-fix outcomes]

`Loop 1 audit: 1P0 / 3P1 / 0P2`
`Loop 1 fix: commit a1b2c3d (2 files, +8/-3) — 2 fixed, 2 could_not_address`
`Loop 2 audit: 0P0 / 2P1 / 0P2`
`Loop 2 fix: 0 fixed, 2 could_not_address (no commit)`

`/bugteam exit: stuck`
`Loops: 2`
`Unresolved findings (2): src/auth.py:45 (P1: file is generated, cannot edit); src/legacy.py:200 (P1: rewrite scope exceeds the bug)`

The bugfix teammate writes one outcome per finding to `.bugteam-loop-2.outcomes.xml`. Findings with `status=could_not_address` carry their `<reason>` text, and the teammate posts a matching reply to each finding comment so the reviewer sees why each bug stayed open.
</example>

<example>
User: `/bugteam` (no PR or upstream diff)
Claude: `No PR or upstream diff. /bugteam needs a target.`
</example>

<example>
User: `/bugteam` (uncommitted changes in working tree)
Claude: `Uncommitted changes detected. Stash, commit, or revert before /bugteam.`
</example>
