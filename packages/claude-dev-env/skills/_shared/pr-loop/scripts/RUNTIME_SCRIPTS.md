# PR-loop runtime scripts

**Redirect only.** Canonical file lives under the top-level `_shared` tree (not `skills/_shared`).

Load the real file:

@~/.claude/_shared/pr-loop/scripts/code_rules_gate.py

@~/.claude/_shared/pr-loop/scripts/preflight.py

@~/.claude/_shared/pr-loop/scripts/post_audit_thread.py

@~/.claude/_shared/pr-loop/scripts/post_audit_review.py

@~/.claude/_shared/pr-loop/scripts/gh_util.py

@~/.claude/_shared/pr-loop/scripts/reviews_disabled.py

@~/.claude/_shared/pr-loop/scripts/reviewer_availability.py

@~/.claude/_shared/pr-loop/scripts/copilot_quota.py

@~/.claude/_shared/pr-loop/scripts/grant_project_claude_permissions.py

@~/.claude/_shared/pr-loop/scripts/revoke_project_claude_permissions.py

@~/.claude/_shared/pr-loop/scripts/verify_review.py

@~/.claude/_shared/pr-loop/scripts/README.md

Skill-local scripts in **this** folder (`build_*_prompt.py`, `init_loop_state.py`, etc.) stay here. Runtime gate/preflight/review helpers live only under `~/.claude/_shared/pr-loop/scripts/`.
