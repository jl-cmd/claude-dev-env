#!/usr/bin/env python3
"""
CODE_RULES.md enforcer - blocks code that violates mandatory rules.

Checks (blocking):
1. No comments (# or // in code, excluding shebangs/type: ignore)
2. Imports at top (no imports inside functions)
3. Logging f-strings (log_* calls must use format args)
4. Windows API None (win32gui calls with None parameter)
5. Magic values (literals in function bodies)
6. E2E test naming (no online/offline in test names)
7. Constants outside config (UPPER_SNAKE = in non-config files)

Advisory only (non-blocking):
- File line count: stderr warning at 400 lines (soft) and 1000 lines (hard)
"""
import ast
import io
import json
import re
import sys
import tokenize
from typing import Optional

PYTHON_EXTENSIONS = {".py"}
JAVASCRIPT_EXTENSIONS = {".js", ".ts", ".tsx", ".jsx"}
ALL_CODE_EXTENSIONS = PYTHON_EXTENSIONS | JAVASCRIPT_EXTENSIONS

CONFIG_PATH_PATTERNS = {"config/", "config\\", "/config.", "\\config.", "settings.py"}
TEST_PATH_PATTERNS = {"test_", "_test.", ".test.", ".spec.", "/tests/", "\\tests\\", "/tests.py", "\\tests.py"}
HOOK_INFRASTRUCTURE_PATTERNS = {"/.claude/hooks/", "\\.claude\\hooks\\", "\\.claude/hooks/", "/packages/claude-dev-env/hooks/", "\\packages\\claude-dev-env\\hooks\\"}
WORKFLOW_REGISTRY_PATTERNS = {"/workflow/", "\\workflow\\", "_tab.py", "/states.py", "\\states.py", "/modules.py", "\\modules.py"}
MIGRATION_PATH_PATTERNS = {"/migrations/", "\\migrations\\"}

ADVISORY_LINE_THRESHOLD_SOFT = 400
ADVISORY_LINE_THRESHOLD_HARD = 1000


TYPE_CHECKING_BLOCK_PATTERN = re.compile(r"^(?P<indent>\s*)if\s+(typing\.)?TYPE_CHECKING\s*:\s*$")
IMPORT_STATEMENT_PREFIXES: tuple[str, ...] = ("import ", "from ")
NOT_INSIDE_TYPE_CHECKING_BLOCK = -1
MAX_ISSUES_PER_CHECK = 3


def get_file_extension(file_path: str) -> str:
    """Extract lowercase file extension."""
    dot_index = file_path.rfind(".")
    if dot_index == -1:
        return ""
    return file_path[dot_index:].lower()


def is_hook_infrastructure(file_path: str) -> bool:
    """Check if file is a Claude Code hook (standalone infrastructure, not project code)."""
    path_lower = file_path.lower().replace("\\", "/")
    return any(pattern.replace("\\", "/") in path_lower for pattern in HOOK_INFRASTRUCTURE_PATTERNS)


def is_config_file(file_path: str) -> bool:
    """Check if file is in a config directory or is a config file."""
    path_lower = file_path.lower()
    return any(pattern in path_lower for pattern in CONFIG_PATH_PATTERNS)


def is_test_file(file_path: str) -> bool:
    """Check if file is a test file."""
    path_lower = file_path.lower()
    basename_lower = path_lower.replace("\\", "/").rsplit("/", 1)[-1]
    if basename_lower == "conftest.py":
        return True
    return any(pattern in path_lower for pattern in TEST_PATH_PATTERNS)


def is_workflow_registry_file(file_path: str) -> bool:
    """Check if file is a workflow state/module registry file.

    Workflow tab files and state/module registry files use UPPER_SNAKE naming
    for StateDefinition and WorkflowModule instances by architectural convention.
    These are module-level singletons, not misplaced literal constants.
    """
    path_lower = file_path.lower().replace("\\", "/")
    return any(pattern.replace("\\", "/") in path_lower for pattern in WORKFLOW_REGISTRY_PATTERNS)


def is_spec_file(file_path: str) -> bool:
    """Check if file is an E2E spec file."""
    return ".spec." in file_path.lower()


def check_comments_python(content: str) -> list[str]:
    """Check for comments in Python code."""
    issues = []
    lines = content.split("\n")

    for line_number, line in enumerate(lines, 1):
        stripped = line.strip()

        if not stripped:
            continue

        if stripped.startswith("#!"):
            continue

        if stripped.startswith("# type:"):
            continue

        if stripped.startswith("# noqa"):
            continue

        if stripped.startswith("# pylint:"):
            continue

        if stripped.startswith("# pragma:"):
            continue

        comment_index = line.find("#")
        if comment_index != -1:
            before_comment = line[:comment_index]
            if not before_comment.strip().startswith(("'", '"')):
                in_string = False
                quote_char = None
                for i, char in enumerate(before_comment):
                    if char in ("'", '"') and (i == 0 or before_comment[i - 1] != "\\"):
                        if not in_string:
                            in_string = True
                            quote_char = char
                        elif char == quote_char:
                            in_string = False

                if not in_string:
                    comment_text = line[comment_index + 1 :].strip()
                    if comment_text and not comment_text.startswith(("type:", "noqa", "pylint:", "pragma:")):
                        issues.append(f"Line {line_number}: Comment found - refactor to self-documenting code")

        if len(issues) >= 3:
            break

    return issues


def check_comments_javascript(content: str) -> list[str]:
    """Check for comments in JavaScript/TypeScript code."""
    issues = []
    lines = content.split("\n")
    in_multiline_comment = False

    for line_number, line in enumerate(lines, 1):
        stripped = line.strip()

        if not stripped:
            continue

        if in_multiline_comment:
            if "*/" in stripped:
                in_multiline_comment = False
            continue

        if stripped.startswith("/*"):
            in_multiline_comment = "*/" not in stripped
            if not stripped.startswith("/**"):
                issues.append(f"Line {line_number}: Block comment found - refactor to self-documenting code")
            continue

        if stripped.startswith("//"):
            if not stripped.startswith(("// @ts-", "// eslint-", "// prettier-", "/// ")):
                issues.append(f"Line {line_number}: Comment found - refactor to self-documenting code")

        if len(issues) >= 3:
            break

    return issues


def extract_comment_texts(content: str, file_path: str) -> tuple[set[str], set[str]]:
    """Extract normalized comment text strings from content for comparison.

    Returns:
        Tuple of (inline_comments, standalone_comments).
        Inline comments appear after code on the same line.
        Standalone comments are lines where the entire line is a comment.
    """
    extension = get_file_extension(file_path)
    inline_comments: set[str] = set()
    standalone_comments: set[str] = set()
    if not content:
        return inline_comments, standalone_comments

    lines = content.split("\n")

    if extension in PYTHON_EXTENSIONS:
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("#"):
                if stripped.startswith(("#!", "# type:", "# noqa", "# pylint:", "# pragma:")):
                    continue
                standalone_comments.add(stripped)
            elif "#" in line:
                comment_index = line.find("#")
                before_comment = line[:comment_index]
                if not before_comment.strip().startswith(("'", '"')):
                    in_string = False
                    quote_char = None
                    for i, char in enumerate(before_comment):
                        if char in ("'", '"') and (i == 0 or before_comment[i - 1] != "\\"):
                            if not in_string:
                                in_string = True
                                quote_char = char
                            elif char == quote_char:
                                in_string = False
                    if not in_string:
                        comment_text = line[comment_index + 1 :].strip()
                        if comment_text and not comment_text.startswith(("type:", "noqa", "pylint:", "pragma:")):
                            inline_comments.add(line[comment_index:].strip())

    elif extension in JAVASCRIPT_EXTENSIONS:
        in_multiline = False
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            if in_multiline:
                if "*/" in stripped:
                    in_multiline = False
                continue
            if stripped.startswith("/*"):
                in_multiline = "*/" not in stripped
                if not stripped.startswith("/**"):
                    standalone_comments.add(stripped)
                continue
            if stripped.startswith("//"):
                if not stripped.startswith(("// @ts-", "// eslint-", "// prettier-", "/// ")):
                    standalone_comments.add(stripped)
            elif "//" in line:
                before_slash = line[:line.index("//")]
                if before_slash.strip():
                    inline_comments.add(stripped[stripped.index("//"):])

    return inline_comments, standalone_comments


def check_comment_changes(old_content: str, new_content: str, file_path: str) -> list[str]:
    """Check for comment additions or removals between old and new content.

    Inline comments (after code on same line): BLOCK when added.
    Standalone comment lines: NUDGE (print advisory) when added.
    Existing comments being removed: BLOCK (comment preservation principle).
    """
    issues: list[str] = []

    old_inline, old_standalone = extract_comment_texts(old_content, file_path)
    new_inline, new_standalone = extract_comment_texts(new_content, file_path)

    added_inline = new_inline - old_inline
    if added_inline:
        sample = next(iter(added_inline))
        issues.append(f"Inline comment added: {sample[:60]} - refactor to self-documenting code")

    added_standalone = new_standalone - old_standalone
    if added_standalone:
        sample = next(iter(added_standalone))
        print(f"[CODE_RULES advisory] Standalone comment added: {sample[:60]} - prefer self-documenting code", file=sys.stderr)

    all_old = old_inline | old_standalone
    all_new = new_inline | new_standalone
    removed_comments = all_old - all_new
    if removed_comments:
        old_line_count = len([line for line in old_content.split("\n") if line.strip()])
        new_line_count = len([line for line in new_content.split("\n") if line.strip()])
        code_was_removed = new_line_count < old_line_count - len(removed_comments)
        if not code_was_removed:
            sample = next(iter(removed_comments))
            issues.append(f"Existing comment removed: {sample[:60]} - NEVER delete existing comments")

    return issues


def check_imports_at_top(content: str) -> list[str]:
    """Check for imports inside functions (Python only).

    An import lexically inside an ``if TYPE_CHECKING:`` block is exempt.
    An import inside a function body is flagged even if the file uses TYPE_CHECKING
    elsewhere at module scope.

    Only the innermost ``if TYPE_CHECKING:`` block is tracked: a second, nested
    ``if TYPE_CHECKING:`` header overwrites the outer block's indent so that when
    control dedents back to the outer block's body, the tracker resets.

    Known limitation: nested ``if TYPE_CHECKING:`` blocks are NOT supported. After
    a nested inner block ends, subsequent lines at the OUTER block's body indent
    are treated as outside any TYPE_CHECKING scope, so function-body imports there
    WILL be flagged as violations even though they are lexically guarded by the
    outer block. Rewrite to a single top-level ``if TYPE_CHECKING:`` block to avoid
    this false positive. Nested TYPE_CHECKING blocks are rare in practice, so this
    simpler single-level tracking is preferred over maintaining a stack of indent
    levels. The pinned behavior is covered by
    ``test_should_track_only_innermost_type_checking_block``.
    """
    issues: list[str] = []
    lines = content.split("\n")
    inside_function = False
    function_indent = 0
    type_checking_block_indent = NOT_INSIDE_TYPE_CHECKING_BLOCK

    for line_number, each_line in enumerate(lines, 1):
        stripped = each_line.strip()

        if not stripped:
            continue

        current_indent = len(each_line) - len(each_line.lstrip())

        if type_checking_block_indent != NOT_INSIDE_TYPE_CHECKING_BLOCK:
            if current_indent <= type_checking_block_indent:
                type_checking_block_indent = NOT_INSIDE_TYPE_CHECKING_BLOCK

        type_checking_match = TYPE_CHECKING_BLOCK_PATTERN.match(each_line)
        if type_checking_match:
            type_checking_block_indent = len(type_checking_match.group("indent"))
            continue

        function_match = re.match(r"^(\s*)(async\s+)?def\s+\w+", each_line)
        if function_match:
            inside_function = True
            function_indent = len(function_match.group(1)) if function_match.group(1) else 0
            continue

        if inside_function:
            if current_indent <= function_indent and stripped and not stripped.startswith(("#", "@", ")")):
                inside_function = False

        is_inside_type_checking_block = type_checking_block_indent != NOT_INSIDE_TYPE_CHECKING_BLOCK
        if inside_function and not is_inside_type_checking_block:
            if stripped.startswith(IMPORT_STATEMENT_PREFIXES):
                issues.append(f"Line {line_number}: Import inside function - move to top of file")

        if len(issues) >= MAX_ISSUES_PER_CHECK:
            break

    return issues


LOGGING_FSTRING_PATTERN = re.compile(
    r'\b(?:log_(?:debug|info|warning|error|critical|exception)'
    r'|(?:logger|logging|log)\.(?:debug|info|warning|error|critical|exception))'
    r'\s*\(\s*(?:[rR][fF]|[fF][rR]?)["\']'
)


def check_logging_fstrings(content: str) -> list[str]:
    """Check for f-strings in logging calls."""
    issues = []
    pattern = LOGGING_FSTRING_PATTERN

    for line_number, line in enumerate(content.split("\n"), 1):
        if pattern.search(line):
            issues.append(f"Line {line_number}: f-string in log call - use format args instead")

        if len(issues) >= 3:
            break

    return issues


def advise_file_line_count(content: str, file_path: str) -> None:
    """Emit non-blocking stderr advisories when a file crosses size smell thresholds.

    Thresholds are smell signals, not hard caps. See CODE_RULES.md "File length guidance"
    for rationale. Soft threshold aligns with Clean Code Ch. 5 / Fowler "Large Class".
    Hard threshold matches pylint default max-module-lines and SonarQube S104 default.
    """
    line_count = len(content.splitlines())
    if line_count >= ADVISORY_LINE_THRESHOLD_HARD:
        print(
            f"[CODE_RULES advisory] {file_path}: {line_count} lines - "
            f"exceeds pylint/SonarQube default ({ADVISORY_LINE_THRESHOLD_HARD}); "
            f"strongly consider splitting by responsibility (SRP / cohesion)",
            file=sys.stderr,
        )
    elif line_count >= ADVISORY_LINE_THRESHOLD_SOFT:
        print(
            f"[CODE_RULES advisory] {file_path}: {line_count} lines - "
            f"consider splitting (Clean Code Ch. 5; Fowler 'Large Class' smell)",
            file=sys.stderr,
        )


def check_windows_api_none(content: str) -> list[str]:
    """Check for win32gui calls with None parameter."""
    issues = []
    pattern = re.compile(r"win32gui\.\w+\s*\([^)]*,\s*None\s*\)")

    for line_number, line in enumerate(content.split("\n"), 1):
        if pattern.search(line):
            issues.append(f"Line {line_number}: win32gui call with None - use 0 for unused int params")

        if len(issues) >= 3:
            break

    return issues


def check_magic_values(content: str, file_path: str) -> list[str]:
    """Check for magic values in function bodies."""
    if is_config_file(file_path) or is_test_file(file_path):
        return []

    issues = []
    lines = content.split("\n")
    inside_function = False

    number_pattern = re.compile(r"(?<![.\w])(\d+\.?\d*)(?![.\w])")
    allowed_numbers = {"0", "1", "-1", "0.0", "1.0"}

    for line_number, line in enumerate(lines, 1):
        stripped = line.strip()

        if not stripped:
            continue

        if re.match(r"^(async\s+)?def\s+\w+", stripped):
            inside_function = True
            continue

        if re.match(r"^class\s+\w+", stripped):
            inside_function = False
            continue

        if inside_function:
            if "=" in stripped and stripped.split("=")[0].strip().isupper():
                continue

            if stripped.startswith(("return", "yield", "raise")):
                continue

            numbers_found = number_pattern.findall(stripped)
            for number in numbers_found:
                if number not in allowed_numbers:
                    if "range(" in stripped or "enumerate(" in stripped:
                        continue
                    if "[" in stripped and "]" in stripped:
                        continue
                    issues.append(f"Line {line_number}: Magic value {number} - extract to named constant")
                    break

        if len(issues) >= 3:
            break

    return issues


def check_e2e_test_naming(content: str, file_path: str) -> list[str]:
    """Check for online/offline in test names (spec files only)."""
    if not is_spec_file(file_path):
        return []

    issues = []
    pattern = re.compile(r'(test|it|describe)\s*\(\s*["\'][^"\']*\b(online|offline)\b[^"\']*["\']', re.IGNORECASE)

    for line_number, line in enumerate(content.split("\n"), 1):
        if pattern.search(line):
            issues.append(f"Line {line_number}: Test name contains online/offline - file scope defines this")

        if len(issues) >= 3:
            break

    return issues


def _render_annotation_source(annotation_node: ast.expr) -> str:
    """Return a textual representation of an annotation AST node."""
    unparse_function = getattr(ast, "unparse", None)
    if unparse_function is not None:
        return unparse_function(annotation_node)
    sys.stderr.write(
        "code-rules-enforcer: ast.unparse unavailable on this interpreter; "
        "falling back to ast.dump for Any detection.\n"
    )
    return ast.dump(annotation_node)


def _annotation_uses_any(annotation_node: Optional[ast.expr]) -> bool:
    """Return True when an annotation AST node textually references Any."""
    if annotation_node is None:
        return False
    annotation_source = _render_annotation_source(annotation_node)
    return bool(re.search(r"\bAny\b", annotation_source))


def _collect_annotated_arguments(function_node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[ast.arg]:
    """Return every argument node on a function that may carry an annotation."""
    arguments = function_node.args
    all_annotated_arguments: list[ast.arg] = []
    all_annotated_arguments.extend(arguments.posonlyargs)
    all_annotated_arguments.extend(arguments.args)
    all_annotated_arguments.extend(arguments.kwonlyargs)
    if arguments.vararg is not None:
        all_annotated_arguments.append(arguments.vararg)
    if arguments.kwarg is not None:
        all_annotated_arguments.append(arguments.kwarg)
    return all_annotated_arguments


def _find_any_annotation_lines(source: str) -> list[int]:
    """Return line numbers of annotations that textually reference Any."""
    try:
        parsed_tree = ast.parse(source)
    except SyntaxError:
        return []

    offending_line_numbers: list[int] = []
    already_reported_lines: set[int] = set()
    for each_node in ast.walk(parsed_tree):
        if isinstance(each_node, ast.AnnAssign) and _annotation_uses_any(each_node.annotation):
            if each_node.lineno not in already_reported_lines:
                offending_line_numbers.append(each_node.lineno)
                already_reported_lines.add(each_node.lineno)
            continue
        if isinstance(each_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if _annotation_uses_any(each_node.returns) and each_node.lineno not in already_reported_lines:
                offending_line_numbers.append(each_node.lineno)
                already_reported_lines.add(each_node.lineno)
            for each_argument in _collect_annotated_arguments(each_node):
                if _annotation_uses_any(each_argument.annotation) and each_argument.lineno not in already_reported_lines:
                    offending_line_numbers.append(each_argument.lineno)
                    already_reported_lines.add(each_argument.lineno)
    return offending_line_numbers


def _comment_tokens(source: str) -> list[tokenize.TokenInfo]:
    """Return COMMENT tokens from source, or an empty list when tokenization fails."""
    try:
        return [
            each_token
            for each_token in tokenize.generate_tokens(io.StringIO(source).readline)
            if each_token.type == tokenize.COMMENT
        ]
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return []


def _find_unjustified_type_ignore_lines(source: str) -> list[int]:
    """Return line numbers of # type: ignore comments lacking a trailing reason."""
    ignore_pattern = re.compile(r"#\s*type:\s*ignore(?:\[[^\]]*\])?(.*)$")
    minimum_justification_characters = len("xxxxx")
    offending_line_numbers: list[int] = []
    for each_comment_token in _comment_tokens(source):
        matched = ignore_pattern.search(each_comment_token.string)
        if not matched:
            continue
        line_number = each_comment_token.start[0]
        trailing_text = matched.group(1).strip()
        if not trailing_text.startswith("#"):
            offending_line_numbers.append(line_number)
            continue
        justification_text = trailing_text.lstrip("#").strip()
        if len(justification_text) < minimum_justification_characters:
            offending_line_numbers.append(line_number)
    return offending_line_numbers


def check_type_escape_hatches(content: str, file_path: str) -> list[str]:
    """Flag Any annotations and unjustified # type: ignore comments."""
    if is_test_file(file_path):
        return []

    issues: list[str] = []

    for each_any_line in _find_any_annotation_lines(content):
        issues.append(f"Line {each_any_line}: Any annotation - replace with explicit type")

    for each_ignore_line in _find_unjustified_type_ignore_lines(content):
        issues.append(
            f"Line {each_ignore_line}: Unjustified # type: ignore - add trailing '# reason' explaining why"
        )

    return issues


def is_migration_file(file_path: str) -> bool:
    """Check if file is a Django migration (must be self-contained)."""
    path_lower = file_path.lower().replace("\\", "/")
    return any(pattern.replace("\\", "/") in path_lower for pattern in MIGRATION_PATH_PATTERNS)


def check_constants_outside_config(content: str, file_path: str) -> list[str]:
    """Check for UPPER_SNAKE constants defined outside config files."""
    if is_config_file(file_path):
        return []

    if is_test_file(file_path):
        return []

    if is_workflow_registry_file(file_path):
        return []

    if is_migration_file(file_path):
        return []

    issues = []
    lines = content.split("\n")
    inside_function = False
    inside_class = False

    constant_pattern = re.compile(r"^([A-Z][A-Z0-9_]{2,})\s*=\s*[^=]")

    for line_number, line in enumerate(lines, 1):
        stripped = line.strip()

        if not stripped:
            continue

        if re.match(r"^(async\s+)?def\s+\w+", stripped):
            inside_function = True
            continue

        if re.match(r"^class\s+\w+", stripped):
            inside_class = True
            inside_function = False
            continue

        indent = len(line) - len(line.lstrip())
        if indent == 0 and stripped and not stripped.startswith(("#", "@", ")")):
            inside_function = False
            inside_class = False

        if not inside_function and not inside_class:
            match = constant_pattern.match(stripped)
            if match:
                constant_name = match.group(1)
                if constant_name not in ("__all__",):
                    issues.append(f"Line {line_number}: Constant {constant_name} - move to config/")

        if len(issues) >= 3:
            break

    return issues


BANNED_IDENTIFIERS: frozenset[str] = frozenset({"result", "data", "output", "response", "value", "item", "temp"})
MAX_BANNED_IDENTIFIER_ISSUES: int = 3
BANNED_IDENTIFIER_MESSAGE_SUFFIX: str = "use descriptive name (see CODE_RULES Naming section)"
BANNED_IDENTIFIER_SKIP_ADVISORY: str = (
    "banned-identifier check skipped: file did not parse as Python"
)


def _collect_banned_names_from_target(target: ast.expr) -> list[ast.Name]:
    """Return every banned ast.Name reachable through tuple/list unpacking or starred targets."""
    if isinstance(target, ast.Name):
        if target.id in BANNED_IDENTIFIERS:
            return [target]
        return []
    if isinstance(target, (ast.Tuple, ast.List)):
        banned_names: list[ast.Name] = []
        for each_element in target.elts:
            banned_names.extend(_collect_banned_names_from_target(each_element))
        return banned_names
    if isinstance(target, ast.Starred):
        return _collect_banned_names_from_target(target.value)
    return []


def _collect_banned_names_from_node(node: ast.AST) -> list[ast.Name]:
    """Return banned ast.Name nodes introduced by a single binding construct."""
    if isinstance(node, ast.Assign):
        banned_names: list[ast.Name] = []
        for each_target in node.targets:
            banned_names.extend(_collect_banned_names_from_target(each_target))
        return banned_names
    if isinstance(node, ast.AnnAssign):
        return _collect_banned_names_from_target(node.target)
    if isinstance(node, (ast.For, ast.AsyncFor)):
        return _collect_banned_names_from_target(node.target)
    if isinstance(node, ast.comprehension):
        return _collect_banned_names_from_target(node.target)
    if isinstance(node, ast.withitem):
        if node.optional_vars is None:
            return []
        return _collect_banned_names_from_target(node.optional_vars)
    if isinstance(node, ast.NamedExpr):
        return _collect_banned_names_from_target(node.target)
    return []


def check_banned_identifiers(content: str, file_path: str) -> list[str]:
    """Flag assignments to identifiers banned by the project Naming rules."""
    if is_test_file(file_path) or is_hook_infrastructure(file_path):
        return []

    try:
        parsed_tree = ast.parse(content)
    except SyntaxError:
        print(f"{file_path}: {BANNED_IDENTIFIER_SKIP_ADVISORY}", file=sys.stderr)
        return []

    banned_name_nodes: list[ast.Name] = []
    for each_node in ast.walk(parsed_tree):
        banned_name_nodes.extend(_collect_banned_names_from_node(each_node))

    banned_name_nodes.sort(key=lambda each_name: (each_name.lineno, each_name.col_offset))

    issues: list[str] = []
    for each_name in banned_name_nodes:
        issues.append(
            f"Line {each_name.lineno}: Banned identifier '{each_name.id}' - {BANNED_IDENTIFIER_MESSAGE_SUFFIX}"
        )
        if len(issues) >= MAX_BANNED_IDENTIFIER_ISSUES:
            break

    return issues


def validate_content(content: str, file_path: str, old_content: str = "") -> list[str]:
    """Run all applicable validators on content.

    Args:
        content: The new content being written.
        file_path: Path to the file.
        old_content: Previous content (old_string for Edit, existing file for Write).
            Used to detect comment additions/removals instead of flagging all comments.
    """
    extension = get_file_extension(file_path)
    all_issues = []

    if extension in PYTHON_EXTENSIONS:
        if not is_test_file(file_path):
            all_issues.extend(check_comment_changes(old_content, content, file_path))
        all_issues.extend(check_imports_at_top(content))
        all_issues.extend(check_logging_fstrings(content))
        all_issues.extend(check_windows_api_none(content))
        all_issues.extend(check_magic_values(content, file_path))
        all_issues.extend(check_constants_outside_config(content, file_path))
        all_issues.extend(check_type_escape_hatches(content, file_path))
        all_issues.extend(check_banned_identifiers(content, file_path))

    elif extension in JAVASCRIPT_EXTENSIONS:
        if not is_test_file(file_path):
            all_issues.extend(check_comment_changes(old_content, content, file_path))
        all_issues.extend(check_e2e_test_naming(content, file_path))

    if extension in ALL_CODE_EXTENSIONS:
        advise_file_line_count(content, file_path)

    return all_issues


def main() -> None:
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})
    file_path = tool_input.get("file_path", "")

    if not file_path:
        sys.exit(0)

    if is_hook_infrastructure(file_path):
        sys.exit(0)

    extension = get_file_extension(file_path)
    if extension not in ALL_CODE_EXTENSIONS:
        sys.exit(0)

    old_content = ""
    if tool_name == "Edit":
        content = tool_input.get("new_string", "")
        old_content = tool_input.get("old_string", "")
    else:
        content = tool_input.get("content", "") or tool_input.get("new_string", "")
        try:
            with open(file_path, "r", encoding="utf-8") as existing_file:
                old_content = existing_file.read()
        except (FileNotFoundError, OSError, UnicodeDecodeError):
            old_content = ""

        if old_content:
            sys.exit(0)

    if not content:
        sys.exit(0)

    issues = validate_content(content, file_path, old_content)

    if issues:
        issue_list = "; ".join(issues[:10])
        result = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": f"BLOCKED: [CODE_RULES] {len(issues)} violation(s): {issue_list}",
            }
        }
        print(json.dumps(result))
        sys.stdout.flush()

    sys.exit(0)


if __name__ == "__main__":
    main()
