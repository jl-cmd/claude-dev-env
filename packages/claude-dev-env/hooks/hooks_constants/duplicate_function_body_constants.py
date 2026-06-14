"""Constants for the duplicate-function-body scan in ``code_rules_enforcer``.

The blocking scan flags a top-level function whose body is structurally identical
to a top-level function already defined in a sibling ``.py`` module in the same
directory. This catches the Reuse-before-create / DRY violation where a helper is
copy-pasted across several modules instead of imported from one shared home.

The ``CROSS_SKILL_*`` and ``SKILL*`` constants feed the non-blocking companion
advisory: a helper copied between two skills' ``scripts`` directories, where a
shared module would break independent install. That advisory names the source
skill on stderr rather than denying the write.
"""

MINIMUM_DUPLICATE_BODY_STATEMENTS: int = 3
MAX_DUPLICATE_BODY_ISSUES: int = 25
DUNDER_INIT_FILENAME: str = "__init__.py"
PYTHON_SOURCE_SUFFIX: str = ".py"
DUPLICATE_BODY_GUIDANCE: str = (
    "this function body is identical to one in a sibling module; "
    "extract a single shared helper (for example in hooks_constants/) and "
    "import it from both modules instead of copying it (Reuse before create / DRY)"
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
