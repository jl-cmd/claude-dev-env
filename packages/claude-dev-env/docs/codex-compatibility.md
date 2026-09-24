# Codex compatibility entry point

`codex-compat` is an optional, explicit bridge from this package's Claude-oriented source tree to Codex-compatible records. The package installer also registers the supported native subagent routing hook in the selected Codex home.

## Materialization

Run `codex-compat materialize --source-root <claude-root> --target-root <codex-root>`. The command defaults to a dry run; add `--apply` to publish files. Use `--python <command>` or `CODEX_COMPAT_PYTHON` to select Python. If no usable interpreter is found, the command reports that condition. The launcher passes an argv array, never a shell command.

The Python materializer maps Claude `_shared/`, `agents/`, `hooks/`, `rules/`, and `scripts/` into the target according to the package's compatibility materialization rules. Claude agent frontmatter is converted to Codex TOML metadata. The canonical failure blast-radius rule projects its repository-instruction excerpt into a managed `AGENTS.md` file. Claude metadata reports its supported-field shape.

The Codex hook projection merges a managed `apply_patch` entry for `code_rules_enforcer.py` into the target `hooks.json`. Existing Codex hook entries keep their order, repeated enforcer entries collapse to one deterministic record, and the command resolves under the target root. The enforcer reads the patch command, reconstructs every file's pre-edit and projected post-edit content, and returns a blocking diagnostic for patch shapes requiring correction or code-rule violations. The existing Claude `Write`, `Edit`, and `MultiEdit` dispatcher keeps its current order and behavior.

The capability bridge emits declarative records and leaves translated surfaces for their owning runtime.

Materialization uses a compatibility manifest to identify generated files. Dry runs report the plan without writing. Apply mode uses safe link/copy fallback where linking is unavailable, writes atomically, removes only stale managed files, and rolls back managed changes on failure. A failed rollback reports that reconciliation is required.

The manifest hash decides who owns a target file. A file whose hash still matches the manifest is one the tool wrote, so a later run refreshes it in place. A file whose hash differs is one you edited, so the run preserves it and reports a conflict. A file the manifest does not record at all is adopted only when its bytes already match the plan, which is what an interrupted run leaves behind; any other unrecorded file is preserved, and the error names the file to move or delete.

A missing or unreadable source root is an error, and the run changes nothing. An existing source root holding no agents makes every managed file stale, so the run refuses to delete them and exits non-zero; add `--allow-prune-all` to remove them on purpose.

## Capability bridge

Run `codex-compat bridge --surface <name> --payload '<json-object>'`. The bridge exposes the Python translation logic directly. `TaskCreate` and `TaskUpdate` map to `update_plan`; spawn, message, wait, and stop map to multi-agent surfaces. `ScheduleWakeup` is explicitly unsupported and requires manual review.

## Automatic model routing

The package installer seeds `subagent-model-policy.json` in the agents-home
`rules/` directory when the file is absent. It registers one `PreToolUse` group
for `multi_agent_v1__spawn_agent` in `$CODEX_HOME/hooks.json`. Existing Codex
hook groups stay in place. Claude-only hook groups do not enter the Codex file.

Edit the installed policy file to change the next routing decision. The resolver
loads that path for each invocation.

The default `.claude` target uses `CODEX_HOME`. A named profile or another
target uses `<managed-root>/.codex`, so launch that profile with the same
`CODEX_HOME` value.

## Luna spawn tier

No hook gates the tier a Luna spawn asks for, so a Codex `hooks.json` needs no
entry for it, and the caller holds that tier.

## Roots and safety

Both materializer roots are caller-supplied. The tool writes only inside those
roots. No personal paths or secrets are embedded in the package.
