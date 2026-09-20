"""Exit 0 when every function in a Python file spans at most the given line count.

Exit 1 when one is longer, 3 when the file is missing or does not parse.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

from config.max_function_length_constants import EXPECTED_ARGUMENT_COUNT, HARNESS_EXIT


def main(all_arguments: list[str]) -> int:
    """Grade a Python file by the span of its longest function.

    ::

        arguments: reports/summary.py 25
        longest function spans 18 lines   ->   exit 0
        longest function spans 40 lines   ->   exit 1

    Args:
        all_arguments: The path of the Python file to read, then the line count
            each function must stay within.

    Returns:
        0 when every function spans at most that line count, 1 when one spans
        more, and the harness exit code when the arguments are wrong, the file
        is missing, the file does not parse, or the file defines no function.
    """
    if len(all_arguments) != EXPECTED_ARGUMENT_COUNT or not Path(all_arguments[0]).is_file():
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
