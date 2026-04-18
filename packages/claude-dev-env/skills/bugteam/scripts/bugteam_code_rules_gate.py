from __future__ import annotations

import argparse
import importlib.util
import re
import subprocess
import sys
from pathlib import Path


def hunk_header_pattern() -> re.Pattern[str]:
    return re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


def violation_line_pattern() -> re.Pattern[str]:
    return re.compile(r"^Line (\d+):")


def resolve_claude_dev_env_root() -> Path:
    environment_value = (Path(__file__).resolve().parents[3]).resolve()
    return environment_value


def load_validate_content():
    package_root = resolve_claude_dev_env_root()
    enforcer_path = package_root / "hooks" / "blocking" / "code_rules_enforcer.py"
    if not enforcer_path.is_file():
        message = f"bugteam_code_rules_gate: missing enforcer at {enforcer_path}"
        print(message, file=sys.stderr)
        raise SystemExit(2)
    specification = importlib.util.spec_from_file_location(
        "code_rules_enforcer",
        enforcer_path,
    )
    if specification is None or specification.loader is None:
        print("bugteam_code_rules_gate: could not load code_rules_enforcer.", file=sys.stderr)
        raise SystemExit(2)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module.validate_content


def resolve_merge_base(repository_root: Path, base_reference: str) -> str:
    merge_result = subprocess.run(
        ["git", "merge-base", "HEAD", base_reference],
        cwd=str(repository_root),
        capture_output=True,
        text=True,
        check=False,
    )
    if merge_result.returncode != 0:
        print(
            f"bugteam_code_rules_gate: git merge-base HEAD {base_reference} failed:\n"
            f"{merge_result.stderr}",
            file=sys.stderr,
        )
        raise SystemExit(2)
    return merge_result.stdout.strip()


def paths_from_git_diff(repository_root: Path, base_reference: str) -> list[Path]:
    merge_base = resolve_merge_base(repository_root, base_reference)
    name_result = subprocess.run(
        ["git", "diff", "--name-only", f"{merge_base}..HEAD"],
        cwd=str(repository_root),
        capture_output=True,
        text=True,
        check=False,
    )
    if name_result.returncode != 0:
        print(
            f"bugteam_code_rules_gate: git diff --name-only failed:\n{name_result.stderr}",
            file=sys.stderr,
        )
        raise SystemExit(2)
    relative_paths = [line.strip() for line in name_result.stdout.splitlines() if line.strip()]
    return [repository_root / relative_path for relative_path in relative_paths]


def is_code_path(file_path: Path) -> bool:
    suffix = file_path.suffix.lower()
    return suffix in {".py", ".js", ".ts", ".tsx", ".jsx"}


def parse_added_line_numbers(unified_diff_text: str) -> set[int]:
    header_regex = hunk_header_pattern()
    added_line_numbers: set[int] = set()
    for each_line in unified_diff_text.splitlines():
        header_match = header_regex.match(each_line)
        if header_match is None:
            continue
        new_start_text, new_count_text = header_match.groups()
        new_start = int(new_start_text)
        new_count = 1 if new_count_text is None else int(new_count_text)
        if new_count <= 0:
            continue
        for each_number in range(new_start, new_start + new_count):
            added_line_numbers.add(each_number)
    return added_line_numbers


def is_file_new_at_base(
    repository_root: Path,
    merge_base: str,
    relative_path_posix: str,
) -> bool:
    cat_result = subprocess.run(
        ["git", "cat-file", "-e", f"{merge_base}:{relative_path_posix}"],
        cwd=str(repository_root),
        capture_output=True,
        text=True,
        check=False,
    )
    return cat_result.returncode != 0


def added_lines_for_file(
    repository_root: Path,
    merge_base: str,
    relative_path_posix: str,
) -> set[int]:
    diff_result = subprocess.run(
        ["git", "diff", "--unified=0", f"{merge_base}..HEAD", "--", relative_path_posix],
        cwd=str(repository_root),
        capture_output=True,
        text=True,
        check=False,
    )
    if diff_result.returncode != 0:
        print(
            f"bugteam_code_rules_gate: git diff --unified=0 failed for {relative_path_posix}:\n"
            f"{diff_result.stderr}",
            file=sys.stderr,
        )
        raise SystemExit(2)
    if not diff_result.stdout.strip():
        return set()
    return parse_added_line_numbers(diff_result.stdout)


def whole_file_line_set(file_path: Path) -> set[int]:
    try:
        total_lines = len(file_path.read_text().splitlines())
    except OSError:
        return set()
    if total_lines <= 0:
        return set()
    return set(range(1, total_lines + 1))


def added_lines_by_file(
    repository_root: Path,
    base_reference: str,
    file_paths: list[Path],
) -> dict[Path, set[int]]:
    merge_base = resolve_merge_base(repository_root, base_reference)
    resolved_root = repository_root.resolve()
    added_by_path: dict[Path, set[int]] = {}
    for each_path in file_paths:
        try:
            resolved = each_path.resolve()
        except OSError:
            continue
        try:
            relative = resolved.relative_to(resolved_root)
        except ValueError:
            continue
        relative_posix = str(relative).replace("\\", "/")
        added_numbers = added_lines_for_file(resolved_root, merge_base, relative_posix)
        if not added_numbers and resolved.is_file():
            if is_file_new_at_base(resolved_root, merge_base, relative_posix):
                added_numbers = whole_file_line_set(resolved)
        added_by_path[resolved] = added_numbers
    return added_by_path


def extract_violation_line_number(violation_text: str) -> int | None:
    match_result = violation_line_pattern().match(violation_text)
    if match_result is None:
        return None
    return int(match_result.group(1))


def split_violations_by_scope(
    issues: list[str],
    added_line_numbers: set[int] | None,
) -> tuple[list[str], list[str]]:
    if added_line_numbers is None:
        return list(issues), []
    blocking: list[str] = []
    advisory: list[str] = []
    for each_issue in issues:
        violation_line = extract_violation_line_number(each_issue)
        if violation_line is None:
            blocking.append(each_issue)
            continue
        if violation_line in added_line_numbers:
            blocking.append(each_issue)
        else:
            advisory.append(each_issue)
    return blocking, advisory


def print_violation_section(
    header_message: str,
    violations_by_file: dict[Path, list[str]],
    repository_root: Path,
) -> None:
    print(header_message, file=sys.stderr)
    resolved_root = repository_root.resolve()
    for each_path in sorted(violations_by_file.keys()):
        relative = each_path.relative_to(resolved_root)
        print(f"{relative}:", file=sys.stderr)
        for each_issue in violations_by_file[each_path]:
            print(f"  {each_issue}", file=sys.stderr)


def run_gate(
    validate_content,
    file_paths: list[Path],
    repository_root: Path,
    added_lines_map: dict[Path, set[int]] | None = None,
) -> int:
    blocking_by_file: dict[Path, list[str]] = {}
    advisory_by_file: dict[Path, list[str]] = {}
    for file_path in sorted(set(file_paths)):
        try:
            resolved = file_path.resolve()
        except OSError:
            continue
        try:
            resolved.relative_to(repository_root.resolve())
        except ValueError:
            continue
        if not is_code_path(resolved):
            continue
        if not resolved.is_file():
            continue
        try:
            content = resolved.read_text(encoding="utf-8")
        except OSError:
            print(f"bugteam_code_rules_gate: skip unreadable {resolved}", file=sys.stderr)
            continue
        relative = resolved.relative_to(repository_root.resolve())
        issues = validate_content(content, str(relative).replace("\\", "/"), old_content=content)
        if not issues:
            continue
        added_for_file = None if added_lines_map is None else added_lines_map.get(resolved)
        blocking, advisory = split_violations_by_scope(issues, added_for_file)
        if blocking:
            blocking_by_file[resolved] = blocking
        if advisory:
            advisory_by_file[resolved] = advisory
    blocking_count = sum(len(each_list) for each_list in blocking_by_file.values())
    advisory_count = sum(len(each_list) for each_list in advisory_by_file.values())
    if blocking_count:
        if added_lines_map is None:
            header = f"bugteam_code_rules_gate: {blocking_count} violation(s) reported."
        else:
            header = (
                f"bugteam_code_rules_gate: {blocking_count} violation(s) "
                "introduced on changed lines:"
            )
        print_violation_section(
            header,
            blocking_by_file,
            repository_root,
        )
    if advisory_count:
        if blocking_count:
            print("", file=sys.stderr)
        print_violation_section(
            (
                f"bugteam_code_rules_gate: {advisory_count} pre-existing violation(s) "
                "in touched files (advisory, not blocking):"
            ),
            advisory_by_file,
            repository_root,
        )
    if blocking_count:
        return 1
    return 0


def parse_arguments(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run CODE_RULES validators (validate_content) on files in the working tree. "
            "Default file set: git diff --name-only merge-base(base)..HEAD."
        ),
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Repository root (default: cwd).",
    )
    parser.add_argument(
        "--base",
        default="origin/main",
        help="Merge-base ref for git diff (default: origin/main).",
    )
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        help="Optional explicit files; if set, git diff is not used.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    arguments = parse_arguments(sys.argv[1:] if argv is None else argv)
    repository_root = (
        arguments.repo_root.resolve()
        if arguments.repo_root is not None
        else Path.cwd().resolve()
    )
    validate_content = load_validate_content()
    if arguments.paths:
        file_paths = [repository_root / path for path in arguments.paths]
        return run_gate(validate_content, file_paths, repository_root, added_lines_map=None)
    file_paths = paths_from_git_diff(repository_root, arguments.base)
    scoped_added_lines = added_lines_by_file(repository_root, arguments.base, file_paths)
    return run_gate(
        validate_content,
        file_paths,
        repository_root,
        added_lines_map=scoped_added_lines,
    )


if __name__ == "__main__":
    raise SystemExit(main())
