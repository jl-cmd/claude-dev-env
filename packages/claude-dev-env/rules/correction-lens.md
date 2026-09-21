# Correction Lens

**Standing rule. This file is never archived and never removed.** The permanence
clause at the end of this document states what that binds.

**When this applies:** Every correction the user gives. A "no, do it this way", a
"stop writing that word", a repeated review comment, a fix the user makes by hand
after an agent hands work back. Each one is evidence that a control is missing,
and the correction is handled by building that control.

## Rule

A correction runs through five layers, in this order, and the lesson lands at the
highest layer that can hold it. The change opens in the same run as the
correction.

| Priority | Layer | What holds the lesson | The lesson lands as |
|---|---|---|---|
| 1 | Codebase | The mistake is impossible by how the code is written | A type, a signature, a data structure, an API shape, a deleted branch |
| 2 | Static analysis | A program reads the tree and decides | A lint rule, an enforcer check, a paired test, a CI gate |
| 3 | Review tooling | A reviewer or a review bot reads the criterion | A `CODE_RULES.md` row, a `.cursor/BUGBOT.md` pointer, a Graphite or BugBot rule |
| 4 | Skill | An agent follows a procedure | A skill under the agents home |
| 5 | Style guide | Word choice and prose shape | A row in a `rules/*.md` file or a style document |

Layer 1 is the goal every time. A lesson encoded there needs no reader, no run,
and no agent to remember it. The wrong call has nowhere to live.

## Choosing the layer

Three sentences close every correction:

1. The layer chosen.
2. Why each higher layer cannot hold this lesson.
3. The change opened at the chosen layer, by pull request.

A layer holds a lesson when its own test passes:

- **Layer 1 holds it** when a type, a signature, or a data structure can make the
  wrong call fail to compile, fail to construct, or fail to exist.
- **Layer 2 holds it** when a program reading the tree can separate right from
  wrong with no judgment call.
- **Layer 3 holds it** when a reader needs the criterion in front of them and a
  program cannot decide it.
- **Layer 4 holds it** when the lesson is a procedure with steps an agent runs.
- **Layer 5 holds it** when the lesson is word choice or the shape of prose.

Effort rules out no layer. A layer is ruled out when it lacks the capability to
hold the lesson, and the sentence that rules it out says which capability is
missing. "A lint for this would take a day" leaves layer 2 in play.

Two layers often hold one correction. Take both: the shape at layer 1 and the
check at layer 2 cost one run together and each covers what the other misses.

## A repeated correction moves up a layer

The same correction arriving a second time is the measurement. The layer chosen
the first time was too low. Move the lesson one layer up and say so in the same
run.

A review comment that repeats across pull requests reads the same way. Each
repetition names the layer below the reviewer as the one that needs the control.
Count the repetitions.

## Where the control lands

A control lands in this package, so every session that loads this environment
carries it, on any machine, under any model. A control written into one
project's instructions reaches that project alone, and a control written into a
chat reply reaches that conversation alone.

Memory holds the decision. The control holds the behavior. A correction that
produced a memory file and nothing else has been recorded and never encoded, so
the rule still binds. Open the control.

## Trust grows as the controls catch the common mistakes

Add agents after the controls catch what agents get wrong, and start from a
workflow small enough to watch. Each repeated correction becomes a stronger
control, and the number of agents rises behind it.
[`docs/high-trust-agent-delivery.md`](../docs/high-trust-agent-delivery.md)
carries the model this comes from, including the layered-controls picture and
the inner and outer delivery loops.

## Permanence

This file stays in `rules/`. A prune pass, an archive sweep, a consolidation, or
a rewrite that would move it into `rules-archived/` stops at this line. The
"Never archived" section of
[`packages/claude-dev-env/rules-archived/ARCHIVE-MANIFEST.md`](../rules-archived/ARCHIVE-MANIFEST.md)
names it, and
[`archiving-agent-config.md`](archiving-agent-config.md) names the same
exemption from the archiving procedure's side.

An edit that sharpens this rule is welcome. The file stays.

## Excerpt for repository-instruction sessions

Codex reads its repository `AGENTS.md`; this excerpt supplies the standalone
contract.

```
Correction handling for this run, from rules/correction-lens.md.

Every correction the user gives becomes a control. Run it through five layers
and land it at the highest one that can hold it:

1. Codebase. The mistake is impossible by how the code is written: a type, a
   signature, a data structure, an API shape.
2. Static analysis. A program reads the tree and decides: a lint rule, an
   enforcer check, a paired test, a CI gate.
3. Review tooling. A reviewer or a review bot reads the criterion: a code-rules
   row, a BUGBOT pointer, a Graphite rule.
4. Skill. An agent follows a procedure.
5. Style guide. Word choice and prose shape.

Close the correction with three sentences: the layer chosen, why each higher
layer cannot hold the lesson, and the change opened at that layer in this run.
Effort rules out no layer; a missing capability does, and you name which one.

The same correction arriving twice means the layer was too low. Move it up one
layer and say so.

Land the control in the shared environment package, so every session carries
it. A memory file records the decision and encodes nothing.
```

## Sibling rules

| Rule | Role |
|---|---|
| [`flag-non-breaking-findings.md`](flag-non-breaking-findings.md) | A gate blocks on a breaking finding and records a smell |
| [`code-standards.md`](code-standards.md) | The layer map of contract, pointer, enforcer, lint, session rules |
| [`archiving-agent-config.md`](archiving-agent-config.md) | How a rule leaves service, and which files are exempt |
| [`falsify-before-green.md`](falsify-before-green.md) | A new layer-2 check counts once it has run red on a named break |
