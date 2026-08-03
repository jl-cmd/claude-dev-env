# Quality gates

Judgment checks a script cannot make. Run them by eye on the rendered result, after `scripts/validate-artifact.py` passes.

- The artifact is self-contained and uses an approved external-resource origin when a resource is needed.
- Rendered output has no clipping, unintended overlap, or unreadable contrast.
- The visual reads at display scale, not just at full zoom.
