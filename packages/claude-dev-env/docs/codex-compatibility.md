# Codex compatibility entry point

`codex-compat` is an optional, explicit bridge from this package's Claude-oriented source tree to Codex-compatible records. The existing `claude-dev-env` installer is unchanged and does not invoke it.

## Materialization

Run `codex-compat materialize --source-root <claude-root> --target-root <codex-root>`. The command defaults to a dry run; add `--apply` to publish files. Use `--python <command>` or `CODEX_COMPAT_PYTHON` to select Python. If no usable interpreter is found, the command reports that condition. The launcher passes an argv array, never a shell command.

The Python materializer maps Claude `_shared/`, `agents/`, `hooks/`, `rules/`, and `scripts/` into the target according to the package's compatibility materialization rules. Claude agent frontmatter is converted to Codex TOML metadata. Unsupported Claude metadata is reported, rather than silently treated as equivalent.

Rules, hooks, and scripts that have no safe Codex runtime equivalent remain inert or source-only. They are preserved for inspection and are not executed as translated target tools. The capability bridge likewise emits declarative records only; it never invokes the translated surface.

Materialization uses a compatibility manifest to identify generated files. Dry runs report the plan without writing. Apply mode uses safe link/copy fallback where linking is unavailable, writes atomically, removes only stale managed files, and rolls back managed changes on failure. A failed rollback reports that reconciliation is required.

## Capability bridge

Run `codex-compat bridge --surface <name> --payload '<json-object>'`. The bridge exposes the Python translation logic directly. `TaskCreate` and `TaskUpdate` map to `update_plan`; spawn, message, wait, and stop map to multi-agent surfaces. `ScheduleWakeup` is explicitly unsupported and requires manual review.

## Roots and safety

Both roots are caller-supplied. The tool never writes to `.agents` or `CODEX_HOME` automatically; pass those locations explicitly when desired. No personal paths or secrets are embedded in the package.
