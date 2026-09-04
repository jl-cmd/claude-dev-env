# Audit tool design synthesis

## Base

Use the Sol static execution graph. It makes the 32 direct commands, five dispatchers, and 43 hosted entries explicit. It also compares Claude, Codex, and native Git against their own expected projections.

## Grafts from Terra

- Render no raw command, path, file content, or digest.
- Keep two public entry points. Use the command-line interface and `audit(request)`.
- Assert that Git inspection runs only fixed read-only configuration queries.

## What we left out

- File access and Git probes stay private until a real second caller appears.
- Support only the current literal roster syntax.
- Dispatcher route details stay internal unless a finding needs them as evidence.

## Rejections

- Do not import roster modules. Import-time code can mutate the machine.
- Do not keep a hand-written inventory. Runtime sources own discovery.
- Do not expose opaque command fingerprints. Source position is enough for the report.

## Dropout

The Luna candidate did not finish before synthesis. Terra and Sol both completed. Both parse rosters statically instead of importing hook code.

## Verification contract

The implementation passes only when it finds 32 direct commands, five dispatcher registrations, and 43 hosted entries without importing or executing hook code. Installed output must omit literal user paths and command text.

## Implemented shape

`audit-hooks.mjs` owns static discovery and analysis. `audit-hooks-cli.mjs` owns command-line arguments and file output. The split keeps the analysis module below 400 lines. Installed dispatcher rosters come from the installed hook tree. Each hosted child keeps its declared tool matcher. Lifecycle coverage includes canonical, installed-only, and native Git targets.
