# Copilot instructions

Hooks in this repo enforce the conventions below. Follow them so your suggestions match what the gates accept. The full reference is `packages/claude-dev-env/docs/CODE_RULES.md`.

## Naming

- Full words, no abbreviations. Never name anything `ctx`, `cfg`, `msg`, `btn`, `idx`, `cnt`, `tmp`, `elem`, or `val` — write `context`, `configuration`, `message`, `button`, `index`, `count`, `element`, and so on.
- Never use the vague names `result`, `data`, `output`, `response`, `value`, `item`, or `temp`. Pick a domain noun that says what the thing is.
- Never start a function name with `handle_`, `process_`, `manage_`, or `do_`. Name the action: `validate_order`, `send_invite`, `build_prompt`.
- Boolean names start with `is_`, `has_`, `should_`, `can_`, `was_`, or `did_` (camelCase `is` / `has` / `should` / `can` / `was` / `did` in JavaScript and TypeScript).
- Loop variables read as `each_<noun>`. The single letters `i`, `j`, `k` are fine for numeric loops and `e` for a caught exception.

## Comments and documentation

- Write self-documenting code. Do not add new inline `#` or `//` comments in production code — the name carries the meaning.
- Docstrings on modules, classes, and functions are welcome. Keep the prose in step with the code: a docstring that lists the cases the body handles lists every one of them.
- Never drop an existing comment on a line you are not otherwise changing.
- Documentation describes the current state of the code. State what the code is and does, not how it got there.

## Types

- Every function parameter and every return is typed.
- Do not use `Any`, do not use `cast()`, and do not add a bare `# type: ignore`. When an ignore cannot be avoided, add a short reason after it.

## Constants and configuration

- No magic values in a production function body. The numbers `0`, `1`, and `-1` are fine.
- Constants live in `config/` or a `*_constants` package, never as a loose `UPPER_SNAKE` at module scope in a production file.
- Search for an existing constant before adding a new one, and reuse it.

## Logging

- Pass the format string and its arguments as separate parameters: `log_info("saved %d rows for %s", row_count, account_id)`. Never pass an f-string to a `log_*` call.

## Imports

- Every import sits at the top of the module, never inside a function body.
- Drop an import the file does not read.

## Structure

- Prefer functions over classes when there is no state to hold. Prefer a concrete class over an abstract base until a second implementation exists.
- Keep functions small and single-purpose. Use guard clauses and early returns rather than deep nesting.
