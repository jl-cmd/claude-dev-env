# Proof-of-Work PR Comments

**When this applies:** Every pull request. One comment on the PR carries the proof of the work — posted after `gh pr create` or after a material new commit, and always before the PR leaves draft.

## The standard

A proof comment has five parts:

1. **The exact commands run on real data.** A fenced code block showing the command(s) that produced the artifact — not test output alone.
2. **Measured outcomes.** Numbers read from the produced artifact — counts, dimensions, hashes, byte sizes, rankings — as a table or a bullet list of facts.
3. **Plan linkage.** One sentence naming the parent issue or phase the PR advances, with the issue reference (for example: "Advances phase 2 of issue #12").
4. **Visual evidence for values a human cannot read at a glance.** When the change is visual (the diff touches images, HTML, CSS, or hex color values), embed an image: hex colors as inline swatch images (`![](https://placehold.co/20x20/RRGGBB/RRGGBB.png)`), coordinates as marked-up screenshots, size changes as before/after pairs. A wall of raw values fails the standard even when every value is correct.
5. **Honest gaps.** State plainly what the offline proof cannot show, and what covers that gap.

## Enforcement

The `pr_description_enforcer` hook enforces the standard at two points:

- **On `gh pr comment`:** a comment body whose heading names proof or verification is audited for the five parts. The audit looks for a fenced code block with content, a table row or bullet line carrying a number, a line pairing an issue reference (`#123`) with a linkage word (issue, phase, plan, parent, advances, milestone, part of), an image embed when the PR diff is visual, and a gap phrase (gap, limitation, cannot, does not show, not shown, unverified, not covered). The block message names each missing part.
- **On `gh pr ready`:** the hook reads the PR's comments and blocks readying while no comment passes the audit. `gh pr ready --undo` returns a PR to draft and is never blocked.

A `gh` failure (network, auth, missing executable) never blocks — the gate fails open on tooling problems, and the comment audit skips bodies it cannot read.

## Why

A PR body says what changed; the proof comment shows that it worked. Real command output, measured numbers, and a rendered image let a reviewer check the claim in seconds, with no need to re-run the work. Stating the gaps keeps the proof honest: the reviewer knows exactly what still rests on trust and where that is covered. Gating draft-to-ready makes the comment land before review starts, on every machine, whatever the session's habits.
