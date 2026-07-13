"""Per-repository PII-scan exemption keyed on the origin remote's owner/repo slug.

A commit's repository is exempt from the staged PII scan when its
``remote.origin.url`` resolves to an ``owner/repo`` slug named in
``CLAUDE_PII_EXEMPT_REPOS`` or the ``pii_exempt_repositories`` list in
``~/.claude/local-identity.json``. A repository without a readable origin remote
is never exempt (fail-closed to scanning).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

try:
    _blocking_directory = str(Path(__file__).resolve().parent.parent)
    _hooks_directory = str(Path(__file__).resolve().parent.parent.parent)
    for each_bootstrap_directory in (_blocking_directory, _hooks_directory):
        if each_bootstrap_directory not in sys.path:
            sys.path.insert(0, each_bootstrap_directory)
    from hooks_constants.local_identity import (
        pii_allowlisted_values_by_repository,
        pii_exempt_repository_slugs,
    )
    from hooks_constants.pii_prevention_constants import (
        ALL_GIT_ORIGIN_URL_COMMAND,
        ALL_NETWORK_GIT_URL_SCHEMES,
        GIT_COMMAND_TIMEOUT_SECONDS,
        GIT_URL_SUFFIX,
        GITHUB_COM_HOST,
        MINIMUM_OWNER_REPO_SEGMENT_COUNT,
        POSIX_PATH_SEPARATOR,
        SCP_STYLE_PATH_SEPARATOR,
        URL_SCHEME_SEPARATOR,
        USERINFO_HOST_SEPARATOR,
        WINDOWS_PATH_SEPARATOR,
    )
except ImportError as import_error:
    raise ImportError(
        "repository_exemption: cannot import its sibling constants; "
        "ensure the blocking and hooks directories are importable."
    ) from import_error


def repository_allowlisted_values(repository_root: Path) -> frozenset[str]:
    """Return the exact values the repository at *repository_root* may carry.

    ::

        origin slug in the allowlist mapping  ->  that repo's frozenset of values
        no origin remote, or slug not mapped  ->  frozenset()

    Args:
        repository_root: Repository whose origin owner/repo slug keys the
            per-repository PII allowlist.

    Returns:
        The exact literal values the repository's commits and writes may carry
        past the PII scan, or an empty set when the repository has none.
    """
    origin_slug = _repository_origin_slug(repository_root)
    if origin_slug is None:
        return frozenset()
    return pii_allowlisted_values_by_repository().get(origin_slug, frozenset())


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
        _ = parsed_url.port
    except ValueError:
        return None
    repository_path = parsed_url.path.replace(WINDOWS_PATH_SEPARATOR, POSIX_PATH_SEPARATOR).lstrip(
        POSIX_PATH_SEPARATOR
    )
    return maybe_host.lower(), repository_path


def _host_and_path_from_scp_url(origin_url: str) -> tuple[str, str] | None:
    if USERINFO_HOST_SEPARATOR not in origin_url:
        return None
    userinfo_and_host, separator, repository_path = origin_url.partition(SCP_STYLE_PATH_SEPARATOR)
    if not separator or USERINFO_HOST_SEPARATOR not in userinfo_and_host:
        return None
    if not repository_path:
        return None
    host = userinfo_and_host.rsplit(USERINFO_HOST_SEPARATOR, maxsplit=1)[-1]
    if not host:
        return None
    normalized_path = repository_path.replace(WINDOWS_PATH_SEPARATOR, POSIX_PATH_SEPARATOR)
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
        each_segment for each_segment in repository_path.split(POSIX_PATH_SEPARATOR) if each_segment
    ]
    if len(all_segments) < MINIMUM_OWNER_REPO_SEGMENT_COUNT:
        return None
    owner_name = all_segments[0]
    repository_name = all_segments[1]
    return POSIX_PATH_SEPARATOR.join((owner_name, repository_name)).lower()


def _owner_repo_slug_from_origin_url(origin_url: str) -> str | None:
    """Return the lowercased owner/repo slug from a github.com origin URL.

    ::

        https://github.com/Owner/Repo.git    ->  owner/repo
        https://github.com/Owner/Repo         ->  owner/repo
        https://evil.test/Owner/Repo.git      ->  None

    Accepts only the exact host ``github.com`` (case-insensitive), in https or
    ssh form. Spoof hosts, unparseable port authorities, and path-shaped origins
    return None so the repository is never exempt.

    Args:
        origin_url: The ``remote.origin.url`` value, https or ssh form.

    Returns:
        The ``owner/repo`` slug in lowercase, or None when the host is not
        exactly ``github.com`` or the URL carries no owner/repo tail.
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
            check=False, capture_output=True,
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
