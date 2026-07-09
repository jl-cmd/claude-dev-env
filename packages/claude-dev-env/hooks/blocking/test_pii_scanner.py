"""Behavior tests for the pure PII scanner."""

from __future__ import annotations

import sys
from pathlib import Path

_HOOK_DIR = Path(__file__).parent
_HOOKS_DIR = _HOOK_DIR.parent
if str(_HOOK_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOK_DIR))
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))

from pii_scanner import (  # noqa: E402
    is_path_exempt_from_pii_scan,
    scan_text_for_pii,
)

SYNTHETIC_GITHUB_TOKEN = "ghp_" + ("A" * 36)
SYNTHETIC_AWS_KEY = "AKIA" + ("B" * 16)
SYNTHETIC_PEM_HEADER = "-----BEGIN RSA PRIVATE KEY-----"
SYNTHETIC_REAL_EMAIL = "person.fixture@company-example.io"
SYNTHETIC_SAFE_EMAIL = "user@example.com"
SYNTHETIC_HOME_PATH = r"C:\Users\fixture_real_user\notes.txt"
SYNTHETIC_PLACEHOLDER_HOME = r"C:\Users\<you>\notes.txt"
SYNTHETIC_PRIVATE_IP = "192.168.42.17"
SYNTHETIC_PUBLIC_IP = "8.8.8.8"


def test_flags_real_email_and_allows_example_domain() -> None:
    all_email_hits = scan_text_for_pii(f"contact {SYNTHETIC_REAL_EMAIL}")
    all_safe_hits = scan_text_for_pii(f"contact {SYNTHETIC_SAFE_EMAIL}")
    assert any(each.category == "email" for each in all_email_hits)
    assert all_email_hits[0].matched_text == SYNTHETIC_REAL_EMAIL
    assert all_safe_hits == []


def test_flags_home_path_and_allows_placeholder_user() -> None:
    all_home_hits = scan_text_for_pii(f"path is {SYNTHETIC_HOME_PATH}")
    all_placeholder_hits = scan_text_for_pii(f"path is {SYNTHETIC_PLACEHOLDER_HOME}")
    assert any(each.category == "home-path" for each in all_home_hits)
    assert all_placeholder_hits == []


def test_allows_hygiene_placeholder_username_example() -> None:
    assert scan_text_for_pii(r"path is C:\Users\example\notes.txt") == []
    assert scan_text_for_pii("path is C:/Users/example/.claude/hooks") == []


def test_flags_unix_home_path() -> None:
    all_unix_hits = scan_text_for_pii(
        "config lives in /Users/fixture_real_user/.config"
    )
    assert any(each.category == "home-path" for each in all_unix_hits)


def test_flags_private_ip_and_allows_public_ip() -> None:
    all_lan_hits = scan_text_for_pii(f"host {SYNTHETIC_PRIVATE_IP}")
    all_dns_hits = scan_text_for_pii(f"dns {SYNTHETIC_PUBLIC_IP}")
    assert any(each.category == "private-ip" for each in all_lan_hits)
    assert all_lan_hits[0].matched_text == SYNTHETIC_PRIVATE_IP
    assert all_dns_hits == []


def test_allows_loopback_unspecified_and_link_local_addresses() -> None:
    assert scan_text_for_pii("http://127.0.0.1:8080/health") == []
    assert scan_text_for_pii("Listen on 0.0.0.0:8000") == []
    assert scan_text_for_pii("peer 169.254.10.20") == []


def test_allows_product_nas_private_ip() -> None:
    assert scan_text_for_pii("ssh -p 9222 jon@192.168.1.100 uptime") == []


def test_flags_github_token_aws_key_and_pem_header() -> None:
    all_github_hits = scan_text_for_pii(f"export TOKEN={SYNTHETIC_GITHUB_TOKEN}")
    all_aws_hits = scan_text_for_pii(f"key={SYNTHETIC_AWS_KEY}")
    all_pem_hits = scan_text_for_pii(SYNTHETIC_PEM_HEADER + "\nabc\n")
    assert any(each.category == "secret" for each in all_github_hits)
    assert any(each.category == "secret" for each in all_aws_hits)
    assert any(each.category == "secret" for each in all_pem_hits)


def test_secret_and_email_previews_are_redacted() -> None:
    all_secret_hits = scan_text_for_pii(f"export TOKEN={SYNTHETIC_GITHUB_TOKEN}")
    all_email_hits = scan_text_for_pii(f"contact {SYNTHETIC_REAL_EMAIL}")
    secret_finding = next(
        each for each in all_secret_hits if each.category == "secret"
    )
    email_finding = next(each for each in all_email_hits if each.category == "email")
    assert secret_finding.matched_text == SYNTHETIC_GITHUB_TOKEN
    assert SYNTHETIC_GITHUB_TOKEN not in secret_finding.preview
    assert "…" in secret_finding.preview
    assert email_finding.matched_text == SYNTHETIC_REAL_EMAIL
    assert SYNTHETIC_REAL_EMAIL not in email_finding.preview
    assert "…" in email_finding.preview


def test_allows_common_cloud_and_system_home_usernames() -> None:
    assert scan_text_for_pii(r"C:\Users\ubuntu\notes.txt") == []
    assert scan_text_for_pii(r"C:\Users\admin\notes.txt") == []
    assert scan_text_for_pii("/home/runner/work/repo") == []
    assert scan_text_for_pii("/home/container/app") == []


def test_flags_genuine_human_home_username() -> None:
    all_human_hits = scan_text_for_pii(r"C:\Users\johnsmith\notes.txt")
    assert any(each.category == "home-path" for each in all_human_hits)


def test_short_nonsafe_email_preview_is_fully_redacted() -> None:
    all_email_hits = scan_text_for_pii("reach owner@acme.io")
    email_finding = next(
        each for each in all_email_hits if each.category == "email"
    )
    assert email_finding.matched_text == "owner@acme.io"
    assert email_finding.preview == "[redacted]"
    assert "owner" not in email_finding.preview


def test_home_path_preview_redacts_only_the_username() -> None:
    all_home_hits = scan_text_for_pii(r"path is C:\Users\johnsmith\secret.txt")
    home_finding = next(
        each for each in all_home_hits if each.category == "home-path"
    )
    assert "johnsmith" not in home_finding.preview
    assert "[redacted]" in home_finding.preview
    assert "Users" in home_finding.preview


def test_clean_prose_returns_no_findings() -> None:
    prose = "Ship the fix. Use user@example.com in docs. Path is C:/Users/<you>/."
    assert scan_text_for_pii(prose) == []


def test_path_exemptions_for_tests_license_and_self_modules() -> None:
    assert is_path_exempt_from_pii_scan("packages/hooks/blocking/test_pii_scanner.py")
    assert is_path_exempt_from_pii_scan("LICENSE")
    assert is_path_exempt_from_pii_scan("LICENSE.md")
    assert is_path_exempt_from_pii_scan("hooks/blocking/pii_scanner.py")
    assert is_path_exempt_from_pii_scan(
        "packages/claude-dev-env/hooks/hooks_constants/pii_prevention_constants.py"
    )
    assert not is_path_exempt_from_pii_scan("vendor/pii_scanner.py")
    assert not is_path_exempt_from_pii_scan("not_hooks/blocking/pii_scanner.py")
    assert not is_path_exempt_from_pii_scan("xhooks/blocking/pii_scanner.py")
    assert not is_path_exempt_from_pii_scan("LICENSE_leak.env")
    assert not is_path_exempt_from_pii_scan("src/app/settings.md")
    assert not is_path_exempt_from_pii_scan("test_notes.md")
    assert not is_path_exempt_from_pii_scan("test_secrets.env")
    assert not is_path_exempt_from_pii_scan("")


def test_empty_path_still_scans_payload_text() -> None:
    all_hits = scan_text_for_pii(f"contact {SYNTHETIC_REAL_EMAIL}")
    assert any(each.category == "email" for each in all_hits)
