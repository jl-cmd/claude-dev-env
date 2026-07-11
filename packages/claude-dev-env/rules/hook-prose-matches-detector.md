---
paths: **/hooks/**/*.py
---

# Hook Prose Matches Its Detector

**When this applies:** Any Write or Edit to a hook module (`.py` under `hooks/`) or its `*_constants.py` companion.

**Hook enforcement:** `hook-prose-detector-consistency` (PreToolUse on Write|Edit) blocks a hook whose user-facing prose claims a trigger its detector never fires on. See `hooks.json` for registration.

## Rule

A hook's docstring lead narrative and its `CORRECTIVE_MESSAGE` describe exactly the shapes the detector flags — no broader trigger surface than the regex enforces. An author reads the corrective message to learn what they did wrong; an author reads the docstring to learn what the hook guards. When either claims a trigger the detector cannot fire on, both audiences are misled: an author whose only token is that shape never sees the block, and an author who does see the block is told the wrong cause.

## The path-shape blocker case

A path-shape blocker detects a per-iteration token only when the token sits next to a path separator (its detection regex keys off a `[\\/]`-style character class). Such a hook must not claim it blocks an "output-key segment": a quoted structured-output key alone, with no looped path, is never flagged. The `*_constants.py` companion holds the corrective message and not the detector, so the phrase "output-key segment" describing a blocked trigger is itself the violation there, regardless of which file holds the regex.

| Prohibited claim | Why it overstates | Correct phrasing |
|---|---|---|
| "appears as a path or output-key segment" | the detector keys off a path separator only | "appears as a per-iteration path segment" |
| docstring: "blocks a bare token like `cand_i`" | a bare prose token next to no separator is not flagged | "blocks a per-iteration path like `${work}\cand_i\plate.svg`" |

## The test

After writing a hook, ask: **would a token that matches every word of this message actually trip the detector?** When the message names a shape the regex skips, rewrite the message to name only what the regex catches.
