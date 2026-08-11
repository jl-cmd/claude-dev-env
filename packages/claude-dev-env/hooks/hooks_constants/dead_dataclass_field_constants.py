"""Constants for the dead dataclass-field detector in ``code_rules_enforcer``.

Lives under the hooks-tree ``hooks_constants`` package so module-level
UPPER_SNAKE constants satisfy the CODE_RULES "constants live in config"
requirement and share a home with the other hook-tree configuration.
"""

ALL_DATACLASS_DECORATOR_NAMES: frozenset[str] = frozenset({"dataclass", "dataclasses"})
ATTRGETTER_FUNCTION_NAME: str = "attrgetter"
CLASSVAR_ANNOTATION_NAME: str = "ClassVar"
GETATTR_FUNCTION_NAME: str = "getattr"
GETATTR_NAME_ARGUMENT_MINIMUM: int = 2
ALL_REFLECTIVE_FIELD_CONSUMER_NAMES: frozenset[str] = frozenset(
    {"asdict", "astuple", "fields", "replace", "vars"}
)
WHOLE_INSTANCE_DICT_ATTRIBUTE_NAME: str = "__dict__"
ALL_WHOLE_INSTANCE_STRINGIFY_NAMES: frozenset[str] = frozenset(
    {"str", "repr", "format"}
)
MAX_DEAD_DATACLASS_FIELD_ISSUES: int = 25
DEAD_DATACLASS_FIELD_GUIDANCE: str = (
    "Field is assigned in this file and needs a read. Read it where the value is"
    " needed or remove the field and its population code (CODE_RULES §9.8)."
)
