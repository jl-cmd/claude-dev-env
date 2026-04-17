"""Magic value detection validator.

Implements check 7: No hardcoded magic values.
Use named constants instead of magic numbers.

Note: Only checks for magic numbers. Magic string detection is not implemented.
"""

import ast
import re
import sys
from pathlib import Path
from typing import Dict, FrozenSet, List, Tuple, Type

from validator_base import Violation


ALLOWED_NUMBERS: FrozenSet[int] = frozenset({-1, 0, 1, 2, 100})

_UPPER_SNAKE_NAME_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*$")

_CONTAINER_LITERAL_TYPES: Tuple[Type[ast.AST], ...] = (
    ast.Dict,
    ast.List,
    ast.Tuple,
    ast.Set,
)


def check_magic_values(tree: ast.AST, filename: str) -> List[Violation]:
    violations: List[Violation] = []
    parent_by_child = _build_parent_map(tree)

    for node in ast.walk(tree):
        if isinstance(node, ast.Constant):
            if isinstance(node.value, int) and node.value not in ALLOWED_NUMBERS:
                if not _is_in_constant_definition(node, parent_by_child):
                    violations.append(
                        Violation(
                            filename,
                            node.lineno,
                            f"Magic number {node.value} - use named constant",
                        )
                    )

    return violations


def _build_parent_map(tree: ast.AST) -> Dict[int, ast.AST]:
    parent_by_child: Dict[int, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parent_by_child[id(child)] = parent
    return parent_by_child


def _is_in_constant_definition(
    node: ast.Constant,
    parent_by_child: Dict[int, ast.AST],
) -> bool:
    current_node: ast.AST = node
    while id(current_node) in parent_by_child:
        parent = parent_by_child[id(current_node)]
        if _is_upper_snake_constant_assignment(parent):
            return True
        if not isinstance(parent, _CONTAINER_LITERAL_TYPES):
            return False
        current_node = parent
    return False


def _is_upper_snake_constant_assignment(node: ast.AST) -> bool:
    if isinstance(node, ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Name) and _is_upper_snake_name(target.id):
                return True
        return False
    if isinstance(node, ast.AnnAssign):
        target = node.target
        return isinstance(target, ast.Name) and _is_upper_snake_name(target.id)
    return False


def _is_upper_snake_name(name: str) -> bool:
    return bool(_UPPER_SNAKE_NAME_PATTERN.match(name))


def validate_file(file_path: Path) -> List[Violation]:
    filename = str(file_path)
    try:
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except Exception as error:
        return [Violation(filename, 0, f"Error: {error}")]

    return check_magic_values(tree, filename)


def main() -> int:
    if len(sys.argv) < 2:
        return 1

    all_violations: List[Violation] = []
    for file_arg in sys.argv[1:]:
        all_violations.extend(validate_file(Path(file_arg)))

    for violation in all_violations:
        print(violation)

    return 1 if all_violations else 0


if __name__ == "__main__":
    sys.exit(main())
