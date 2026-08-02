# Quality gates

Checks `scripts/validate-artifact.py` cannot make — the script covers metadata, the text floor, connector fill, layout bounds, positioning, and accessible names.

- The artifact is self-contained and uses an approved external-resource origin when a resource is needed.
- Every inventory element is either in a visual or named in the surrounding prose.
- Connectors stop at boundaries.
- Rendered output has no clipping, unintended overlap, or unreadable contrast.
