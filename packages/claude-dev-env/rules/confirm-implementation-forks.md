# Confirm Implementation Forks

**When this applies:** During planning or implementation, whenever two or more viable paths would satisfy the goal and the choice changes the deliverable — its scope, completeness, the work it defers, the dependencies it adds, or a contract that is hard to reverse.

## Rule

At a material fork, stop and ask the user which path to take through `AskUserQuestion`. Do not silently pick one path and proceed. Present each path as an option whose description states its tradeoff: what it delivers, what it defers, the follow-up cost it creates, and how reversible it is. Begin implementing only after the user chooses.

A fork is **material** when any of these hold:

- The paths produce different deliverables, scope, or completeness against the stated target.
- One path defers work — a stub, placeholder, or partial wiring — that creates a follow-up task or hidden debt, while another path completes the work in the same change.
- The paths diverge on something hard to reverse: architecture, a public API or contract, a data schema, or a newly added dependency.
- The choice trades off something the user has a stake in: speed against completeness, a scope cut against full coverage, or a shortcut against the original plan's target.

When one path quietly drops part of the requested outcome or leaves work for later, that gap is itself the fork — surface it rather than choosing the smaller deliverable on the user's behalf.

## Not a fork — just proceed

- Trivially reversible, internal-only choices with no deliverable impact (a local variable name, the layout of a private helper, one of two equivalent standard-library calls).
- The codebase, the user's stated goal, or an existing rule already determines the answer — follow it (see `verify-before-asking`), and do not manufacture a choice.
- Only one path is actually viable — implement it; a false choice wastes a round-trip.

## How to ask

- Write the question and every option in plain language — short, common words and concrete phrasing a non-expert grasps on first read. Spell out or drop jargon, internal names, and acronyms the user has not already used.
- Give just enough to decide (progressive disclosure): state each path's outcome and its main tradeoff in a sentence or two, and hold deeper detail in reserve for when the user asks. Do not paste code, long file lists, or background the choice does not need — extra information raises the reader's effort without improving the decision.
- One option per path. Keep each `label` short; put the tradeoff in the `description`.
- Recommend the path that best meets the user's stated target and list it first, flagged as recommended (per the AskUserQuestion directive in `CLAUDE.md`).
- Hold all edits to the forked area until the answer arrives. Continue unrelated, unambiguous work if it helps.

## Examples

**Wrong:** Reach a point where the feature can be completed or partially wired with a placeholder, pick the placeholder, and move on — leaving the real implementation as an unrequested follow-up.
**Right:** Ask: "Complete the feature in this change, or land a placeholder and track the rest as a follow-up?" with each option's cost stated, and wait for the choice.

**Wrong:** Add a third-party dependency to solve a problem a few lines of existing code could handle, without flagging it.
**Right:** Ask whether to add the dependency or hand-roll the small helper, naming the maintenance and footprint tradeoff.

## Why

A fork is a scope-or-direction decision the user holds a stake in. Choosing silently commits their effort and tokens to a path they may not want, and a deferred-work path can hide a follow-up the user never agreed to. Surfacing the fork once, with the tradeoffs visible, costs one round-trip and avoids rework.

## Relationship to other rules

- **verify-before-asking** gates *whether* a question belongs to the user; a material fork is a judgment or scope call that always does. Resolve anything the codebase can answer first, then ask only about the genuine choice.
- **conservative-action** governs *whether* to act when intent is ambiguous; this rule names a specific trigger — divergent viable paths — that demands a choice before acting.
- **ask-user-question-required** governs *how* to ask: route the fork through `AskUserQuestion`, never a plain-text question.
