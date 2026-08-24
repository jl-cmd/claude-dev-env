# Report template

Emit this shape. Keep it compact.

```markdown
## Name-by-capability audit — PR #<N>

**Verdict:** <clean | N violations, M OK drivers>

### Violations
| Finding | Path / title | Why | Suggested rename direction |
|---------|--------------|-----|----------------------------|
| Driver word on capability | `path/or/Title` | <one sentence> | <capability-oriented name family> |

### OK drivers
| Surface | Path / title | Why OK |
|---------|--------------|--------|
| Queue / routing / … | `path` | <one sentence> |

### Notes
- <optional: expanded offense in a package this PR grew, doc-only context, etc.>
```

### Rules for filling cells

- **Finding** — short label for Violations rows only (`Driver word on capability`, `Motive framing in title`).
- **Why** — cite the checklist item (reuse? action name? motive reserved for drivers?).
- **Suggested rename direction** — a family of names (e.g. “STP color batch / color UID rewrite”).
- When clean: **Verdict: clean** and omit Violation rows (keep the OK drivers / Notes sections if useful).
