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

Selector exclusions keep a pair out of panels. They do not change direct route
decisions. The shipped policy keeps Sol Medium out of panels and routes direct
requests for Sol Medium to Luna Max through `replacements`. Sol Medium is absent
from `approvedPairs`. The selector drops the requested pair before routing it,
so its Luna replacement does not enter the panel through that preference.

```json
"selectorExclusions": [
  {"model": "sol", "effort": "medium"}
]
```

The matching replacement is:

```json
{
  "requested": {"model": "sol", "effort": "medium"},
  "selected": {"model": "luna", "effort": "max"}
}
```

Unknown values, invalid policy data, unavailable replacement models, and
unresolved parent inheritance stop the spawn with a short diagnostic.

The direct spawn hook and advisor bridge use the same shared resolver. A Sol
Medium remap changes only the model and effort fields in the hook's tool input.
The hook returns an allow decision with the updated input and emits no remap
notice when the selected model matches `gpt-*-luna`. Any route that resolves to
another model is denied. Parent inheritance is denied because the hook cannot
verify the inherited model before the spawn.

The hook blocks advisor role claims because the current Codex hook input has no
host-provided role binding. The Python advisor bridge passes trusted session
metadata to the shared resolver. The native advisor hook path stays pending
until the host supplies that binding.
