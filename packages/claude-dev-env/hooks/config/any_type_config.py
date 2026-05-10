"""Configuration constants for the Any/cast escape-hatch check."""

ALL_ANY_ALLOWED_PATTERNS: tuple[str, ...] = (
    "__init__.py",
    "protocols.py",
    "types.py",
    "conftest.py",
)
