# hooks/blocking/config

A Python package that holds shared constants for blocking hooks. Opinionated prose-style gates import from here.

## Key files

| File | Contents |
|---|---|
| `__init__.py` | Declares this as a regular package (not a namespace package) so it resolves first on `sys.path` |
| `prose_style_enforcement_constants.py` | `CLAUDE_PROSE_STYLE_ENFORCEMENT` opt-in (default off) for opinionated prose gates |
