"""Constants for the duplicate-function-body scans in ``code_rules_enforcer``.

The cross-file blocking scan flags a top-level function whose body is
structurally identical to a top-level function already defined in a sibling
``.py`` module in the same directory. The same-file blocking scan flags a
top-level function whose body appears verbatim as a contiguous statement block
inside another function in the same module. Both catch the Reuse-before-create /
DRY violation where a block of logic is copied instead of called from one shared
home, so a fix that lands in one copy leaves the other carrying the bug.

The ``CROSS_SKILL_*`` and ``SKILL*`` constants feed the non-blocking companion
advisory: a helper copied between two skills' ``scripts`` directories, where a
shared module would break independent install. That advisory names the source
skill on stderr rather than denying the write.
"""

MINIMUM_DUPLICATE_BODY_STATEMENTS: int = 3
MINIMUM_INLINE_DUPLICATE_BODY_STATEMENTS: int = 1
MAX_DUPLICATE_BODY_ISSUES: int = 25
DUNDER_INIT_FILENAME: str = "__init__.py"
PYTHON_SOURCE_SUFFIX: str = ".py"
DUPLICATE_BODY_GUIDANCE: str = (
    "This function body matches a sibling module. Extract one shared helper in "
    "hooks_constants/ and import it from both modules (Reuse before create / DRY)."
)
SAME_FILE_INLINE_DUPLICATE_GUIDANCE: str = (
    "This function body also appears inline inside another function in the same "
    "module. Call this helper from both sites so one implementation serves both "
    "call sites (Reuse before create / DRY)."
)
SAME_FILE_INLINE_DUPLICATE_SPAN_SUFFIX_TEMPLATE: str = (
    "(inline duplicate body spans: helper at line {helper_start} spanning "
    "{helper_length} lines, enclosing at line {enclosing_start} spanning "
    "{enclosing_length} lines)"
)

SKILLS_DIRECTORY_NAME: str = "skills"
SKILL_SCRIPTS_DIRECTORY_NAME: str = "scripts"
MAX_CROSS_SKILL_ADVISORY_ISSUES: int = 25
CROSS_SKILL_ADVISORY_PREFIX: str = "[CODE_RULES advisory]"
CROSS_SKILL_DUPLICATE_GUIDANCE: str = (
    "Two skill folders install independently, so this copy supports skill "
    "isolation. A shared module would couple the skills. Confirm the copy's "
    "intent, and raise a large or behavior-bearing body through AskUserQuestion "
    "(see the cross-skill duplicate-helper rule)."
)
