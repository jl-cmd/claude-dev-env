---
paths: **/hooks/**/*.py
---

# Hook Prose Matches Its Detector

A hook's docstring lead narrative and its `CORRECTIVE_MESSAGE` describe exactly the shapes the detector flags — no broader trigger surface than the regex enforces.

`hook_prose_detector_consistency` (PreToolUse on Write|Edit of hook modules and `*_constants.py` companions) blocks prose that claims a trigger the detector never fires on, and names the fix.

## Judgment

After writing a hook, ask: would a token that matches every word of this message actually trip the detector? When the message names a shape the regex skips, rewrite the message to name only what the regex catches.

The path-shape case is the common overstatement: a detector that keys off a path separator must not claim it blocks an "output-key segment". The corrective message spells the rewrite.
