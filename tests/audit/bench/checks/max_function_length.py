"""Exit 0 when every function in a Python file spans at most the given line count.

Exit 1 when one is longer, 3 when the file is missing or does not parse.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

HARNESS_EXIT = 3


def main(all_arguments: list[str]) -> int:
    if len(all_arguments) != 2 or not Path(all_arguments[0]).is_file():
        return HARNESS_EXIT
    try:
        tree = ast.parse(Path(all_arguments[0]).read_text(encoding="utf-8"))
    except SyntaxError:
        return HARNESS_EXIT
    all_lengths = [
        (each_node.end_lineno or each_node.lineno) - each_node.lineno + 1
        for each_node in ast.walk(tree)
        if isinstance(each_node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    if not all_lengths:
        return HARNESS_EXIT
    return 0 if max(all_lengths) <= int(all_arguments[1]) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
