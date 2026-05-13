"""Constants for the pr-consistency-audit skill."""

P0_LABEL = "P0"
P1_LABEL = "P1"
P2_LABEL = "P2"

ALL_SEVERITY_LABELS = frozenset({P0_LABEL, P1_LABEL, P2_LABEL})

ALL_SEVERITY_MEANINGS = {
    P0_LABEL: "Runtime failure — the command or tool call will error",
    P1_LABEL: "Confusing or wrong — will mislead but not crash",
    P2_LABEL: "Cleanup — stale references, docs out of sync",
}

ALL_RULE_IDS = frozenset(
    {
        "rule-1",
        "rule-2",
        "rule-3",
        "rule-4",
        "rule-5",
        "rule-6",
        "rule-7",
        "rule-8",
        "rule-9",
        "rule-10",
    }
)

ALL_RULE_NAMES = {
    "rule-1": "canonical_source_cross_reference",
    "rule-2": "parameter_naming_convention",
    "rule-3": "code_vs_docstring_behavior",
    "rule-4": "nonexistent_reference",
    "rule-5": "placeholder_detection",
    "rule-6": "cross_file_contradiction",
    "rule-7": "stale_reference",
    "rule-8": "cross_platform_assumption",
    "rule-9": "script_invocation_correctness",
    "rule-10": "value_consistency",
}

ALL_CSV_HEADER_COLUMNS = [
    "file_path",
    "line_number",
    "rule_id",
    "severity",
    "what_is_wrong",
    "what_it_should_be",
    "evidence_path",
    "evidence_detail",
]

MANIFEST_FILENAME_TEMPLATE = "audit-manifest-{timestamp}.json"
FINDINGS_FILENAME_TEMPLATE = "inconsistency-audit-{timestamp}.csv"
