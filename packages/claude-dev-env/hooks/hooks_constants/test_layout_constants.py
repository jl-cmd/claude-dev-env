"""Constants for the test-module dead-scaffolding checks in ``code_rules_enforcer``.

Lives under the hooks-tree ``hooks_constants`` package so module-level
UPPER_SNAKE constants satisfy the CODE_RULES "constants live in config"
requirement and share a home with the other hook-tree configuration. The
values here drive two test-file checks that catch scaffolding a removed
monkeypatch line leaves behind: a dead private module constant, and an
unused private-helper parameter.
"""

import re

PRIVATE_NAME_PREFIX: str = "_"
TEST_FUNCTION_MODULE_BASENAME_PATTERN: re.Pattern[str] = re.compile(r"^(test_.+|.+_test)\.py$")
FIXTURE_DECORATOR_MARKER: str = "fixture"
SELF_PARAMETER_NAME: str = "self"
CLASS_METHOD_FIRST_PARAMETER_NAME: str = "cls"
MINIMUM_CONSTANT_NAME_LENGTH: int = 2
MAX_TEST_LAYOUT_ISSUES: int = 50
DEAD_TEST_CONSTANT_GUIDANCE: str = (
    "module-level constant is defined in this test module but read by no other"
    " line in the file - remove the dead constant, or reference it where its"
    " value is needed (CODE_RULES §9.8)"
)
UNUSED_TEST_HELPER_PARAMETER_GUIDANCE: str = (
    "parameter is declared on this private test helper but read nowhere in its"
    " body - drop the dead parameter and stop forwarding it at every call site"
)
