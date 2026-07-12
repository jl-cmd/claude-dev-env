#!/usr/bin/env python3
"""PreToolUse hook: block writes, durable posts, and commits that carry PII.

Surfaces guarded:

- Write / Edit / MultiEdit — new content about to land on disk
- Bash / PowerShell ``gh`` post subcommands and GitHub MCP post tools — durable
  bodies
- Bash / PowerShell ``git commit`` (including ``git.exe`` and flag forms) —
  staged file contents about to become history. Commit message bodies are out
  of scope; only staged blob text is scanned.

Payload and post-body scanning live in ``pii_payload_scan``; git-commit command
detection lives in ``pii_commit_command``; both re-export through this entry
module so the hooks.json wiring and every importer resolve unchanged.

A repository named in ``CLAUDE_PII_EXEMPT_REPOS`` or the ``pii_exempt_repositories``
list in ``~/.claude/local-identity.json`` skips the staged-commit scan; a
repository without a readable origin remote is never exempt.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

_blocking_directory = str(Path(__file__).resolve().parent)
_hooks_directory = str(Path(__file__).resolve().parent.parent)
if _blocking_directory not in sys.path:
    sys.path.insert(0, _blocking_directory)
if _hooks_directory not in sys.path:
    sys.path.insert(0, _hooks_directory)

from block_main_commit import resolve_directory  # noqa: E402
from pii_commit_command import (  # noqa: E402
    extract_git_commit_working_directory,
    is_git_commit_shell_command,
)
from pii_payload_scan import (  # noqa: E402
    build_deny_reason,
    evaluate_post_body_texts,
    evaluate_write_edit_payload,
)
from pii_scanner import is_path_exempt_from_pii_scan, scan_text_for_pii  # noqa: E402
from precommit_code_rules_gate import resolve_repository_root  # noqa: E402
from volatile_path_in_post_blocker import (  # noqa: E402
    extract_gh_post_body_texts_for_privacy_gate,
    extract_mcp_body_texts,
)

from hooks_constants.hook_block_logger import log_hook_block  # noqa: E402
from hooks_constants.local_identity import pii_exempt_repository_slugs  # noqa: E402
from hooks_constants.pii_prevention_constants import (  # noqa: E402
    ALL_GIT_ORIGIN_URL_COMMAND,
    ALL_NETWORK_GIT_URL_SCHEMES,
    ALL_SHELL_TOOL_NAMES,
    ALL_STAGED_BLOB_SHOW_COMMAND_PREFIX,
    ALL_STAGED_FILES_COMMAND,
    ALL_WRITE_EDIT_MULTI_EDIT_TOOL_NAMES,
    BODY_FILE_ENCODING,
    GIT_COMMAND_TIMEOUT_SECONDS,
    GIT_URL_SUFFIX,
    GITHUB_COM_HOST,
    HOOK_SCRIPT_BASENAME,
    MAXIMUM_STAGED_FILE_BYTES,
    MCP_GITHUB_TOOL_PREFIX,
    MINIMUM_OWNER_REPO_SEGMENT_COUNT,
    NULL_BYTE_MARKER,
    POSIX_PATH_SEPARATOR,
    REPOSITORY_ROOT_UNRESOLVED_REASON,
    SCP_STYLE_PATH_SEPARATOR,
    STAGED_BLOB_PREFIX,
    STAGED_BLOB_REASON_DECODE_FAILED,
    STAGED_BLOB_REASON_GIT_SHOW_FAILED,
    STAGED_BLOB_REASON_NULL_BYTES,
    STAGED_BLOB_REASON_OVERSIZED,
    STAGED_BLOB_UNSCANNABLE_REASON_TEMPLATE,
    STAGED_LIST_FAILURE_REASON,
    URL_SCHEME_SEPARATOR,
    USERINFO_HOST_SEPARATOR,
    WINDOWS_PATH_SEPARATOR,
)
from hooks_constants.pre_tool_use_stdin import (  # noqa: E402
    read_hook_input_dictionary_from_stdin,
)


def list_staged_file_paths(
    repository_root: Path,
) -> tuple[list[str] | None, str | None]:
    """List staged non-deleted paths, or report a list failure.

    Args:
        repository_root: Repository root used as the git working directory.

    Returns:
        ``(paths, None)`` on success, or ``(None, deny_reason)`` when the
        staged list cannot be read (fail-closed for commit gating).
    """
    try:
        completed_process = subprocess.run(
            list(ALL_STAGED_FILES_COMMAND),
            capture_output=True,
            text=True,
            timeout=GIT_COMMAND_TIMEOUT_SECONDS,
            cwd=str(repository_root),
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None, STAGED_LIST_FAILURE_REASON
    if completed_process.returncode != 0:
        return None, STAGED_LIST_FAILURE_REASON
    all_paths = [
        each_line.strip()
        for each_line in completed_process.stdout.splitlines()
        if each_line.strip()
    ]
    return all_paths, None


def read_staged_file_text(
    repository_root: Path, relative_path: str
) -> tuple[str | None, str | None]:
    """Return staged blob text, or report why the blob is unscannable.

    Args:
        repository_root: Repository root for the git show working directory.
        relative_path: Repository-relative path of the staged file.

    Returns:
        ``(text, None)`` when the blob is scannable UTF-8 text, or
        ``(None, deny_reason)`` when the blob cannot be scanned (fail-closed).
    """
    staged_blob_reference = STAGED_BLOB_PREFIX + relative_path
    try:
        completed_process = subprocess.run(
            list(ALL_STAGED_BLOB_SHOW_COMMAND_PREFIX) + [staged_blob_reference],
            capture_output=True,
            timeout=GIT_COMMAND_TIMEOUT_SECONDS,
            cwd=str(repository_root),
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None, STAGED_BLOB_UNSCANNABLE_REASON_TEMPLATE.format(
            relative_path=relative_path,
            reason=STAGED_BLOB_REASON_GIT_SHOW_FAILED,
        )
    if completed_process.returncode != 0:
        return None, STAGED_BLOB_UNSCANNABLE_REASON_TEMPLATE.format(
            relative_path=relative_path,
            reason=STAGED_BLOB_REASON_GIT_SHOW_FAILED,
        )
    raw_bytes = completed_process.stdout
    if len(raw_bytes) > MAXIMUM_STAGED_FILE_BYTES:
        return None, STAGED_BLOB_UNSCANNABLE_REASON_TEMPLATE.format(
            relative_path=relative_path,
            reason=STAGED_BLOB_REASON_OVERSIZED,
        )
    if NULL_BYTE_MARKER in raw_bytes:
        return None, STAGED_BLOB_UNSCANNABLE_REASON_TEMPLATE.format(
            relative_path=relative_path,
            reason=STAGED_BLOB_REASON_NULL_BYTES,
        )
    try:
        return raw_bytes.decode(BODY_FILE_ENCODING), None
    except UnicodeDecodeError:
        return None, STAGED_BLOB_UNSCANNABLE_REASON_TEMPLATE.format(
            relative_path=relative_path,
            reason=STAGED_BLOB_REASON_DECODE_FAILED,
        )


def evaluate_staged_commit(
    repository_root: Path,
) -> str | None:
    """Return a deny reason when staged content carries PII or is unscannable.

    Fail-closed: git list/show failures and unscannable blobs deny the commit
    rather than treating unread content as clean.

    Args:
        repository_root: Repository whose index is about to be committed.

    Returns:
        Deny reason text, or None when every scannable staged path is clean.
    """
    all_relative_paths, list_failure_reason = list_staged_file_paths(repository_root)
    if list_failure_reason is not None or all_relative_paths is None:
        return list_failure_reason or STAGED_LIST_FAILURE_REASON
    for each_relative_path in all_relative_paths:
        if is_path_exempt_from_pii_scan(each_relative_path):
            continue
        staged_text, unscannable_reason = read_staged_file_text(
            repository_root, each_relative_path
        )
        if unscannable_reason is not None:
            return unscannable_reason
        if staged_text is None:
            return STAGED_BLOB_UNSCANNABLE_REASON_TEMPLATE.format(
                relative_path=each_relative_path,
                reason=STAGED_BLOB_REASON_GIT_SHOW_FAILED,
            )
        all_findings = scan_text_for_pii(staged_text)
        if all_findings:
            gate_surface = f"staged commit ({each_relative_path})"
            return build_deny_reason(all_findings, gate_surface)
    return None


def _strip_trailing_path_separators(origin_url: str) -> str:
    stripped_url = origin_url
    while stripped_url and stripped_url[-1] in (
        POSIX_PATH_SEPARATOR,
        WINDOWS_PATH_SEPARATOR,
    ):
        stripped_url = stripped_url[:-1]
    return stripped_url


def _strip_trailing_git_suffix(origin_url: str) -> str:
    if origin_url.lower().endswith(GIT_URL_SUFFIX):
        return origin_url[: -len(GIT_URL_SUFFIX)]
    return origin_url


def _normalized_origin_url(origin_url: str) -> str:
    return _strip_trailing_git_suffix(_strip_trailing_path_separators(origin_url))


def _host_and_path_from_scheme_url(origin_url: str) -> tuple[str, str] | None:
    parsed_url = urlparse(origin_url)
    if parsed_url.scheme not in ALL_NETWORK_GIT_URL_SCHEMES:
        return None
    maybe_host = parsed_url.hostname
    if maybe_host is None:
        return None
    try:
        parsed_url.port
    except ValueError:
        return None
    repository_path = parsed_url.path.replace(
        WINDOWS_PATH_SEPARATOR, POSIX_PATH_SEPARATOR
    ).lstrip(POSIX_PATH_SEPARATOR)
    return maybe_host.lower(), repository_path


def _host_and_path_from_scp_url(origin_url: str) -> tuple[str, str] | None:
    if USERINFO_HOST_SEPARATOR not in origin_url:
        return None
    userinfo_and_host, separator, repository_path = origin_url.partition(
        SCP_STYLE_PATH_SEPARATOR
    )
    if not separator or USERINFO_HOST_SEPARATOR not in userinfo_and_host:
        return None
    if not repository_path:
        return None
    host = userinfo_and_host.rsplit(USERINFO_HOST_SEPARATOR, maxsplit=1)[-1]
    if not host:
        return None
    normalized_path = repository_path.replace(
        WINDOWS_PATH_SEPARATOR, POSIX_PATH_SEPARATOR
    )
    return host.lower(), normalized_path


def _host_and_repository_path_from_origin_url(
    origin_url: str,
) -> tuple[str, str] | None:
    normalized_url = _normalized_origin_url(origin_url)
    if URL_SCHEME_SEPARATOR in normalized_url:
        return _host_and_path_from_scheme_url(normalized_url)
    return _host_and_path_from_scp_url(normalized_url)


def _owner_repo_slug_from_path(repository_path: str) -> str | None:
    all_segments = [
        each_segment
        for each_segment in repository_path.split(POSIX_PATH_SEPARATOR)
        if each_segment
    ]
    if len(all_segments) < MINIMUM_OWNER_REPO_SEGMENT_COUNT:
        return None
    owner_name = all_segments[0]
    repository_name = all_segments[1]
    return POSIX_PATH_SEPARATOR.join((owner_name, repository_name)).lower()


def _owner_repo_slug_from_origin_url(origin_url: str) -> str | None:
    """Return the lowercased owner/repo slug from a github.com origin URL.

    ::

        https://github.com/Owner/Repo.git                 ->  owner/repo
        https://github.com/Owner/Repo                     ->  owner/repo
        https://github.com:443/Owner/Repo.git             ->  owner/repo
        ssh://git@github.com:22/Owner/Repo.git            ->  owner/repo
        git@github.com:Owner/Repo.git                     ->  owner/repo
        ssh://git@github.com/Owner/Repo.git               ->  owner/repo
        https://github.com/Owner/Repo.git/                ->  owner/repo
        https://evil.test/Owner/Repo.git                  ->  None
        https://github.com:443.evil.test/Owner/Repo.git   ->  None
        ssh://git@github.com:22.evil.test/Owner/Repo.git  ->  None
        C:/repos/Owner/Repo                               ->  None

    Accepts only the exact host ``github.com`` (case-insensitive). Spoof hosts,
    unparseable port authorities, and path-shaped origins return None so the
    repository is never exempt.

    Args:
        origin_url: The ``remote.origin.url`` value, https or ssh form.

    Returns:
        The ``owner/repo`` slug in lowercase, or None when the host is not
        exactly ``github.com``, the port authority is unparseable, or the URL
        carries no owner/repo tail.
    """
    maybe_host_and_path = _host_and_repository_path_from_origin_url(origin_url)
    if maybe_host_and_path is None:
        return None
    host, repository_path = maybe_host_and_path
    if host != GITHUB_COM_HOST:
        return None
    return _owner_repo_slug_from_path(repository_path)


def _repository_origin_slug(repository_root: Path) -> str | None:
    """Return the lowercased owner/repo slug of the origin remote, or None.

    Args:
        repository_root: Repository whose origin remote identifies it.

    Returns:
        The ``owner/repo`` slug in lowercase, or None when the repository has no
        readable origin remote or the URL carries no owner/repo tail.
    """
    try:
        completed_process = subprocess.run(
            list(ALL_GIT_ORIGIN_URL_COMMAND),
            capture_output=True,
            text=True,
            timeout=GIT_COMMAND_TIMEOUT_SECONDS,
            cwd=str(repository_root),
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None
    if completed_process.returncode != 0:
        return None
    return _owner_repo_slug_from_origin_url(completed_process.stdout.strip())


def _is_repository_exempt_from_pii_scan(repository_root: Path) -> bool:
    """Report whether commits in *repository_root* skip the staged PII scan.

    Exempt repositories are named by owner/repo slug through
    ``CLAUDE_PII_EXEMPT_REPOS`` or the ``pii_exempt_repositories`` list in the
    git-ignored ``~/.claude/local-identity.json``. A repository without a readable
    origin remote is never exempt (fail-closed to scanning).

    Args:
        repository_root: Repository whose index is about to be committed.

    Returns:
        True when the repository's origin slug is in the exempt set.
    """
    origin_slug = _repository_origin_slug(repository_root)
    if origin_slug is None:
        return False
    return origin_slug in pii_exempt_repository_slugs()


def evaluate_bash_command(
    bash_command: str, working_directory: str | None
) -> str | None:
    """Return a deny reason for a shell gh post or git commit with PII.

    Args:
        bash_command: The Bash or PowerShell tool command string.
        working_directory: Directory git should run in, or None for process CWD.

    Returns:
        Deny reason text, or None when the command is clean or out of scope.
    """
    all_post_bodies, body_file_failure_reason = (
        extract_gh_post_body_texts_for_privacy_gate(
            bash_command, working_directory=working_directory
        )
    )
    if body_file_failure_reason is not None:
        return body_file_failure_reason
    post_deny_reason = evaluate_post_body_texts(all_post_bodies)
    if post_deny_reason is not None:
        return post_deny_reason
    if not is_git_commit_shell_command(bash_command):
        return None
    command_directory = extract_git_commit_working_directory(bash_command)
    resolved_directory = resolve_directory(command_directory) or working_directory
    repository_root = resolve_repository_root(resolved_directory)
    if repository_root is None:
        return REPOSITORY_ROOT_UNRESOLVED_REASON
    if _is_repository_exempt_from_pii_scan(repository_root):
        return None
    return evaluate_staged_commit(repository_root)


def evaluate(payload_by_key: dict[str, object]) -> str | None:
    """Decide whether a PreToolUse payload carries high-confidence PII.

    Args:
        payload_by_key: The PreToolUse payload with tool_name and tool_input.

    Returns:
        Deny-reason text when blocked, or None when allowed.
    """
    raw_tool_name = payload_by_key.get("tool_name", "")
    tool_name = raw_tool_name if isinstance(raw_tool_name, str) else ""
    raw_tool_input = payload_by_key.get("tool_input", {})
    all_tool_input = raw_tool_input if isinstance(raw_tool_input, dict) else {}

    if tool_name in ALL_WRITE_EDIT_MULTI_EDIT_TOOL_NAMES:
        return evaluate_write_edit_payload(tool_name, all_tool_input)

    if tool_name in ALL_SHELL_TOOL_NAMES:
        command_value = all_tool_input.get("command", "")
        if not isinstance(command_value, str) or not command_value:
            return None
        working_directory_value = all_tool_input.get("working_directory")
        working_directory = (
            working_directory_value
            if isinstance(working_directory_value, str)
            else None
        )
        if working_directory is None:
            cwd_value = payload_by_key.get("cwd")
            working_directory = cwd_value if isinstance(cwd_value, str) else None
        return evaluate_bash_command(
            command_value, working_directory=working_directory
        )

    if tool_name.startswith(MCP_GITHUB_TOOL_PREFIX):
        return evaluate_post_body_texts(extract_mcp_body_texts(all_tool_input))

    return None


def build_deny_payload(deny_reason: str) -> dict[str, object]:
    """Build the PreToolUse deny payload for *deny_reason*.

    Args:
        deny_reason: The permissionDecisionReason text.

    Returns:
        Deny payload dictionary serialized to stdout by the hook.
    """
    log_hook_block(
        calling_hook_name=HOOK_SCRIPT_BASENAME,
        hook_event="PreToolUse",
        block_reason=deny_reason,
    )
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": deny_reason,
        }
    }


def main() -> None:
    """Read PreToolUse stdin and deny when high-confidence PII is present."""
    payload_dictionary = read_hook_input_dictionary_from_stdin()
    if payload_dictionary is None:
        sys.exit(0)
    deny_reason = evaluate(payload_dictionary)
    if deny_reason is None:
        sys.exit(0)
    print(json.dumps(build_deny_payload(deny_reason)))
    sys.stdout.flush()
    sys.exit(0)


if __name__ == "__main__":
    main()
