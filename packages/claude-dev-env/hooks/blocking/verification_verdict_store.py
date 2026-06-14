"""Shared verdict storage and branch-diff logic for the verified-commit gate.

The verified-commit workflow has two halves that must agree byte-for-byte on
what a verdict covers: ``verifier_verdict_minter.py`` (SubagentStop) writes a
verdict bound to the current change surface, and ``verified_commit_gate.py``
(PreToolUse on Bash) refuses ``git commit`` / ``git push`` unless a verdict
matching the live surface exists. This module owns that shared contract:
locating the repo, computing the canonical surface manifest and its hash,
deriving the verdict file path, deciding the mechanical docs-only exemption,
and reading/writing verdict files.
"""

from __future__ import annotations

import ast
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

blocking_directory = str(Path(__file__).resolve().parent)
if blocking_directory not in sys.path:
    sys.path.insert(0, blocking_directory)

from config.verified_commit_constants import (
    CLAUDE_HOME_DIRECTORY_NAME,
    CONFTEST_FILE_NAME,
    DOCS_ONLY_EXTENSIONS,
    ALL_FALLBACK_BASE_REFERENCES,
    GIT_TIMEOUT_SECONDS,
    MINIMUM_STATUS_FIELD_COUNT,
    PYTHON_EXTENSION,
    ROOT_KEY_HEX_LENGTH,
    TEST_FILE_PREFIX,
    TEST_FILE_SUFFIX,
    ALL_TOOLING_STATE_PREFIXES,
    VERDICT_DIRECTORY_NAME,
    VERDICT_JSON_INDENT,
    VERDICT_KEY_ALL_PASS,
    VERDICT_KEY_MANIFEST_SHA256,
)


def run_git(repo_directory: str, *git_arguments: str) -> str | None:
    """Run a git command and return its stdout, or None on any failure.

    Args:
        repo_directory: Directory git runs in (``git -C``).
        *git_arguments: The git subcommand and its arguments.

    Returns:
        Decoded stdout with trailing whitespace stripped, or None when git
        exits nonzero, times out, or is not installed.
    """
    try:
        completed_process = subprocess.run(
            ["git", "-C", repo_directory, *git_arguments],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=GIT_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed_process.returncode != 0:
        return None
    return completed_process.stdout.rstrip()


def resolve_repo_root(start_directory: str) -> str | None:
    """Resolve the repository top level for a directory.

    Args:
        start_directory: Any directory inside (or outside) a work tree.

    Returns:
        The absolute repo root path, or None when the directory is not
        inside a git work tree.
    """
    return run_git(start_directory, "rev-parse", "--show-toplevel")


def _tracked_upstream_reference(repo_root: str) -> str | None:
    """Read HEAD's configured upstream tracking reference.

    Args:
        repo_root: The repository top-level directory.

    Returns:
        The upstream reference (``origin/develop`` and the like) when HEAD
        tracks one, or None when no upstream is configured.
    """
    return run_git(
        repo_root, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"
    )


def candidate_base_references(repo_root: str) -> tuple[str, ...]:
    """Collect the upstream references to probe for the merge base, in order.

    Probes ``origin/HEAD`` first, then HEAD's configured upstream tracking
    reference (so a non-standard default branch like ``origin/develop`` is
    found regardless of its name), then the fixed ``origin/main`` /
    ``origin/master`` fallbacks for checkouts with no tracking ref set.

    Args:
        repo_root: The repository top-level directory.

    Returns:
        The ordered upstream references to try, with duplicates removed.
    """
    upstream_head = run_git(repo_root, "symbolic-ref", "--quiet", "refs/remotes/origin/HEAD")
    tracked_upstream = _tracked_upstream_reference(repo_root)
    ordered_references = (
        ((upstream_head,) if upstream_head else ())
        + ((tracked_upstream,) if tracked_upstream else ())
        + ALL_FALLBACK_BASE_REFERENCES
    )
    return tuple(dict.fromkeys(ordered_references))


def resolve_merge_base(repo_root: str) -> str | None:
    """Find the merge base between HEAD and the default upstream branch.

    Args:
        repo_root: The repository top-level directory.

    Returns:
        The merge-base commit sha, or None when no upstream base resolves —
        the caller decides how to treat base-less repositories.
    """
    for each_reference in candidate_base_references(repo_root):
        merge_base_sha = run_git(repo_root, "merge-base", "HEAD", each_reference)
        if merge_base_sha:
            return merge_base_sha
    return None


def untracked_file_paths(repo_root: str) -> list[str] | None:
    """List untracked, non-ignored files outside tooling-state directories.

    Paths under the transient tooling-state subtrees (the Claude and Cursor
    scratch subdirectories named in ``ALL_TOOLING_STATE_PREFIXES`` —
    verification verdicts, worktree copies, daemon and team session state)
    are skipped: they hold session state and stale worktree copies, never
    the branch's work, and in real checkouts they run to thousands of
    files. Production hook, agent, and skill files tracked elsewhere under
    ``.claude/`` are kept, so a new untracked one still binds to the
    verdict surface.

    Args:
        repo_root: The repository top-level directory.

    Returns:
        Sorted repo-relative paths, or None when git fails.
    """
    listing_text = run_git(
        repo_root, "-c", "core.quotePath=false", "ls-files", "--others", "--exclude-standard"
    )
    if listing_text is None:
        return None
    return sorted(
        each_line
        for each_line in listing_text.splitlines()
        if each_line and not each_line.startswith(ALL_TOOLING_STATE_PREFIXES)
    )


def branch_surface_manifest(repo_root: str, merge_base_sha: str) -> str | None:
    """Compute the canonical change-surface manifest a verdict covers.

    The surface is every path that differs from the merge base plus every
    untracked file, each bound by a digest of its current work-tree
    content. Binding paths and contents — not patch text or index state —
    makes the hash invariant under ``git add`` and commit slicing, while
    any content edit or new file after verification still changes it.

    Args:
        repo_root: The repository top-level directory.
        merge_base_sha: The merge-base commit sha the branch grew from.

    Returns:
        One ``<path> sha256=<digest>`` line per surface file (deleted
        files carry a ``deleted`` marker), or None when git or a file
        read fails.
    """
    changed_paths_text = run_git(
        repo_root, "-c", "core.quotePath=false", "diff", "--name-only", "--no-renames",
        merge_base_sha,
    )
    if changed_paths_text is None:
        return None
    untracked_paths = untracked_file_paths(repo_root)
    if untracked_paths is None:
        return None
    surface_paths = sorted(
        {each_path for each_path in changed_paths_text.splitlines() if each_path}
        | set(untracked_paths)
    )
    manifest_lines = []
    for each_path in surface_paths:
        surface_file = Path(repo_root) / each_path
        if not surface_file.is_file():
            manifest_lines.append(f"{each_path} deleted")
            continue
        try:
            content_digest = hashlib.sha256(surface_file.read_bytes()).hexdigest()
        except OSError:
            return None
        manifest_lines.append(f"{each_path} sha256={content_digest}")
    return "\n".join(manifest_lines)


def manifest_sha256(surface_manifest_text: str) -> str:
    """Hash a change-surface manifest.

    Args:
        surface_manifest_text: The manifest from ``branch_surface_manifest``.

    Returns:
        The hex sha256 digest of the encoded manifest text.
    """
    return hashlib.sha256(surface_manifest_text.encode("utf-8")).hexdigest()


def verdict_path_for_repo(repo_root: str) -> Path:
    """Derive the verdict file path for a repository work tree.

    Verdicts live outside the repository (under the user's Claude home) so
    no repo accumulates untracked files, keyed by a hash of the normalized
    work-tree path so every worktree gets its own verdict.

    Args:
        repo_root: The repository top-level directory.

    Returns:
        The verdict file path for this work tree.
    """
    normalized_root = str(Path(repo_root).resolve()).replace("\\", "/").lower()
    root_key = hashlib.sha256(normalized_root.encode("utf-8")).hexdigest()[:ROOT_KEY_HEX_LENGTH]
    return (
        Path.home() / CLAUDE_HOME_DIRECTORY_NAME / VERDICT_DIRECTORY_NAME / f"{root_key}.json"
    )


def load_valid_verdict(repo_root: str, expected_manifest_sha256: str) -> dict | None:
    """Load the verdict for a repo when it passes and covers the live surface.

    Args:
        repo_root: The repository top-level directory.
        expected_manifest_sha256: Hash of the live surface manifest the
            verdict must match exactly.

    Returns:
        The verdict mapping when it exists, parses, reports ``all_pass``
        true, and binds to the expected manifest hash; otherwise None.
    """
    verdict_file = verdict_path_for_repo(repo_root)
    try:
        verdict_record = json.loads(verdict_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(verdict_record, dict):
        return None
    if verdict_record.get(VERDICT_KEY_ALL_PASS) is not True:
        return None
    if verdict_record.get(VERDICT_KEY_MANIFEST_SHA256) != expected_manifest_sha256:
        return None
    return verdict_record


def write_verdict(
    repo_root: str,
    bound_manifest_sha256: str,
    is_all_pass: bool,
    all_findings: list,
    minted_from_agent_id: str,
) -> Path:
    """Write a verdict file binding a verification outcome to a surface hash.

    Args:
        repo_root: The repository top-level directory.
        bound_manifest_sha256: Hash of the surface manifest the verdict covers.
        is_all_pass: Whether the verifier reported a clean verdict.
        all_findings: The verifier's findings list (empty when clean).
        minted_from_agent_id: The subagent invocation id, kept for audit.

    Returns:
        The path the verdict was written to.
    """
    verdict_file = verdict_path_for_repo(repo_root)
    verdict_file.parent.mkdir(parents=True, exist_ok=True)
    verdict_record = {
        VERDICT_KEY_ALL_PASS: is_all_pass,
        VERDICT_KEY_MANIFEST_SHA256: bound_manifest_sha256,
        "repo_root": repo_root,
        "findings": all_findings,
        "minted_from_agent_id": minted_from_agent_id,
        "minted_at_epoch_seconds": int(time.time()),
    }
    verdict_file.write_text(
        json.dumps(verdict_record, indent=VERDICT_JSON_INDENT), encoding="utf-8"
    )
    return verdict_file


def stripped_ast_dump(python_source: str) -> str | None:
    """Dump a Python module's AST with every docstring removed.

    Comments never reach the AST, so two sources with equal stripped dumps
    differ only in docstrings, comments, or formatting — never in behavior.

    Args:
        python_source: The module source text.

    Returns:
        The ``ast.dump`` text of the stripped tree, or None when the source
        does not parse (callers treat unparseable sources as changed).
    """
    try:
        module_tree = ast.parse(python_source)
    except (SyntaxError, ValueError):
        return None
    for each_node in ast.walk(module_tree):
        if not isinstance(
            each_node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            continue
        node_body = each_node.body
        if (
            node_body
            and isinstance(node_body[0], ast.Expr)
            and isinstance(node_body[0].value, ast.Constant)
            and isinstance(node_body[0].value.value, str)
        ):
            each_node.body = node_body[1:] or [ast.Pass()]
    return ast.dump(module_tree)


def _is_python_change_docstring_only(
    repo_root: str, merge_base_sha: str, repo_relative_path: str
) -> bool:
    """Decide whether one Python file changed only in docstrings or comments.

    Args:
        repo_root: The repository top-level directory.
        merge_base_sha: The merge-base commit holding the old version.
        repo_relative_path: The file's path relative to the repo root.

    Returns:
        True only when both versions parse and their docstring-stripped
        ASTs match exactly.
    """
    old_source = run_git(repo_root, "show", f"{merge_base_sha}:{repo_relative_path}")
    if old_source is None:
        return False
    try:
        new_source = (Path(repo_root) / repo_relative_path).read_text(
            encoding="utf-8", errors="replace"
        )
    except OSError:
        return False
    old_dump = stripped_ast_dump(old_source)
    new_dump = stripped_ast_dump(new_source)
    return old_dump is not None and old_dump == new_dump


def _is_test_file_path(repo_relative_path: str) -> bool:
    """Decide whether a path names a pytest test file.

    Args:
        repo_relative_path: The file's path relative to the repo root.

    Returns:
        True when the file name follows a pytest collection convention
        (``test_*.py``, ``*_test.py``, or ``conftest.py``).
    """
    file_name = Path(repo_relative_path).name
    if file_name == CONFTEST_FILE_NAME:
        return True
    if not file_name.endswith(PYTHON_EXTENSION):
        return False
    return file_name.startswith(TEST_FILE_PREFIX) or file_name.endswith(TEST_FILE_SUFFIX)


def is_verification_exempt_diff(repo_root: str, merge_base_sha: str) -> bool:
    """Decide the mechanical exemption: nothing production-behavioral changed.

    A diff is exempt only when every changed file is a docs/image file (by
    extension), a pytest test file (by name convention), or a Python file
    whose docstring-stripped AST is unchanged. Untracked files count as
    changes: only docs-extension and test-named ones are exempt, since an
    untracked production Python file has no merge-base version to compare
    against. Renames are decomposed into a delete plus an add
    (``--no-renames``) so renaming code to a docs extension still gates
    the deletion. Production edits key on a fact the diff author cannot
    steer — any behavioral edit changes the AST and gets gated. Test files
    are exempt by policy: a test-only surface cannot change production
    behavior, and test quality is covered by review, not by the verifier.

    Args:
        repo_root: The repository top-level directory.
        merge_base_sha: The merge-base commit sha the branch grew from.

    Returns:
        True when every change is exempt; False otherwise, and False
        whenever git output cannot be read (fail closed).
    """
    name_status_text = run_git(
        repo_root, "-c", "core.quotePath=false", "diff", "--name-status", "--no-renames",
        merge_base_sha,
    )
    if name_status_text is None:
        return False
    untracked_paths = untracked_file_paths(repo_root)
    if untracked_paths is None:
        return False
    for each_untracked_path in untracked_paths:
        if _is_test_file_path(each_untracked_path):
            continue
        if Path(each_untracked_path).suffix.lower() not in DOCS_ONLY_EXTENSIONS:
            return False
    if not name_status_text:
        return True
    for each_status_line in name_status_text.splitlines():
        status_fields = each_status_line.split("\t")
        if len(status_fields) < MINIMUM_STATUS_FIELD_COUNT:
            return False
        change_code = status_fields[0]
        changed_path = status_fields[-1]
        if _is_test_file_path(changed_path):
            continue
        file_extension = Path(changed_path).suffix.lower()
        if file_extension in DOCS_ONLY_EXTENSIONS:
            continue
        if file_extension != PYTHON_EXTENSION:
            return False
        if not change_code.startswith("M"):
            return False
        if not _is_python_change_docstring_only(repo_root, merge_base_sha, changed_path):
            return False
    return True
