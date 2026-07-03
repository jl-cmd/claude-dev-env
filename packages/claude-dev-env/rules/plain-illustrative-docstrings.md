---
paths:
  - "**/*.py"
---

# Plain, Illustrative Docstrings

**When this applies:** Any Write or Edit to a public function, method, class, or module docstring whose narrative prose — the summary and description before the first `Args:` / `Returns:` / `Raises:` / `Yields:` section — says what the code is for or how it behaves. The standard governs the prose a reader meets first, not the structured `Args:` / `Returns:` entries below it.

## Rule

A docstring's narrative reads plainly enough that a general developer follows it on the first read. Two things make that true:

- **Illustrative.** The prose paints a concrete scene — the reader pictures the moment the code matters, the input it sees, the outcome it produces. A reader who finishes the narrative can say what breaks without it.
- **Brief.** The narrative makes its point in few words. Short sentences, each carrying one idea.

Two shapes break the standard. Hold the prose clear of both:

- **No machinery nouns stacked into a wall.** A sentence that chains abstract machinery terms (`the SIGINT install/restore/installability check, the atexit terminal-record registration, and the interrupted-run finalizer`) names parts without painting a scene. Name what the reader sees and why it matters.
- **No defining by negation.** Prose that explains a thing by what it is not (`the non-promoter-specific machinery`) leaves the reader without a picture. Say what the thing is.

## Shape: a summary line, then a diagram

The clearest way to be illustrative is to show a worked example, not describe one. A docstring that lands well reads in four parts:

1. **One summary line** that says what the code does.
2. **A diagram block** that carries the explanation by sight — a reStructuredText literal block (a line ending in `::`, then an indented example) or a doctest (`>>>`). Give the concrete input, mark the outcome, and add `ok:` / `flag:` contrast lines where a pass-and-fail pair makes the point. Keep the diagram clear of a bare number or an ALL-CAPS `NAME = value` line, which read as a magic value or a stray constant to a line-based lint pass.
3. **A couple of short narrative lines** after the block — two or three at most.
4. **The Google `Args:` / `Returns:` sections.**

Keep the wording neutral in the diagram and the prose: two names "contradict" or "clash", two names "agree". Skip words that pass judgment.

Canonical example:

```
Flag a boolean assignment whose target and callee assert opposite polarity.

::

    is_inside_allowed = _point_hits_any_forbidden(...)
             ^^^^^^^                    ^^^^^^^^^
             allowed         vs.        forbidden      ⚠ the two names clash
    ok:   is_inside_allowed = _point_inside_allowed_region(...)
    flag: is_inside_allowed = _point_hits_any_forbidden(...)

The target token and the callee token contradict each other, so the reader
cannot tell which name states the truth. Rename the callee to a neutral form
the two names agree on at every call site.
```

The live version of this docstring sits on `check_polarity_name_contradiction` in `packages/claude-dev-env/hooks/blocking/code_rules_naming_collection.py`.

A short narrative with no diagram is fine when a couple of plain sentences carry the whole picture. The diagram earns its place once the explanation grows past what two or three lines hold — the moment a wall of prose starts to form.

## What to check before you write the docstring

Read the narrative back as a stranger would:

- Does one sentence run long while joining clauses with an em-dash or a semicolon? That is the wall mark — break it into short sentences.
- Does the prose name a concrete moment, input, and outcome, or only abstract parts?
- Does any sentence define the thing by what it is not? Rewrite it to say what the thing is.

## Worked example

A dense wall — one long sentence, machinery nouns, a term defined by negation:

```
Owns the SIGINT install/restore/installability check, the atexit terminal-record
registration, and the interrupted-run finalizer — the non-promoter-specific
machinery that brackets a run so the JSONL artifact always carries a terminal
record and an in-flight theme record on interrupt.
```

The same contract, plain and illustrative:

```
Make sure a run's log always records how it ended.

So when you reopen the report, the last line tells you the truth: the run
finished cleanly, or you hit Ctrl-C while theme 42 was processing, or it died
on an unexpected error. Without this, a killed run looks identical to a clean
one — and you're debugging blind.
```

## Enforcement

Two surfaces carry this standard:

- **Hook (the run-on backstop).** `check_docstring_runon_sentence` in `packages/claude-dev-env/hooks/blocking/code_rules_docstrings.py` flags the one mechanical mark of a wall: a single narrative sentence that is both over the word limit and joined by an em-dash or a semicolon. A hook cannot judge whether prose paints a picture, so it catches only this structural mark. It reads the narrative through a shared partition that sets aside any `::` literal block and any doctest, so a diagram's own arrows and dashes never count against the sentence.
- **Hook (the prose-wall backstop).** `check_docstring_prose_wall_without_illustration` in the same module flags a narrative that runs more than six prose lines with no diagram block. It marks the wall so the writer shows the behavior with a `::` example or a doctest and trims the prose to a few short lines. It cannot judge whether the diagram illustrates well; that stays with the audit lane.
- **Audit (the judgment lane).** Category O sub-bucket O9 in `packages/claude-dev-env/audit-rubrics/category_rubrics/category-o-docstring-vs-impl-drift.md` carries the illustrative-and-brief judgment the hook cannot. The audit teammate reads each changed docstring's narrative and asks whether a general developer follows it on the first read.

## Why

A docstring earns its place by saving the reader a trip into the body. A wall of stacked machinery nouns costs more to read than the code it describes, so the reader skips it and the docstring becomes dead weight. Prose that paints a concrete scene — the moment, the input, the outcome — lets a reader reason about the code without reading it. Naming this standard makes the wall a finding at write time and at audit, rather than a slow defect a reader meets months later.
