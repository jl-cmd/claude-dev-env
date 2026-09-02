"""Constants for the validate_content edit-lane and full-gate phase split.

The edit lane and the full gate share every check except six that read
sibling modules from disk. These names identify each phase, name the checks
the full gate alone runs, name the hook-infrastructure checks the edit lane
still runs, and template the error for an unrecognized phase.
"""

EDIT_LANE_PHASE: str = "edit_lane"
FULL_GATE_PHASE: str = "full_gate"
ALL_VALIDATION_PHASES: frozenset[str] = frozenset({EDIT_LANE_PHASE, FULL_GATE_PHASE})

ALL_FULL_GATE_ONLY_CHECK_NAMES: frozenset[str] = frozenset(
    {
        "check_duplicate_function_body_across_files",
        "advise_cross_skill_duplicate_helper",
        "check_public_function_missing_paired_test",
        "check_test_file_omits_module_public_function",
        "check_orphan_css_classes",
        "check_config_duplicate_path_anchor",
    }
)

ALL_HOOK_INFRASTRUCTURE_EDIT_LANE_CHECK_NAMES: frozenset[str] = frozenset(
    {
        "check_same_file_inline_duplicate_body",
        "check_zero_payload_function_alias",
        "check_unanchored_command_dispatch",
    }
)

UNKNOWN_VALIDATION_PHASE_MESSAGE_TEMPLATE: str = (
    "unrecognized validation phase {phase!r}; expected one of {all_phases}"
)
