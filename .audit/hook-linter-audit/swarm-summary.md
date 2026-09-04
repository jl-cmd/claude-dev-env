# Hook audit swarm summary

| Slice | Result | Main finding |
| --- | --- | --- |
| Registration and installation | ISSUES | Claude drops the inline validator during same-matcher merge. Codex has legacy duplicates and two missing targets. |
| Blocking hooks | ISSUES | Source has 18 blocking write entries, 17 shell entries, two Stop blockers, and more direct blockers. |
| Lifecycle and automation | ISSUES | `config_change_guard.py` blocks. Most other lifecycle hooks run synchronously without blocking. |
| Validators | ISSUES | True linters run through blocking hook wrappers. The documented 12-check save roster has 11 entries. |
| Git and pull requests | ISSUES | Native pre-commit and pre-push hooks block. Pull-request author switching can outlive a later denial. |
| Linter and continuous integration coverage | ISSUES | Ruff, Mypy, tests, and instruction pairs exist. Full custom rule coverage is missing from continuous integration. |
| Runtime evidence | ISSUES | The audit reproduced a shell parsing false positive and one valid personal-path catch at write time. |
| Completeness and tests | ISSUES | The verifier misses dispatcher children, inline commands, and Git hooks. One retired blocker is unmanaged. |

All eight slices returned. No coverage worker dropped out.

## Verified counts

- Canonical hook commands: 32.
- Dispatcher-hosted entries: 43.
- Canonical logical execution associations after expansion: 70.
- Native Git hooks: 3.
- Installed Claude commands: 39.
- Installed Codex commands: 50.
- Shared block-log records: 182,713 valid and 11 malformed at inspection time.

## Main defects

- The Claude installer merges same-matcher groups by replacement. The inline validator disappears.
- Installed Codex configuration repeats direct checks that its dispatchers also run.
- Installed Codex configuration names two files that do not exist.
- Pull-request author switching can remain active when a later PreToolUse gate denies creation.
- The timing harness can report a fast Windows command-launch failure as a valid timing sample.
- Full custom code-rule checks do not run as a required continuous integration gate.
- `stale_comment_reference_blocker.py` is absent from the active roster and absent from the installer retirement set.
- `session_end_cleanup.py` has no dedicated test.
