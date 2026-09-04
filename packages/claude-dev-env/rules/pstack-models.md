# Pstack delegation policy

Pstack names each role by the capability it needs. Model IDs live in host
preference files. The active native subagent tool lists the model IDs this
host accepts.

These role requirements override the model defaults in pstack skills.
Setup-pstack writes only the selected host preference JSON. The installer
copies this policy into the Cursor rule and the agents-home rule file.

## Setup

When setup-pstack runs, read the active native subagent tool metadata. Use the
host name from that tool or the current host context. Do not infer the host from
CODEX_HOME, CLAUDE_CONFIG_DIR, or another environment variable.

Save choices in the agents home under
`rules/pstack-model-preferences.<host>.json`. Keep each host in its own file.
The file contains this shape:

```json
{
  "host": "current-host",
  "modelsByRole": {
    "feature, refactoring": ["confirmed-host-model"]
  }
}
```

Offer only model IDs the active native tool accepts. Keep the user's order.
Treat `inherit-parent` and `auto` as parent inheritance, not model IDs. A
different host starts with its own confirmed choices. It never copies the Codex
preference file.

## Selection before every delegation

Refresh the accepted model IDs from the active native subagent tool immediately
before each native delegation. Run the installed selector once for each agent.
Use `~/.agents/scripts/select_pstack_models.mjs` for the main profile. For a
named or explicit profile, use the selector under that profile's sibling agents
home.

Send one JSON object through standard input. Use the active host shell on
other operating systems:

```powershell
$selectorInput = @'
{
  "host": "current-host",
  "inventoryHost": "current-host",
  "role": "how critics",
  "delegationIndex": 0,
  "panel": {
    "agentCount": 3,
    "requiresDistinctModels": false
  },
  "availableModelIds": ["confirmed-host-model"],
  "confirmedSuitableModelIds": [],
  "parentModelId": "current-parent-model",
  "parentFallback": {
    "isAllowed": true,
    "hasMaterialCapabilityLoss": false
  }
}
'@
$selection = $selectorInput | node "$HOME/.agents/scripts/select_pstack_models.mjs"
```

`availableModelIds` comes from the current native tool metadata.
`confirmedSuitableModelIds` lists available alternatives. The host metadata or
the user has already confirmed that each one fits this role. Do not rank or
classify a model from its name.

Use the returned `nativeSpawnArguments` in the native subagent call. An empty
object with `omitNativeModelArgument: true` means parent inheritance. Omit the
native `model` argument in that case. Stop when `canDelegate` is false. Ask the
user when `requiresUserChoice` is true.

Run the selector again before the next agent call. Pass the same panel contract
and the new delegation index with the refreshed inventory. Report
`panel.selectedModelIds` and `panel.isCrossModelDiverse` as returned. A panel
that repeats one model is a same-model panel.

## Portable role requirements

feature, refactoring: reliable code execution
bug-fix: careful diagnosis and code execution
perf-issue: systems reasoning and performance analysis
hillclimb: strong iterative judgment
judgment and prose: strong judgment and clear prose
hardest tasks: highest available reasoning capability
how explorer: fast codebase exploration
how explainer: clear technical synthesis
how critics: independent technical criticism
why investigators: fast evidence gathering
why synthesizer: strong evidence synthesis
reflect tooling: reliable tool and workflow analysis
reflect judgment, divergent, synthesizer: strong judgment and divergent analysis
arena runners: independent solution development
arena cross-judge pool: independent comparative judgment
swarm workers: fast bounded task execution
architect runners: independent architecture design
interrogate reviewers: independent adversarial review

## Panel requirements

Panel size and model diversity are separate from model preferences.

- How critics use three agents by default. Cross-model diversity is optional.
- Arena runners use three agents by default and require distinct models.
- The arena cross-judge pool selects one judge. Pass `parentModelId` so the
  selector chooses another available preference before the parent's model.
- Swarm uses the requested worker count. Same-model workers are valid.
- Architect uses two agents by default and requires distinct models.
- Interrogate uses three agents by default and requires distinct models.

A required-diversity panel stops when the current host lacks enough distinct
confirmed models. Parent inheritance is the last fallback. When inheritance
causes material capability loss, stop and ask the user before delegating.
