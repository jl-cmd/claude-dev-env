# Handoff schema

An orchestrator or the closeout skill hands the tracker one **issue-candidate** JSON record per obstacle. The tracker consumes each record through the full path and returns the issue number and URL.

## The record

```json
{
  "kind": "roadblock | task | bug | enhancement",
  "title": "<short imperative title>",
  "epic": "<work-stream label the sub-issue belongs under>",
  "summary": "<one sentence a reader with zero session context acts on>",
  "evidence": "<verbatim line captured this session — error text, command, or log line>",
  "where": "<file, hook, gate, or tool the evidence names — path relative to the repo root>",
  "impact": "<what the obstacle cost: work blocked, count of times hit, workaround forced>",
  "proposed_fix": "<the specific change — name the failure mode and the condition>",
  "blocking": true
}
```

## Field meanings

| Field | Meaning |
|-------|---------|
| `kind` | The sub-issue's `type:` label stem. `roadblock`, `task`, `bug`, or `enhancement`. |
| `title` | The sub-issue title. Short and imperative. |
| `epic` | The work-stream the sub-issue belongs under. The tracker finds or creates the matching epic. |
| `summary` | The one-sentence body opener. Self-contained — a reader with no session context acts on it. |
| `evidence` | A verbatim line captured this session, placed in a fenced block in the body. |
| `where` | The file, hook, gate, or tool the evidence names. A repo-relative path, no volatile temp path. |
| `impact` | What the obstacle cost. |
| `proposed_fix` | The specific change. |
| `blocking` | `true` routes the sub-issue to `type: roadblock`, overriding `kind`. `false` keeps the `kind` label. |

`kind` maps to the `type:` label. `blocking: true` takes precedence and routes the sub-issue to `type: roadblock`.

## Filled example

```json
{
  "kind": "bug",
  "title": "Inline-collection gate fires in exempt test files",
  "epic": "hook exemptions for test files",
  "summary": "The code_rules_enforcer inline-collection check blocks a valid list literal in a test file, where test files are exempt from the magic-value gate.",
  "evidence": "BLOCKED: [MAGIC_VALUE] Inline list literal [200, 404, 500] in a function body -- extract to a named constant in config/.",
  "where": "packages/claude-dev-env/hooks/blocking/code_rules_enforcer.py",
  "impact": "Hit 3 times in one session on three test files; each forced a workaround move to a module constant.",
  "proposed_fix": "Extend the magic-value test-file exemption to cover the inline-collection check, so list and set literals in test bodies pass.",
  "blocking": false
}
```

## Consume flow

For each record, in order:

1. **Dedup** — search open and closed issues on the target repository for a twin.
2. **Find or create the epic** — match the `epic` label; open a parent with the `epic` label when none matches.
3. **Create the sub-issue** — body from `summary`, `evidence`, `where`, `impact`, `proposed_fix`.
4. **Labels** — apply the `type:` label from `kind`, or `type: roadblock` when `blocking` is `true`. Create the label when the repository lacks it.
5. **Attach the native sub-issue** — read the child's REST database `.id` and attach it under the epic.
6. **Refresh the epic checklist** — add the child's `- [ ] owner/repo#<N>` line and update the epic status.

The return is the sub-issue number and URL (and the epic number and URL when the epic was created this call).
