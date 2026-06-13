"""Constants for the cross-file duplicate-function-body scan in ``code_rules_enforcer``.

The scan flags a top-level function whose body is structurally identical to a
top-level function already defined in a sibling ``.py`` module in the same
directory. This catches the Reuse-before-create / DRY violation where a helper
is copy-pasted across several modules instead of imported from one shared home.
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
