"""Tests for security vulnerability detection."""

import ast

import pytest

from security_checks import (
    check_hardcoded_secrets,
    check_sql_injection,
    check_xss_risk,
)
from validator_base import Violation


GOOD_NO_SECRETS = '''
import os

def get_api_key():
    return os.environ.get("API_KEY")
'''

BAD_HARDCODED_API_KEY = '''
API_KEY = "sk-abc123xyz789"
'''

BAD_HARDCODED_PASSWORD = '''
def connect():
    password = "super_secret_123"
    return password
'''

GOOD_PARAMETERIZED_SQL = '''
def get_user(user_id):
    cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
'''

BAD_FSTRING_SQL = '''
def get_user(user_id):
    cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")
'''

BAD_FORMAT_SQL = '''
def get_user(user_id):
    cursor.execute("SELECT * FROM users WHERE id = {}".format(user_id))
'''

GOOD_ESCAPED_HTML = '''
from django.utils.html import escape

def render(user_input):
    return escape(user_input)
'''

BAD_MARK_SAFE = '''
from django.utils.safestring import mark_safe

def render(user_input):
    return mark_safe(user_input)
'''


class TestHardcodedSecrets:
    def test_env_variable_passes(self) -> None:
        tree = ast.parse(GOOD_NO_SECRETS)
        violations = check_hardcoded_secrets(tree, "test.py")
        assert violations == []

    def test_hardcoded_api_key_fails(self) -> None:
        tree = ast.parse(BAD_HARDCODED_API_KEY)
        violations = check_hardcoded_secrets(tree, "test.py")
        assert len(violations) == 1
        assert "API_KEY" in violations[0].message or "secret" in violations[0].message.lower()

    def test_hardcoded_password_fails(self) -> None:
        tree = ast.parse(BAD_HARDCODED_PASSWORD)
        violations = check_hardcoded_secrets(tree, "test.py")
        assert len(violations) == 1


class TestSqlInjection:
    def test_parameterized_query_passes(self) -> None:
        violations = check_sql_injection(GOOD_PARAMETERIZED_SQL, "test.py")
        assert violations == []

    def test_fstring_sql_fails(self) -> None:
        violations = check_sql_injection(BAD_FSTRING_SQL, "test.py")
        assert len(violations) == 1
        assert "SQL" in violations[0].message or "injection" in violations[0].message.lower()

    def test_format_sql_fails(self) -> None:
        violations = check_sql_injection(BAD_FORMAT_SQL, "test.py")
        assert len(violations) == 1


class TestXssRisk:
    def test_escaped_html_passes(self) -> None:
        tree = ast.parse(GOOD_ESCAPED_HTML)
        violations = check_xss_risk(tree, "test.py")
        assert violations == []

    def test_mark_safe_fails(self) -> None:
        tree = ast.parse(BAD_MARK_SAFE)
        violations = check_xss_risk(tree, "test.py")
        assert len(violations) == 1
        assert "mark_safe" in violations[0].message or "XSS" in violations[0].message
