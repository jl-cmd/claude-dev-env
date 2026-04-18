"""Regression tests for .test.{ts,tsx,js} recognition in code-rules-enforcer."""

import importlib.util
import pathlib


def _load_enforcer_module():
    enforcer_path = pathlib.Path(__file__).parent / "code-rules-enforcer.py"
    spec = importlib.util.spec_from_file_location("code_rules_enforcer", enforcer_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


enforcer = _load_enforcer_module()


def test_is_test_file_should_recognize_dot_test_tsx_files():
    assert enforcer.is_test_file("C:/foo/Button.test.tsx") is True


def test_is_test_file_should_recognize_dot_test_ts_files():
    assert enforcer.is_test_file("C:/foo/Button.test.ts") is True


def test_is_test_file_should_recognize_dot_test_js_files():
    assert enforcer.is_test_file("C:/foo/Button.test.js") is True


def test_is_test_file_should_still_recognize_python_test_files():
    assert enforcer.is_test_file("C:/foo/test_foo.py") is True
    assert enforcer.is_test_file("C:/foo/foo_test.py") is True
    assert enforcer.is_test_file("C:/foo/conftest.py") is True
    assert enforcer.is_test_file("C:/foo/foo.spec.ts") is True


def test_is_hook_infrastructure_should_recognize_packages_claude_dev_env_hooks_forward_slash():
    assert enforcer.is_hook_infrastructure("/repo/packages/claude-dev-env/hooks/blocking/foo.py") is True


def test_is_hook_infrastructure_should_recognize_packages_claude_dev_env_hooks_backslash():
    assert enforcer.is_hook_infrastructure("C:\\repo\\packages\\claude-dev-env\\hooks\\blocking\\foo.py") is True


def test_is_hook_infrastructure_should_recognize_packages_claude_dev_env_hooks_validators():
    assert enforcer.is_hook_infrastructure("/repo/packages/claude-dev-env/hooks/validators/bar.py") is True


def test_is_hook_infrastructure_should_still_recognize_dot_claude_hooks():
    assert enforcer.is_hook_infrastructure("C:/Users/jon/.claude/hooks/blocking/foo.py") is True
    assert enforcer.is_hook_infrastructure("/home/user/.claude/hooks/blocking/foo.py") is True


def test_is_hook_infrastructure_should_not_match_unrelated_package_path():
    assert enforcer.is_hook_infrastructure("/repo/packages/other-package/src/foo.py") is False
