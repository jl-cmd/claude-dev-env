# Building a high trust system for agent driven software delivery

Source: Lauren's talk, posted by poteto,
<https://x.com/poteto/status/2102050467505430555/video/1>.

This document carries the model behind
[`rules/correction-lens.md`](../rules/correction-lens.md). The rule states what a
session does with a correction. This document states why that works.

## The central idea

Trust is the limit on how much delivery an agent fleet carries. An agent produces
a change in minutes, and a person reads it in minutes too, so the reading becomes
the bottleneck the moment the agent count rises. Trust rises when the system
proves the change rather than when the person reads harder.

Build the proof into the system, then add agents behind it.

## Why high volume exposes weak systems

A team of two people writing changes by hand absorbs a weak test suite, a thin
style guide, and a review culture that runs on shared memory. The gaps sit in
people's heads and the volume is low enough that heads keep up.

Agents raise the volume until every gap reports. A convention nobody wrote down
gets broken in twenty pull requests at once. A check that covers half the tree
passes half the changes that should fail. The system did not get worse; the
volume made its shape visible.

## Verification gives the agent evidence

An agent that can run the thing it changed improves its own work before a person
sees it. A test suite, a type checker, a lint, a script that drives the feature:
each one is a source of evidence the agent reads and acts on inside its own run.

An agent with no way to verify hands its work to a person as the first check.
Every weakness in verification converts directly into review load.

## The codebase is part of the control system

The strongest control is a codebase where the mistake cannot be written. A type
that makes an illegal state unrepresentable removes a class of bug from every
future change, by every agent, with no rule to read and no check to run.

Treat code shape as a place to put lessons. A signature that refuses the wrong
argument, a data structure that carries its own invariant, a deleted branch and
the guard it required: each retires a rule that would otherwise need enforcing
forever.

## Build controls in layers

Four layers, strongest first:

1. **Impossible by structure.** Types, signatures, data structures, APIs.
2. **Static checks and CI.** Lints, enforcers, tests, gates that read the tree.
3. **Rules, review bots and skills.** Criteria a reader or a bot applies, and
   procedures an agent follows.
4. **Human review.** Judgment: product sense, taste, tradeoffs, risk.

Each layer catches what the layer above could not express. Human attention is
the scarcest layer, so it goes to the judgment calls and nothing else.

## Turn corrections into repository improvements

Every correction is a measurement of the control system. A person catching a
mistake means every layer above them missed it.

So the correction is handled twice: the change gets fixed, and the layer that
should have caught it gets built. A repeated review comment is the loudest
signal available, because repetition proves the lesson lives nowhere a machine
can read.

## The inner delivery loop

The inner loop is one agent working one task: read the code, make the change,
run the checks, read the failures, fix, repeat. The loop closes on evidence the
agent gathers by itself.

A fast inner loop with good evidence produces work that arrives at review
already correct. Most of the investment that raises delivery sits here.

## The outer delivery loop

The outer loop is the pull request: CI, review bots, human review, merge. It
catches what the inner loop's evidence could not reach, and it is where the
expensive resource, a person's attention, gets spent.

Work that reaches the outer loop and bounces costs the whole round trip. Every
control moved from the outer loop into the inner loop pays back on every later
change.

## How the pieces compound

Each control added at a strong layer removes a class of correction from every
future run. The corrections that remain move up the difficulty scale, so the
next control built is stronger than the last. The agent count rises behind the
controls, and the reading load per change falls even as the change count climbs.

The compounding runs the other way too. A correction absorbed in chat and never
encoded arrives again, and the same attention gets spent twice.

## A practical way to apply the model

- Start with one workflow small enough to watch end to end.
- Let the agent run it repeatedly and read the failures.
- Encode each repeated correction at the highest layer that can hold it.
- Raise the agent count once the controls catch the common mistakes.
- Keep reading the corrections, because they measure the controls.
