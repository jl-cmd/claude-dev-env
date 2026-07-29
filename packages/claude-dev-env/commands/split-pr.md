Split one large pull request into a stacked file-based draft chain.

Invoke the `split-pr` skill with the PR number. The skill analyzes file layers, proposes a dependency-ordered split via `AskUserQuestion`, and on approval creates stacked branches and draft PRs.

Usage:

```text
/split-pr 123
/split-pr 456
```
