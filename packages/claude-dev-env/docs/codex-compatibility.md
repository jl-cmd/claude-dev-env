# Codex compatibility entry point

`codex-compat` is an optional, explicit bridge from this package's Claude-oriented source tree to Codex-compatible records. The existing `claude-dev-env` installer is unchanged and does not invoke it.

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

## Per-message context injection (manual wiring)

Codex reads the same `hookSpecificOutput.additionalContext` shape as Claude,
on its own `UserPromptSubmit` event. `hooks/session/style_reminder_prompt.py`
works for both, as is.

The install already points `$CODEX_HOME/hooks` at the shared hooks folder.
Once installed, the script sits at
`$CODEX_HOME/hooks/session/style_reminder_prompt.py`.

Add this by hand to `$CODEX_HOME/hooks.json` (merge it into an existing file):

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "command": "python3 $CODEX_HOME/hooks/session/style_reminder_prompt.py"
      }
    ]
  }
}
```

Limits:

- The installer skips Codex `hooks.json` for now. Wire it by hand.

## Luna fast-mode guard

`hooks/blocking/luna_fast_mode_gate.py` serves Claude and Codex. Codex reads its own `hooks.json`, so add this `PreToolUse` group to that file. Replace `<CODEX_HOOKS_ROOT>` with the directory that holds the shipped hook:

```json
{
  "matcher": "Agent|Task|multi_agent_v1__spawn_agent",
  "hooks": [
    {
      "type": "command",
      "command": "python <CODEX_HOOKS_ROOT>/blocking/luna_fast_mode_gate.py",
      "timeout": 10
    }
  ]
}
```

The guard requires exact `fast` for Luna spawns through `Agent` and `Task`. Native Codex `multi_agent_v1__spawn_agent` accepts exact `fast` or `priority`. Other models and tools pass through.

## Roots and safety

Both roots are caller-supplied. The tool never writes to `.agents` or `CODEX_HOME` automatically; pass those locations explicitly when desired. No personal paths or secrets are embedded in the package.
