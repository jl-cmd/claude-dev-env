"""Pure text scanners for high-confidence PII and secret material.

Returns structured findings only. Callers decide whether to deny a Write,
a durable GitHub post, or a git commit that carries the match.
"""

from __future__ import annotations

import ipaddress
import os
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

_hooks_directory = str(Path(__file__).resolve().parent.parent)
if _hooks_directory not in sys.path:
    sys.path.insert(0, _hooks_directory)

from hooks_constants.local_identity import nas_host  # noqa: E402
from hooks_constants.pii_prevention_constants import (  # noqa: E402
    ALL_ALLOWLISTED_PRIVATE_IP_ADDRESSES,
    ALL_EXACT_LEGAL_NOTICE_BASENAMES,
    ALL_HOME_DIRECTORY_PATH_MARKERS,
    ALL_PLACEHOLDER_HOME_USERNAMES,
    ALL_REDACTED_PREVIEW_CATEGORIES,
    ALL_RFC1918_NETWORK_CIDRS,
    ALL_SAFE_EMAIL_DOMAINS,
    ALL_SECRET_PATTERNS,
    ALL_SELF_MODULE_PATH_SUFFIXES,
    ALL_SOURCE_TEST_FILE_SUFFIXES,
    ANGLE_BRACKET_PLACEHOLDER_PATTERN,
    CATEGORY_EMAIL,
    CATEGORY_HOME_PATH,
    CATEGORY_PRIVATE_IP,
    CATEGORY_SECRET,
    CONFTEST_BASENAME,
    EMAIL_PATTERN,
    HOME_PATH_PATTERN,
    IPV4_PATTERN,
    IPV4_VERSION_NUMBER,
    MAXIMUM_FINDINGS_PER_SCAN,
    MAXIMUM_OFFENDING_PREVIEW_LENGTH,
    MINIMUM_ENV_STYLE_USERNAME_LENGTH,
    MINIMUM_LENGTH_FOR_PARTIAL_REDACTION,
    PYTHON_SOURCE_FILE_SUFFIX,
    REDACTED_PREVIEW_ELLIPSIS,
    REDACTED_PREVIEW_PREFIX_LENGTH,
    REDACTED_PREVIEW_SUFFIX_LENGTH,
    REDACTED_SHORT_PREVIEW,
    SPEC_BASENAME_MARKER,
    TEST_BASENAME_MARKER,
    TEST_MODULE_BASENAME_PREFIX,
    TEST_MODULE_BASENAME_SUFFIX,
    TESTS_PATH_PREFIX,
    TESTS_PATH_SEGMENT,
)


@dataclass(frozen=True)
class PiiFinding:
    """One high-confidence PII or secret match inside scanned text.

    Attributes:
        category: Stable category label (email, home-path, private-ip, secret).
        matched_text: The exact substring that matched.
        preview: Short, display-safe form of the match for deny messages.
    """

    category: str
    matched_text: str
    preview: str


def is_path_exempt_from_pii_scan(file_path: str) -> bool:
    """Return whether *file_path* must never be scanned for PII.

    Exemptions cover Python test modules (synthetic fixtures), this scanner
    family (pattern source text), and license/copyright notice files that
    intentionally name legal identity. Empty paths are **not** exempt — callers
    must still scan payload text when no real path is supplied.

    Args:
        file_path: Absolute or relative path of the file under review.

    Returns:
        True when the path is out of scope for PII scanning.
    """
    if not file_path:
        return False
    normalized_path = file_path.replace("\\", "/").lower()
    path_for_suffix_match = (
        normalized_path
        if normalized_path.startswith("/")
        else f"/{normalized_path}"
    )
    basename = os.path.basename(file_path)
    basename_lower = basename.lower()
    for each_suffix in ALL_SELF_MODULE_PATH_SUFFIXES:
        if path_for_suffix_match.endswith(each_suffix):
            return True
    if basename_lower == CONFTEST_BASENAME:
        return True
    if basename_lower.endswith(PYTHON_SOURCE_FILE_SUFFIX) and (
        basename_lower.startswith(TEST_MODULE_BASENAME_PREFIX)
        or basename_lower.endswith(TEST_MODULE_BASENAME_SUFFIX)
    ):
        return True
    if TESTS_PATH_SEGMENT in normalized_path or normalized_path.startswith(
        TESTS_PATH_PREFIX
    ):
        return True
    if basename_lower.endswith(ALL_SOURCE_TEST_FILE_SUFFIXES) and (
        SPEC_BASENAME_MARKER in basename_lower or TEST_BASENAME_MARKER in basename_lower
    ):
        return True
    if basename_lower in ALL_EXACT_LEGAL_NOTICE_BASENAMES:
        return True
    return False


def _redact_sensitive_preview(matched_text: str) -> str:
    """Return a preview that redacts the middle of a secret or email body.

    A short match collapses to a fixed placeholder. A longer match keeps a
    bounded prefix and suffix around an ellipsis, so the preview reveals at
    most a few leading and trailing characters rather than the whole body.
    """
    if len(matched_text) < MINIMUM_LENGTH_FOR_PARTIAL_REDACTION:
        return REDACTED_SHORT_PREVIEW
    prefix_length = REDACTED_PREVIEW_PREFIX_LENGTH
    suffix_length = REDACTED_PREVIEW_SUFFIX_LENGTH
    return (
        matched_text[:prefix_length]
        + REDACTED_PREVIEW_ELLIPSIS
        + matched_text[-suffix_length:]
    )


def _build_preview(matched_text: str, category: str) -> str:
    """Build a deny-message preview, redacting secret, email, and home-path matches."""
    if category in ALL_REDACTED_PREVIEW_CATEGORIES:
        return _redact_sensitive_preview(matched_text)
    if category == CATEGORY_HOME_PATH:
        return _redact_home_path_username(matched_text)
    maximum_preview_length = MAXIMUM_OFFENDING_PREVIEW_LENGTH
    if len(matched_text) <= maximum_preview_length:
        return matched_text
    return matched_text[: maximum_preview_length - 3] + "..."


def _finding(category: str, matched_text: str) -> PiiFinding:
    return PiiFinding(
        category=category,
        matched_text=matched_text,
        preview=_build_preview(matched_text, category),
    )


def _is_safe_email_domain(domain_name: str) -> bool:
    if domain_name in ALL_SAFE_EMAIL_DOMAINS:
        return True
    return any(
        domain_name.endswith("." + each_safe_domain)
        for each_safe_domain in ALL_SAFE_EMAIL_DOMAINS
    )


def _is_safe_example_email(email_address: str) -> bool:
    domain_name = email_address.rsplit("@", 1)[-1].lower()
    return _is_safe_email_domain(domain_name)


def _home_username_offset(matched_path: str) -> tuple[int, str] | None:
    """Return the (start offset, value) of the home-username segment, or None.

    The offset locates the username within *matched_path* by its home marker,
    so a same-named directory earlier in the path never shadows the real
    segment::

        C:\\Users\\Users\\file.txt  ->  (9, "Users")   the second Users, not the first

    Replacing backslashes with forward slashes preserves length, so the marker
    offset computed on the normalized path indexes *matched_path* directly.

    Args:
        matched_path: The matched home-path substring.

    Returns:
        The username's start index and value, or None when no marker is found.
    """
    normalized_path = matched_path.replace("\\", "/")
    lowered_path = normalized_path.lower()
    for each_marker in ALL_HOME_DIRECTORY_PATH_MARKERS:
        marker_index = lowered_path.find(each_marker)
        if marker_index < 0:
            continue
        username_start = marker_index + len(each_marker)
        username = normalized_path[username_start:].split("/", 1)[0]
        if not username:
            return None
        return username_start, username
    return None


def _username_from_home_path(matched_path: str) -> str | None:
    """Extract the home username segment from a matched home-path string."""
    username_offset = _home_username_offset(matched_path)
    if username_offset is None:
        return None
    _username_start, username = username_offset
    return username


def _redact_home_path_username(matched_text: str) -> str:
    """Redact only the username segment of a home path, keeping its shape."""
    username_offset = _home_username_offset(matched_text)
    if username_offset is None:
        return matched_text
    username_start, username = username_offset
    return (
        matched_text[:username_start]
        + REDACTED_SHORT_PREVIEW
        + matched_text[username_start + len(username) :]
    )


def _is_placeholder_home_username(username: str) -> bool:
    if ANGLE_BRACKET_PLACEHOLDER_PATTERN.match(username) is not None:
        return True
    lowered_username = username.lower()
    if lowered_username in ALL_PLACEHOLDER_HOME_USERNAMES:
        return True
    if lowered_username.startswith("your"):
        return True
    minimum_env_style_username_length = MINIMUM_ENV_STYLE_USERNAME_LENGTH
    if username.isupper() and len(username) >= minimum_env_style_username_length:
        return True
    return False


def _is_private_ipv4_address(address_text: str) -> bool:
    """Return True only for RFC1918 LAN addresses (not loopback/link-local/etc.)."""
    try:
        parsed_address = ipaddress.ip_address(address_text)
    except ValueError:
        return False
    if parsed_address.version != IPV4_VERSION_NUMBER:
        return False
    for each_cidr in ALL_RFC1918_NETWORK_CIDRS:
        if parsed_address in ipaddress.ip_network(each_cidr, strict=False):
            return True
    return False


def _find_emails(text: str) -> list[PiiFinding]:
    all_findings: list[PiiFinding] = []
    for each_match in EMAIL_PATTERN.finditer(text):
        email_address = each_match.group(1)
        if _is_safe_example_email(email_address):
            continue
        all_findings.append(_finding(CATEGORY_EMAIL, email_address))
    return all_findings


def _find_home_paths(text: str) -> list[PiiFinding]:
    all_findings: list[PiiFinding] = []
    for each_match in HOME_PATH_PATTERN.finditer(text):
        matched_path = each_match.group(0)
        username = _username_from_home_path(matched_path)
        if username is not None and _is_placeholder_home_username(username):
            continue
        all_findings.append(_finding(CATEGORY_HOME_PATH, matched_path))
    return all_findings


def _all_allowlisted_private_ip_addresses() -> frozenset[str]:
    """Return every private IPv4 address the scanner must leave unflagged.

    ::

        CLAUDE_NAS_HOST=10.20.30.40  ->  static set + {"10.20.30.40"}
        CLAUDE_NAS_HOST=nas.local    ->  static set only (a name, not an address)
        (env unset, no file)         ->  static set only

    The committed set carries no real address. The maintainer's own NAS host
    resolves at scan time from ``CLAUDE_NAS_HOST`` or
    ``~/.claude/local-identity.json``, so their ssh traffic and git-ignored
    local config stay unflagged while the repository stays publishable.

    Returns:
        The static allowlist, joined with the locally configured NAS host when
        that host is itself a private IPv4 address.
    """
    configured_nas_host = nas_host()
    if not _is_private_ipv4_address(configured_nas_host):
        return ALL_ALLOWLISTED_PRIVATE_IP_ADDRESSES
    return ALL_ALLOWLISTED_PRIVATE_IP_ADDRESSES | {configured_nas_host}


def _find_private_ips(text: str) -> list[PiiFinding]:
    all_findings: list[PiiFinding] = []
    allowlisted_addresses = _all_allowlisted_private_ip_addresses()
    for each_match in IPV4_PATTERN.finditer(text):
        address_text = each_match.group(1)
        if address_text in allowlisted_addresses:
            continue
        if not _is_private_ipv4_address(address_text):
            continue
        all_findings.append(_finding(CATEGORY_PRIVATE_IP, address_text))
    return all_findings


def _find_secrets(text: str) -> list[PiiFinding]:
    all_findings: list[PiiFinding] = []
    for each_pattern in ALL_SECRET_PATTERNS:
        for each_match in each_pattern.finditer(text):
            all_findings.append(_finding(CATEGORY_SECRET, each_match.group(0)))
    return all_findings


def scan_text_for_pii(text: str) -> list[PiiFinding]:
    """Return high-confidence PII and secret findings in *text*.

    Safe residual examples (``user@example.com``, placeholder home users such
    as ``example``/``alice``, allowlisted private IPs) are omitted. Findings
    are capped so deny messages stay readable.

    ::

        ok:   "contact user@example.com"           -> []
        ok:   r"C:\\Users\\example\\notes.txt"     -> []
        flag: "contact person@company.io"          -> [email]
        flag: r"C:\\Users\\realname\\notes.txt"    -> [home-path]
        flag: "NAS at 10.0.0.5"                    -> [private-ip]
        flag: "ghp_" + ("x" * 36)                  -> [secret]

    Args:
        text: Arbitrary text that would be written, posted, or committed.

    Returns:
        Zero or more findings in first-seen order, deduplicated by
        (category, matched_text), capped at ``MAXIMUM_FINDINGS_PER_SCAN``.
    """
    if not text:
        return []
    all_category_finders: tuple[Callable[[str], list[PiiFinding]], ...] = (
        _find_emails,
        _find_home_paths,
        _find_private_ips,
        _find_secrets,
    )
    all_findings: list[PiiFinding] = []
    all_seen_keys: set[tuple[str, str]] = set()
    maximum_findings_per_scan = MAXIMUM_FINDINGS_PER_SCAN
    for each_finder in all_category_finders:
        for each_finding in each_finder(text):
            category_and_match = (each_finding.category, each_finding.matched_text)
            if category_and_match in all_seen_keys:
                continue
            all_seen_keys.add(category_and_match)
            all_findings.append(each_finding)
            if len(all_findings) >= maximum_findings_per_scan:
                return all_findings
    return all_findings
