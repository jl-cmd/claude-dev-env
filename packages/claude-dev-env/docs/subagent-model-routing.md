# Automatic child model choices

The package routes native subagent requests before the child starts. It keeps
approved pairs, aliases, replacements, and the advisor default in one file.

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

Unknown values, invalid policy data, and unavailable replacement models stop the
spawn with a short diagnostic. Parent inheritance stays unchanged.
