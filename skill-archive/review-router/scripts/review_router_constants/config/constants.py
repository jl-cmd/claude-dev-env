"""Constants for route_review_config."""

UNSUPPORTED_ROUTE = "UNSUPPORTED_ROUTE"
UNSUPPORTED_TIER = "UNSUPPORTED_TIER"
INVALID_ROUTE_RECORD = "INVALID_ROUTE_RECORD"
MALFORMED_TIER_OVERRIDE = "MALFORMED_TIER_OVERRIDE"
INVALID_ROUTE_ARM = "INVALID_ROUTE_ARM"
UNKNOWN_ROUTE_SLOT = "UNKNOWN_ROUTE_SLOT"
ROUTE_SPAWN_ARMED = "ROUTE_SPAWN_ARMED"
ALL_OVERRIDE_VALUES = ("1", "2", "3")
INTEGRITY_KEY_BYTES = 32
DECISION_ID_BYTES = 16
CLEANUP_CONTRACT = """This is a cleanup-only review of the current diff, not a correctness or security bug hunt. Gather the diff and include uncommitted changes. Review reuse, simplification, efficiency, and altitude. Reuse existing helpers and adjacent patterns. Simplify redundant state, copy-paste, nesting, dead code, and unnecessary complexity. Remove redundant computation, repeated I/O, sequential independent work, and long-lived captured objects. Fix each issue at the owning abstraction and preserve the intended behavior. Apply safe fixes directly within the reviewed diff. Each finding has file, line, summary, and concrete cost. Skip findings whose fix changes intended behavior, reaches outside the diff, or belongs to correctness review. Respond exactly: That's a correctness review — use /e-code-review, not this skill. Finish with what was fixed and what was skipped."""
