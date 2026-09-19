# Graders and commands

## Contents

- Prompt frontmatter
- Grader types
- Case set
- Eval commands
- Results
- Flag-gated features outside plugin eval

## Prompt frontmatter

`evals/<case>/prompt.md` takes these frontmatter keys.

| Key | Use |
| --- | --- |
| `max_turns` | Default 10. Set about 40 for a skill that spawns agents. |
| `timeout_seconds` | Wall-clock cap for one run. |
| `allowed_tools` | Read-only set: Read, Glob, Grep, Skill, Agent, TodoWrite, and the task tools. |

Write, Edit, SendMessage, and Bash go on the command line through `--allow-tools`, not in
`allowed_tools`.

## Grader types

Each file in `evals/<case>/graders/` is one grader.

| Type | Fields | Checks |
| --- | --- | --- |
| `regex` | `target`: `last_message`, `trace`, `files`, or `{source: file, path}` | A pattern in the chosen text |
| `tool_used` | `tool`, `input_match`, `min`, `max`, `arm` | How many calls to a tool, filtered by an input regex |
| `tool_order` | `before`, `after`, each a tool name or `{tool, input_match}` | One call lands before another |
| `file_exists` | `path` glob, `exists` | A file created during the run matches, or none does with `exists: false` |
| `llm` | The body is the rubric, `focus` | A judge panel votes, and 2 of 3 decide |
| `baseline` | `baseline_file`, `criteria` | A judge rates the run at least as good as a reference `.jsonl` transcript |

Source doc: https://code.claude.com/docs/en/plugin-evals

## Case set

Write at least these three shapes.

**Slash case.** The prompt starts with `/<name>`. No `Skill` call happens, so grade what only the
skill produces:

- `tool_used` with `tool: Agent` and an `input_match` on the agent name the skill spawns.
- `tool_order` with that `Agent` spawn before the first `Write`.

**Plain-words case.** The prompt asks for the job in ordinary words. Vary the wording, and do not
copy the exact phrase from the skill description into the only trigger case. Grade the trigger with:

```text
tool: Skill
input_match: '"skill"\s*:\s*"(?:[\w-]+:)?<name>"'
```

**Must-not-trigger case.** The prompt uses a verb near the triggers in its ordinary sense. Grade
with `tool_used`, `tool: Skill`, `min: 0`, `max: 0`, `arm: both`.

Grade on skill behavior. A grader keyed to a transport token that upstream may remove breaks on an
upgrade with no change in the skill.

## Eval commands

Run every command from the wrapper root.

Smoke run, one case:

```text
claude plugin eval . --case <name> --runs 1 --ablation none --max-cost-usd 2 --no-publish --trust-plugin --allow-tools Write SendMessage
```

`--trust-plugin` is needed when stdin is not a terminal. `--case` takes one glob. Only the last
`--case` flag takes effect, so match several cases with one glob.

Full run: drop `--runs` and `--ablation`. The default is 3 runs with the plugin and 3 runs without.
The delta, with minus without, measures what the skill adds. A smoke score under `--ablation none`
has no without-plugin arm, so it measures nothing about contribution.

Add `--keep-temp` to keep the sandbox. Its trace is `out/trace.jsonl`.

## Results

Each run writes `evals/results/<timestamp>/report.html` and `aggregate-result.json`.

Before you compare arms, read each run's `permission_denials` and its final result. A run whose
writes were all denied still shows the tool_use attempts.

## Flag-gated features outside plugin eval

The sandbox cannot turn on a flag-gated feature. Test it with `claude -p`, once with the wrapper
loaded and once without:

```text
claude -p "<task>" --advisor <model> --plugin-dir <wrapper> --setting-sources project --strict-mcp-config --allowedTools "<list>" --permission-mode dontAsk --output-format stream-json --verbose
```

Drop `--plugin-dir <wrapper>` for the second arm.

- Keep the user's config. An empty `CLAUDE_CONFIG_DIR` drops the login and the run reports
  "Not logged in". `--setting-sources project` keeps user settings out.
- Count the feature in the stream. For the advisor, count content blocks with `type`
  `server_tool_use` and `name` `advisor` on the main thread only.
- Before you read a zero count, run a positive control whose prompt asks for the feature by name. A
  zero can mean the feature was not attached, rather than not chosen.
- Keep the run's working folder outside the wrapper root, since writes under `--plugin-dir` are
  denied in dontAsk mode.
