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
    "this function body is identical to one in a sibling module; "
    "extract a single shared helper (for example in hooks_constants/) and "
    "import it from both modules instead of copying it (Reuse before create / DRY)"
)
SAME_FILE_INLINE_DUPLICATE_GUIDANCE: str = (
    "this function body is also present inline as a contiguous statement block "
    "inside another function in the same module; call this helper from that "
    "function instead of repeating the block, so a single helper backs both call "
    "sites and a fix cannot land in one copy while the other keeps the bug "
    "(Reuse before create / DRY)"
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
    "two skill folders install on their own, so this copy is a defensible "
    "skill-isolation tradeoff; a shared module would couple the skills and "
    "break independent install. Confirm the copy is intentional, or for a "
    "large or behavior-bearing body raise the choice through AskUserQuestion "
    "(see the no-cross-skill-duplicate-helpers rule)"
)
