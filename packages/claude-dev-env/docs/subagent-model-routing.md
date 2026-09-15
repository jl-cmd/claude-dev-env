# Automatic child model choices

The package routes native subagent requests before the child starts. It keeps
approved pairs, aliases, replacements, selector exclusions, and the advisor
default in one file.

The source policy is
`packages/claude-dev-env/rules/subagent-model-policy.json`.

After install, the editable file is
`<agents-home>/rules/subagent-model-policy.json`.

The installer creates this file only when it is absent. Later installs keep the
file and its edits. The main profile uses the `.agents` directory beside
`.claude`. A named profile uses its matching `<profile>.agents` directory.

To change a route, edit the `selected` pair for one `requested` pair. For
example, change the `terra` and `medium` entry in `replacements` to:

```json
{
  "requested": {
    "model": "terra",
    "effort": "medium"
  },
  "selected": {
    "model": "luna",
    "effort": "max"
  }
}
```

The next routing call reads the file again. The resolver source stays unchanged.

To keep a pair out of selector panels, add it to `selectorExclusions`. This
does not block the shared resolver or the spawn hook. For example:

```json
"selectorExclusions": [
  {"model": "sol", "effort": "medium"}
]
```

Unknown values, invalid policy data, and unavailable replacement models stop the
spawn with a short diagnostic. Parent inheritance stays unchanged.

The hook blocks advisor role claims because the current Codex hook input has no
host-provided role binding. The Python advisor bridge passes trusted session
metadata to the shared resolver. The native advisor hook path stays pending
until the host supplies that binding.
