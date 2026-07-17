"""The additionalContext text the verified-commit gate attaches to a deny.

The gate injects this next to the blocked tool result so the agent learns,
at the moment of the block, when the '# verify-skip' marker is legitimate
and when a fresh verification is required instead.
"""

VERIFY_SKIP_ADDITIONAL_CONTEXT = (
    "The verified-commit gate honors a one-command escape hatch: appending the "
    "marker '# verify-skip' as a trailing shell comment (outside every quoted "
    "region) to the blocked command bypasses the gate for that command only. "
    "It is allowed only when the branch surface is the "
    "same code a code-verifier already passed clean and the gate is "
    "blocking on a verdict that does not cover it (an unminted verdict, "
    "staging churn, or a reverted concurrent write) — confirm the verified "
    "suite still passes and the diff holds nothing beyond the clean verdict "
    "before using it. Any real code change since that clean verdict, a "
    "first verification, or unrepaired findings all require a fresh "
    "verification by the code-verifier agent instead. Full rule: "
    "~/.claude/rules/verified-commit-gate-skip.md."
)
