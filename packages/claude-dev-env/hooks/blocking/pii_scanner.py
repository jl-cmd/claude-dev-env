"""Pure text scanners for high-confidence PII and secret material.

Returns structured findings only. Callers decide whether to deny a Write,
a durable GitHub post, or a git commit that carries the match.
"""

from __future__ import annotations

import ipaddress
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

_hooks_directory = str(Path(__file__).resolve().parent.parent)
if _hooks_directory not in sys.path:
    sys.path.insert(0, _hooks_directory)

from hooks_constants.pii_prevention_constants import (  # noqa: E402
    ALL_ALLOWLISTED_PRIVATE_IP_ADDRESSES,
    ALL_LICENSE_BASENAME_PREFIXES,
    ALL_PLACEHOLDER_HOME_USERNAMES,
    ALL_SAFE_EMAIL_DOMAINS,
    ALL_SELF_MODULE_BASENAMES,
    ANGLE_BRACKET_PLACEHOLDER_PATTERN,
    AWS_ACCESS_KEY_PATTERN,
    CATEGORY_EMAIL,
    CATEGORY_HOME_PATH,
    CATEGORY_PRIVATE_IP,
    CATEGORY_SECRET,
    EMAIL_PATTERN,
    GITHUB_FINE_GRAINED_TOKEN_PATTERN,
    GITHUB_TOKEN_PATTERN,
    HOME_PATH_PATTERN,
    HOME_PATH_USERNAME_CAPTURE_PATTERN,
    IPV4_PATTERN,
    IPV4_VERSION_NUMBER,
    MAXIMUM_FINDINGS_PER_SCAN,
    MAXIMUM_OFFENDING_PREVIEW_LENGTH,
    MINIMUM_ENV_STYLE_USERNAME_LENGTH,
    PEM_PRIVATE_KEY_HEADER_PATTERN,
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

    Exemptions cover test files (which hold synthetic fixtures), this scanner
    family itself (pattern source text), and license/copyright notice files
    that intentionally name legal identity.

    Args:
        file_path: Absolute or relative path of the file under review.

    Returns:
        True when the path is out of scope for PII scanning.
    """
    if not file_path:
        return True
    normalized_path = file_path.replace("\\", "/").lower()
    basename = os.path.basename(file_path)
    basename_lower = basename.lower()
    if basename in ALL_SELF_MODULE_BASENAMES:
        return True
    if basename_lower.startswith("test_") or basename_lower.endswith("_test.py"):
        return True
    if "/tests/" in normalized_path or normalized_path.startswith("tests/"):
        return True
    if ".spec." in basename_lower or ".test." in basename_lower:
        return True
    if basename_lower == "conftest.py":
        return True
    for each_prefix in ALL_LICENSE_BASENAME_PREFIXES:
        if basename.upper().startswith(each_prefix):
            return True
    return False


def _build_preview(matched_text: str) -> str:
    maximum_preview_length = MAXIMUM_OFFENDING_PREVIEW_LENGTH
    if len(matched_text) <= maximum_preview_length:
        return matched_text
    return matched_text[: maximum_preview_length - 3] + "..."


def _email_domain(email_address: str) -> str:
    return email_address.rsplit("@", 1)[-1].lower()


def _is_safe_email_domain(domain_name: str) -> bool:
    if domain_name in ALL_SAFE_EMAIL_DOMAINS:
        return True
    return any(
        domain_name.endswith("." + each_safe_domain)
        for each_safe_domain in ALL_SAFE_EMAIL_DOMAINS
    )


def _home_username_from_match(matched_path: str) -> str | None:
    capture = HOME_PATH_USERNAME_CAPTURE_PATTERN.search(matched_path)
    if capture is None:
        return None
    for each_group in capture.groups():
        if each_group:
            return each_group
    return None


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
    try:
        parsed_address = ipaddress.ip_address(address_text)
    except ValueError:
        return False
    ipv4_version_number = IPV4_VERSION_NUMBER
    if parsed_address.version != ipv4_version_number:
        return False
    return bool(parsed_address.is_private)


def _append_finding(
    all_findings: list[PiiFinding],
    category: str,
    matched_text: str,
    all_seen_keys: set[tuple[str, str]],
) -> bool:
    category_and_match = (category, matched_text)
    if category_and_match in all_seen_keys:
        return len(all_findings) >= MAXIMUM_FINDINGS_PER_SCAN
    all_seen_keys.add(category_and_match)
    all_findings.append(
        PiiFinding(
            category=category,
            matched_text=matched_text,
            preview=_build_preview(matched_text),
        )
    )
    return len(all_findings) >= MAXIMUM_FINDINGS_PER_SCAN


def _scan_emails(
    text: str,
    all_findings: list[PiiFinding],
    all_seen_keys: set[tuple[str, str]],
) -> bool:
    for each_match in EMAIL_PATTERN.finditer(text):
        email_address = each_match.group(1)
        if _is_safe_example_email(email_address):
            continue
        if _append_finding(all_findings, CATEGORY_EMAIL, email_address, all_seen_keys):
            return True
    return False


def _is_safe_example_email(email_address: str) -> bool:
    return _is_safe_email_domain(_email_domain(email_address))


def _scan_home_paths(
    text: str,
    all_findings: list[PiiFinding],
    all_seen_keys: set[tuple[str, str]],
) -> bool:
    for each_match in HOME_PATH_PATTERN.finditer(text):
        matched_path = each_match.group(0)
        username = _home_username_from_match(matched_path)
        if username is not None and _is_placeholder_home_username(username):
            continue
        if _append_finding(
            all_findings, CATEGORY_HOME_PATH, matched_path, all_seen_keys
        ):
            return True
    return False


def _scan_private_ips(
    text: str,
    all_findings: list[PiiFinding],
    all_seen_keys: set[tuple[str, str]],
) -> bool:
    allowlisted_addresses = ALL_ALLOWLISTED_PRIVATE_IP_ADDRESSES
    for each_match in IPV4_PATTERN.finditer(text):
        address_text = each_match.group(1)
        if address_text in allowlisted_addresses:
            continue
        if not _is_private_ipv4_address(address_text):
            continue
        if _append_finding(
            all_findings, CATEGORY_PRIVATE_IP, address_text, all_seen_keys
        ):
            return True
    return False


def _scan_secrets(
    text: str,
    all_findings: list[PiiFinding],
    all_seen_keys: set[tuple[str, str]],
) -> bool:
    all_secret_patterns: tuple[re.Pattern[str], ...] = (
        GITHUB_TOKEN_PATTERN,
        GITHUB_FINE_GRAINED_TOKEN_PATTERN,
        AWS_ACCESS_KEY_PATTERN,
        PEM_PRIVATE_KEY_HEADER_PATTERN,
    )
    for each_pattern in all_secret_patterns:
        for each_match in each_pattern.finditer(text):
            matched_secret = each_match.group(0)
            if _append_finding(
                all_findings, CATEGORY_SECRET, matched_secret, all_seen_keys
            ):
                return True
    return False


def scan_text_for_pii(text: str) -> list[PiiFinding]:
    """Return high-confidence PII and secret findings in *text*.

    Safe residual examples (``user@example.com``, placeholder home users,
    allowlisted private IPs) are omitted. Findings are capped so deny messages
    stay readable.

    ::

        ok:   "contact user@example.com"           -> []
        flag: "contact person@company.io"          -> [email]
        flag: r"C:\\Users\\realname\\notes.txt"    -> [home-path]
        flag: "NAS at 192.168.1.50"                 -> [private-ip]
        flag: "ghp_" + ("x" * 36)                  -> [secret]

    Args:
        text: Arbitrary text that would be written, posted, or committed.

    Returns:
        Zero or more findings in first-seen order.
    """
    if not text:
        return []
    all_findings: list[PiiFinding] = []
    all_seen_keys: set[tuple[str, str]] = set()
    if _scan_emails(text, all_findings, all_seen_keys):
        return all_findings
    if _scan_home_paths(text, all_findings, all_seen_keys):
        return all_findings
    if _scan_private_ips(text, all_findings, all_seen_keys):
        return all_findings
    if _scan_secrets(text, all_findings, all_seen_keys):
        return all_findings
    return all_findings
