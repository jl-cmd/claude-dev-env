"""The message markers that name which check inside a bundling rule spoke.

Most lint rules run one check, so their rule identifier already names the
check. Two rules bundle many checks behind one identifier, and a consumer that
classifies a finding by severity needs to know which of them raised it. Each
entry below pairs a stable fragment of a check's message with the name that
identifies the check.
"""

from __future__ import annotations

from typing import NamedTuple


class CheckCatalogEntry(NamedTuple):
    """One check inside a bundling rule, and the text that identifies it.

    Attributes:
        message_marker: A fragment the check's message always carries.
        check_name: The name that identifies the check inside its rule.
    """

    message_marker: str
    check_name: str


CHECK_ID_SEPARATOR: str = "/"
UNCLASSIFIED_CHECK_NAME: str = "unclassified"
ALL_BUNDLING_RULE_IDS: frozenset[str] = frozenset({"code-rules", "validators"})

ALL_CHECK_CATALOG_ENTRIES: tuple[CheckCatalogEntry, ...] = (
    CheckCatalogEntry(
        "exceeds blocking threshold - split into helpers", "function-length"
    ),
    CheckCatalogEntry(" - consider moving to config/", "function-local-constant"),
    CheckCatalogEntry(" - move to config/", "constant-outside-config"),
    CheckCatalogEntry(" - prefix with all_ (CODE_RULES §5)", "collection-name-prefix"),
    CheckCatalogEntry(" - prefix with each_ (CODE_RULES §5)", "loop-variable-prefix"),
    CheckCatalogEntry("Stuttering collection prefix", "stuttering-collection-prefix"),
    CheckCatalogEntry("string separator", "unnamed-string-separator"),
    CheckCatalogEntry("string magic value", "string-magic-value"),
    CheckCatalogEntry(
        "Block comment found - refactor to self-documenting code",
        "block-comment-added",
    ),
    CheckCatalogEntry(
        "Comment found - refactor to self-documenting code", "comment-added"
    ),
    CheckCatalogEntry("comment added:", "comment-diff"),
    CheckCatalogEntry("docstring carries a", "docstring-runon-sentence"),
    CheckCatalogEntry("summary runs", "docstring-prose-wall"),
    CheckCatalogEntry(
        "return type annotation (CODE_RULES §6)", "missing-return-annotation"
    ),
    CheckCatalogEntry(
        "missing type annotation (CODE_RULES §6)", "missing-type-annotation"
    ),
    CheckCatalogEntry("Single-letter variable", "single-letter-variable"),
    CheckCatalogEntry(
        "is exercised by no test in the module's paired test suite",
        "paired-test-missing-function",
    ),
    CheckCatalogEntry("but exercises nowhere", "paired-test-omitted-function"),
)

SEVERITY_BREAKING: str = "breaking"
SEVERITY_SMELL: str = "smell"
SEVERITY_BY_CHECK_ID: dict[str, str] = {
    "code-rules/paired-test-missing-function": SEVERITY_SMELL,
    "code-rules/paired-test-omitted-function": SEVERITY_SMELL,
    "test-pairing": SEVERITY_SMELL,
}
