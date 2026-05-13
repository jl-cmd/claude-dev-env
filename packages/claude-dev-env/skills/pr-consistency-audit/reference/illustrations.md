# Illustrations

Concrete examples of findings with why-they-matter explanations.

## Wrong argument name in script invocation

```
file_path: SKILL.md
line_number: 100
rule_id: rule-9
severity: P0
what_is_wrong: check_bugbot_ci.py --check-active --sha <SHA>
what_it_should_be: check_bugbot_ci.py --owner <O> --repo <R> --check-active --sha <SHA>
evidence_path: scripts/check_bugbot_ci.py
evidence_detail: lines 134-136 define add_argument("--owner", required=True) and add_argument("--repo", required=True). Both required args are missing from the documented invocation.
```

Why this matters: If an agent copies the command from the doc, the script fails with "the following arguments are required: --owner, --repo." The agent cannot trigger bugbot.

## Parameter naming convention mismatch across tool family

```
file_path: SKILL.md
line_number: 162
rule_id: rule-2
severity: P0
what_is_wrong: add_issue_comment(owner="OWNER", repo="REPO", issue_number=NUMBER, body="bugbot run")
what_it_should_be: add_issue_comment(owner="OWNER", repo="REPO", issueNumber=NUMBER, body="bugbot run")
evidence_path: _shared/pr-loop/gh-payloads.md
evidence_detail: lines 67-72 document add_issue_comment with issueNumber (camelCase). issue_read uses issue_number (snake_case) — the two tools have different conventions.
```

Why this matters: The tool call fails at runtime. Twenty files had this same bug because they copied from each other.

## Docstring claim contradicts implementation

```
file_path: scripts/remove_tree.py
line_number: 15
rule_id: rule-3
severity: P0
what_is_wrong: Docstring says "returns 0 when the path never existed." Implementation calls shutil.rmtree(target_path) which raises FileNotFoundError, caught as OSError, returning EXIT_CODE_REMOVE_TREE_FAILURE.
what_it_should_be: Check Path(target_path).exists() before rmtree and return 0 when absent, or update the docstring.
evidence_path: scripts/remove_tree.py
evidence_detail: line 15 docstring claim vs lines 22-28 implementation — the except OSError handler returns EXIT_CODE_REMOVE_TREE_FAILURE for FileNotFoundError.
```

Why this matters: Teardown scripts calling remove_tree() on an already-cleaned temp directory get a failure return. The orchestrator treats this as a real error.

## Stale feature reference in gotcha section

```
file_path: SKILL.md
line_number: 34
rule_id: rule-7
severity: P1
what_is_wrong: Gotcha describes "inline_lag" with its own streak counter and 90s wait. The decision branch for inline_lag is still present in per-tick.md lines 102-106 — the feature was supposed to be removed but both the gotcha and the branch remain.
what_it_should_be: Remove the gotcha and the inline_lag decision branch from per-tick.md.
evidence_path: reference/per-tick.md
evidence_detail: lines 102-106 still contain the fourth BUGBOT decision branch for inline_lag.
```

Why this matters: An agent reading the gotcha thinks inline_lag is real and may misclassify a dirty review as transient lag, waiting rather than fixing.

## Placeholder text in template file

```
file_path: bugteam/obstacles/self-population.md
line_number: 5
rule_id: rule-5
severity: P1
what_is_wrong: "Spawn  — brief it: check  for an open PR  " contains double spaces where an agent invocation, repo, and PR number should be.
what_it_should_be: Fill in the concrete Agent call or remove the section until populated.
evidence_path: bugteam/obstacles/self-population.md
evidence_detail: Template has placeholder spacing with no variable substitutions defined.
```

Why this matters: Obstacle files are reference material for agents. An obstacle with "Spawn — brief it: check for" and no target wastes context and confuses.
