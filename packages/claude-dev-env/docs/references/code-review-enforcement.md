# Hook enforcement

Codex publication uses repository-native `CODE_RULES` checks and the existing
verified-commit policy. These checks run from the portable hook package and do
not require a Claude session.

## Active checks

- `hooks/git-hooks/pre_push.py` guards protected destinations and runs the
  `CODE_RULES` gate against the remote change base.
- `hooks/hooks_constants/bash_pre_tool_use_dispatcher_constants.py` registers
  the repository-native Bash and PowerShell protections.
- `hooks/hooks.json` registers the supported file, shell, GitHub, and agent
  event contracts.

## Claude review source inventory

The package retains `code_review_push_gate.py`, `code_review_pr_create_gate.py`,
and `code_review_stamp_directory_write_blocker.py` as Claude configuration
source records. Their Claude review-stamp lifecycle is outside the Codex hook
activation surface.

The materializer keeps provider-specific modules source-only until an event,
payload, output, failure, and test contract exists for the target runtime.

## Source locations

- Native push hook: `hooks/git-hooks/pre_push.py`
- Repository verifier policy: `hooks/blocking/verified_commit_gate.py`
- Claude review source records: `hooks/blocking/code_review_*.py`
