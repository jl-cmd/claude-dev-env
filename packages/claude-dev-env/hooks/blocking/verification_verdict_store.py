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
import re
import subprocess
import sys
import time
from pathlib import Path

blocking_directory = str(Path(__file__).resolve().parent)
if blocking_directory not in sys.path:
    sys.path.insert(0, blocking_directory)

from config.verified_commit_constants import (
    AGENT_META_SIDECAR_SUFFIX,
    AGENT_META_TYPE_KEY,
    AGENT_TRANSCRIPT_GLOB,
    BRANCH_REFERENCE_PREFIX,
    BRANCH_WORKTREE_ABSENT_MESSAGE,
    CLAUDE_HOME_DIRECTORY_NAME,
    CONFTEST_FILE_NAME,
    DOCS_ONLY_EXTENSIONS,
    ALL_FALLBACK_BASE_REFERENCES,
    EMPTY_SURFACE_GUARD_MESSAGE,
    GIT_TIMEOUT_SECONDS,
    MANIFEST_HASH_CLI_FLAG,
    MANIFEST_HASH_FOR_BRANCH_CLI_FLAG,
    MINIMUM_STATUS_FIELD_COUNT,
    MINTING_AGENT_TYPE,
    PYTHON_EXTENSION,
    ROOT_KEY_HEX_LENGTH,
    SUBAGENTS_DIRECTORY_NAME,
    TEST_FILE_PREFIX,
    TEST_FILE_SUFFIX,
    ALL_TOOLING_STATE_PREFIXES,
    TRANSCRIPT_ASSISTANT_ENTRY_TYPE,
    TRANSCRIPT_CONTENT_KEY,
    TRANSCRIPT_CONTENT_TYPE_KEY,
    TRANSCRIPT_ENTRY_TYPE_KEY,
    TRANSCRIPT_MESSAGE_KEY,
    TRANSCRIPT_TEXT_CONTENT_TYPE,
    TRANSCRIPT_TEXT_KEY,
    VERDICT_DIRECTORY_NAME,
    VERDICT_FENCE_PATTERN,
    VERDICT_FILE_GLOB,
    VERDICT_JSON_INDENT,
    VERDICT_KEY_ALL_PASS,
    VERDICT_KEY_FINDINGS,
    VERDICT_KEY_MANIFEST_SHA256,
    WORKTREE_LIST_BRANCH_PREFIX,
    WORKTREE_LIST_PATH_PREFIX,
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


def empty_surface_hash() -> str:
    """Return the manifest hash that represents an empty change surface.

    A work tree whose HEAD equals the merge base has no changed or untracked
    files, so ``branch_surface_manifest`` returns ``""`` and this hash is what
    the minter or store CLI would produce for it. Comparing an attested hash
    against this value lets the minter refuse to mint for a verifier that ran
    in the wrong work tree.

    Returns:
        The hex sha256 digest of the empty surface manifest (the empty string).
    """
    return manifest_sha256("")


def worktree_path_for_branch(repo_directory: str, branch_name: str) -> str | None:
    """Find the work-tree directory that has a given branch checked out.

    Parses the porcelain output of ``git worktree list --porcelain`` and
    returns the ``worktree <path>`` line whose block carries a
    ``branch refs/heads/<branch_name>`` line. Returns None when git fails
    or no work tree holds the branch.

    Args:
        repo_directory: Any directory inside the repository.
        branch_name: The short branch name to locate (without ``refs/heads/``).

    Returns:
        The absolute path of the work tree that has the branch checked out,
        or None when no work tree holds the branch or git fails.
    """
    porcelain_output = run_git(repo_directory, "worktree", "list", "--porcelain")
    if porcelain_output is None:
        return None
    target_branch_reference = f"{BRANCH_REFERENCE_PREFIX}{branch_name}"
    current_worktree_path: str | None = None
    for each_line in porcelain_output.splitlines():
        if each_line.startswith(WORKTREE_LIST_PATH_PREFIX):
            current_worktree_path = each_line[len(WORKTREE_LIST_PATH_PREFIX):]
        elif each_line.startswith(WORKTREE_LIST_BRANCH_PREFIX):
            branch_reference = each_line[len(WORKTREE_LIST_BRANCH_PREFIX):]
            if branch_reference == target_branch_reference and current_worktree_path:
                return current_worktree_path
    return None


def verdict_directory() -> Path:
    """Return the shared directory holding every work tree's verdict file.

    Verdicts live outside any repository (under the user's Claude home) so no
    repo accumulates untracked verdict files; every work tree's verdict shares
    this one directory, distinguished by file name.

    Returns:
        The verdict directory under the user's Claude home.
    """
    return Path.home() / CLAUDE_HOME_DIRECTORY_NAME / VERDICT_DIRECTORY_NAME


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
    return verdict_directory() / f"{root_key}.json"


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


def minted_verdict_covers_surface(expected_manifest_sha256: str) -> bool:
    """Decide whether any minted verdict covers the live surface, keyed by hash.

    A verdict's bound ``manifest_sha256`` commits to the exact set of surface
    file paths and their byte contents; the work tree's location never enters
    the hash. A clean verdict minted while verifying one work tree therefore
    proves the same change surface in a sibling work tree of the same branch,
    even though each work tree files its verdict under its own path-keyed name.
    Scanning every verdict file by bound hash lets that verdict clear the
    sibling's commit, while a verdict bound to a different hash — different
    code — never matches. The path-keyed ``load_valid_verdict`` stays the fast
    same-work-tree lookup; this is the cross-work-tree fallback.

    Args:
        expected_manifest_sha256: Hash of the live surface manifest the verdict
            must match exactly.

    Returns:
        True as soon as one verdict file reports ``all_pass`` true and binds to
        the expected hash; False when none match or the directory is absent.
    """
    verdict_dir = verdict_directory()
    if not verdict_dir.is_dir():
        return False
    for each_verdict_file in sorted(verdict_dir.glob(VERDICT_FILE_GLOB)):
        try:
            verdict_record = json.loads(each_verdict_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(verdict_record, dict):
            continue
        if verdict_record.get(VERDICT_KEY_ALL_PASS) is not True:
            continue
        if verdict_record.get(VERDICT_KEY_MANIFEST_SHA256) == expected_manifest_sha256:
            return True
    return False


def _subagents_directory_for_transcript(transcript_path: str) -> Path | None:
    """Locate the live session's subagents directory from a transcript path.

    Handles both transcript shapes the runtime produces: a transcript already
    inside a ``.../subagents/...`` tree resolves to its nearest ancestor named
    ``subagents``; a session transcript ``<dir>/<session-id>.jsonl`` resolves
    to ``<dir>/<session-id>/subagents``.

    Args:
        transcript_path: The live session's transcript path from the payload.

    Returns:
        The existing subagents directory, or None when neither shape yields
        an existing directory.
    """
    if not transcript_path:
        return None
    transcript_file = Path(transcript_path)
    for each_ancestor in transcript_file.parents:
        if each_ancestor.name == SUBAGENTS_DIRECTORY_NAME and each_ancestor.is_dir():
            return each_ancestor
    session_subagents_directory = (
        transcript_file.with_suffix("") / SUBAGENTS_DIRECTORY_NAME
    )
    if session_subagents_directory.is_dir():
        return session_subagents_directory
    return None


def _agent_type_for_transcript(transcript_file: Path) -> str | None:
    """Read an agent transcript's sidecar to learn the agent type it ran as.

    Args:
        transcript_file: An ``agent-*.jsonl`` transcript path.

    Returns:
        The ``agentType`` recorded in the ``<stem>.meta.json`` sidecar, or
        None when the sidecar is missing, unreadable, or carries no type.
    """
    sidecar_file = transcript_file.with_suffix(AGENT_META_SIDECAR_SUFFIX)
    try:
        sidecar_record = json.loads(sidecar_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(sidecar_record, dict):
        return None
    recorded_agent_type = sidecar_record.get(AGENT_META_TYPE_KEY)
    return recorded_agent_type if isinstance(recorded_agent_type, str) else None


def _assistant_text_blocks(transcript_file: Path) -> list[str]:
    """Collect every assistant text block from an agent transcript.

    Args:
        transcript_file: An ``agent-*.jsonl`` transcript path.

    Returns:
        The text of each assistant message content block, in order; empty
        when the file is missing, unreadable, or holds no assistant text.
    """
    try:
        transcript_lines = transcript_file.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    all_text_blocks: list[str] = []
    for each_line in transcript_lines:
        if not each_line.strip():
            continue
        try:
            transcript_entry = json.loads(each_line)
        except json.JSONDecodeError:
            continue
        all_text_blocks.extend(_entry_text_blocks(transcript_entry))
    return all_text_blocks


def _entry_text_blocks(transcript_entry: object) -> list[str]:
    """Extract assistant text from one parsed transcript entry.

    Args:
        transcript_entry: One parsed JSONL transcript entry.

    Returns:
        The text of each text content block on an assistant entry, in order;
        empty for any other entry shape.
    """
    if not isinstance(transcript_entry, dict):
        return []
    if transcript_entry.get(TRANSCRIPT_ENTRY_TYPE_KEY) != TRANSCRIPT_ASSISTANT_ENTRY_TYPE:
        return []
    message_record = transcript_entry.get(TRANSCRIPT_MESSAGE_KEY)
    if not isinstance(message_record, dict):
        return []
    content_blocks = message_record.get(TRANSCRIPT_CONTENT_KEY)
    if not isinstance(content_blocks, list):
        return []
    all_text_blocks: list[str] = []
    for each_block in content_blocks:
        if not isinstance(each_block, dict):
            continue
        if each_block.get(TRANSCRIPT_CONTENT_TYPE_KEY) != TRANSCRIPT_TEXT_CONTENT_TYPE:
            continue
        block_text = each_block.get(TRANSCRIPT_TEXT_KEY)
        if isinstance(block_text, str):
            all_text_blocks.append(block_text)
    return all_text_blocks


def _last_verdict_record(all_text_blocks: list[str]) -> dict | None:
    """Parse the last verdict fence across an agent's assistant text blocks.

    Args:
        all_text_blocks: The assistant text blocks from one transcript.

    Returns:
        The parsed verdict mapping when the last verdict fence carries a bool
        ``all_pass``, a list ``findings``, and a string ``manifest_sha256``;
        otherwise None.
    """
    verdict_fence_pattern = re.compile(VERDICT_FENCE_PATTERN, re.DOTALL)
    all_fence_bodies = [
        each_match.group(1)
        for each_block in all_text_blocks
        for each_match in verdict_fence_pattern.finditer(each_block)
    ]
    if not all_fence_bodies:
        return None
    try:
        verdict_record = json.loads(all_fence_bodies[-1])
    except json.JSONDecodeError:
        return None
    if not isinstance(verdict_record, dict):
        return None
    if not isinstance(verdict_record.get(VERDICT_KEY_ALL_PASS), bool):
        return None
    if not isinstance(verdict_record.get(VERDICT_KEY_FINDINGS), list):
        return None
    if not isinstance(verdict_record.get(VERDICT_KEY_MANIFEST_SHA256), str):
        return None
    return verdict_record


def workflow_verdict_covers_surface(
    transcript_path: str, expected_manifest_sha256: str
) -> bool:
    """Decide whether a workflow code-verifier verdict covers the live surface.

    A workflow-spawned ``code-verifier`` emits its verdict as assistant text in
    its own transcript rather than through the SubagentStop minter, so this
    walks the live session's subagent transcripts for a ``code-verifier`` whose
    final verdict reports ``all_pass`` true and binds to the expected manifest
    hash.

    Args:
        transcript_path: The live session's transcript path from the payload.
        expected_manifest_sha256: Hash of the live surface manifest the verdict
            must match exactly.

    Returns:
        True as soon as one ``code-verifier`` transcript carries a passing
        verdict bound to the expected hash; False when none match or the
        subagents directory cannot be located.
    """
    subagents_directory = _subagents_directory_for_transcript(transcript_path)
    if subagents_directory is None:
        return False
    for each_transcript_file in subagents_directory.rglob(AGENT_TRANSCRIPT_GLOB):
        if _agent_type_for_transcript(each_transcript_file) != MINTING_AGENT_TYPE:
            continue
        verdict_record = _last_verdict_record(
            _assistant_text_blocks(each_transcript_file)
        )
        if verdict_record is None:
            continue
        if verdict_record[VERDICT_KEY_ALL_PASS] is not True:
            continue
        if verdict_record[VERDICT_KEY_MANIFEST_SHA256] == expected_manifest_sha256:
            return True
    return False


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


def _print_live_manifest_hash(repo_directory: str) -> int:
    """Print the live surface manifest hash for a repo, for a workflow verifier.

    A workflow code-verifier runs this to learn the exact hash to bind its
    verdict to, so stdout carries only the hash and nothing else. When the
    work tree has no changed or untracked files (empty change surface), this
    prints the empty-surface guard message to stderr and returns nonzero —
    an empty surface means the verifier is pointed at the wrong work tree.

    Args:
        repo_directory: A directory inside the work tree to bind the verdict to.

    Returns:
        0 after printing the hash; nonzero with no stdout when the repo root,
        merge base, or manifest cannot be resolved, or when the change surface
        is empty (wrong work tree).
    """
    repo_root = resolve_repo_root(repo_directory)
    if repo_root is None:
        return 1
    merge_base_sha = resolve_merge_base(repo_root)
    if merge_base_sha is None:
        return 1
    surface_manifest_text = branch_surface_manifest(repo_root, merge_base_sha)
    if surface_manifest_text is None:
        return 1
    if surface_manifest_text == "":
        print(EMPTY_SURFACE_GUARD_MESSAGE.format(repo_root=repo_root), file=sys.stderr)
        return 1
    print(manifest_sha256(surface_manifest_text))
    return 0


def _print_branch_manifest_hash(branch_name: str) -> int:
    """Print the manifest hash for the work tree that holds a given branch.

    Resolves the repository root from the current working directory, then
    finds the work tree that has ``branch_name`` checked out, and delegates
    to ``_print_live_manifest_hash`` for that work tree. This mode is immune
    to the verifier's own cwd: it always hashes the work tree that holds the
    branch under review, regardless of where the verifier itself is running.

    Args:
        branch_name: The short branch name to locate (without ``refs/heads/``).

    Returns:
        0 after printing the hash; nonzero with a stderr message when the
        repo root cannot be resolved, no work tree holds the branch, or the
        located work tree has an empty change surface.
    """
    repo_root = resolve_repo_root(str(Path.cwd()))
    if repo_root is None:
        print("ERROR: Current directory is not inside a git repository.", file=sys.stderr)
        return 1
    branch_worktree_path = worktree_path_for_branch(repo_root, branch_name)
    if branch_worktree_path is None:
        print(
            BRANCH_WORKTREE_ABSENT_MESSAGE.format(branch=branch_name),
            file=sys.stderr,
        )
        return 1
    return _print_live_manifest_hash(branch_worktree_path)


def main() -> None:
    """Run the verdict-store CLI: compute the live surface-manifest hash.

    Two modes:

    ``--manifest-hash <work-tree-dir>``
        Print the live ``manifest_sha256`` for the given work tree directory
        so a workflow code-verifier can bind its verdict to the exact surface
        the gate checks. Fails with a stderr message when the change surface
        is empty (wrong work tree).

    ``--manifest-hash-for-branch <branch>``
        Resolve the work tree that has ``<branch>`` checked out (via
        ``git worktree list --porcelain``) and print its manifest hash.
        Immune to the verifier's own cwd — always targets the branch's own
        work tree. Fails when no work tree holds the branch or the surface
        is empty.

    Exits nonzero with no stdout on any other argument shape or when the
    surface cannot be resolved.
    """
    if len(sys.argv) == 3 and sys.argv[1] == MANIFEST_HASH_CLI_FLAG:
        sys.exit(_print_live_manifest_hash(sys.argv[2]))
    if len(sys.argv) == 3 and sys.argv[1] == MANIFEST_HASH_FOR_BRANCH_CLI_FLAG:
        sys.exit(_print_branch_manifest_hash(sys.argv[2]))
    sys.exit(1)


if __name__ == "__main__":
    main()
