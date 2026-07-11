# code

Activates strict code standards for the entire implementation session. Triggered by `/code`, `code standards`, `strict code`, `enforce standards`, or `implement with standards`.

## Purpose

Prepends a set of binary completion criteria to every implementation task: no `Any`, no `cast()`, no `# type: ignore`, treated-as-immutable TypedDicts with explicit `_encode_*`/`_decode_*` functions, 100% statement and branch coverage, zero mocks, zero stubs, zero fallbacks, and proper module structure. Every criterion is pass-or-fail; partial credit does not exist.

## Key file

| File | Purpose |
|---|---|
| `SKILL.md` | Sixteen numbered criteria (typing strictness, error handling, test coverage, DI hooks, DRY, TypedDict protocol, Redis boundary, TOML boundary, JSON recursive types, ASGI boundaries, dynamic import pattern, documentation, build infrastructure, lint gates, Protocol signature match, auth/credentials), plus gotchas for Windows PowerShell invocation and per-module `_test_hooks.py` placement. |

## Invocation note

Invoke at the start of an implementation task. The standards persist for the full session. The skill refuses research or planning tasks and redirects them to `/anthropic-plan`.
