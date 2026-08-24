# Review a visual

1. Identify the route and expected output type.
2. Check accessibility metadata and host compatibility.
3. Walk the A–E checklist below in order. Accuracy outranks style, so a finding at A–D outranks a finding at E.
4. Run `validate-artifact.py` and the relevant render inspection.
5. Repair verified defects and rerun all checks.
6. Report the remaining limitation when a module lacks dedicated guidance.

## A–E checklist

- **A — instant readability.** A stranger gets the story in 10 seconds.
- **B — literalness.** Ideas are drawn as objects rather than written as labels.
- **C — visual hierarchy.** The most important object is the largest and strongest.
- **D — accuracy against the source.** Every arrow matches a citable `path:line`.
- **E — craft.** Layout bounds hold, geometry connects, references resolve, color meaning is consistent, and text reads at display scale.

## Optional advisor audit

One pass, no loop. Hand one subagent the artifact plus the A–E checklist above, ask for ranked issues each with a fix, apply the fixes once, then run step 4 again.
