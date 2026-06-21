"""Tests for check_docstring_unguarded_malformed_payload_claim — Category O8 drift.

A function docstring that promises "a malformed payload resolves to None" asserts
the body catches a bad payload and turns it into a None return. The claim drifts
when the value construction that dereferences payload fields (``payload["key"]``,
``float(payload["key"])``) sits OUTSIDE the try/except whose handler returns None:
a present-but-malformed payload raises KeyError or TypeError from that unguarded
dereference and propagates rather than resolving to None. This is the deterministic
slice of Category O8 (docstring prose vs implementation drift) for an
exception-guard claim.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


def _load_enforcer_module() -> ModuleType:
    module_path = Path(__file__).parent / "code_rules_enforcer.py"
    spec = importlib.util.spec_from_file_location("code_rules_enforcer", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


code_rules_enforcer = _load_enforcer_module()


def check_docstring_unguarded_malformed_payload_claim(content: str, file_path: str) -> list[str]:
    return code_rules_enforcer.check_docstring_unguarded_malformed_payload_claim(content, file_path)


PRODUCTION_FILE_PATH = "/project/shared/human_actions.py"
TEST_FILE_PATH = "/project/shared/test_human_actions.py"
HOOK_INFRASTRUCTURE_PATH = "/home/user/.claude/hooks/blocking/example.py"


_UNGUARDED_DEREFERENCE_BODY = (
    "def read_metrics(self, selector: str) -> object:\n"
    '    """Read the container geometry over CDP, or None on failure.\n'
    "\n"
    "    A missing element, a CDP error, or a malformed payload resolves to None\n"
    "    so the caller skips the drag.\n"
    '    """\n'
    "    try:\n"
    "        evaluate_payload = self.cdp.run(selector)\n"
    "        parsed_metrics = json.loads(evaluate_payload)\n"
    "    except (KeyError, TypeError, ValueError):\n"
    "        return None\n"
    '    if not parsed_metrics.get("found"):\n'
    "        return None\n"
    "    return Metrics(\n"
    '        client_width=float(parsed_metrics["client_width"]),\n'
    '        client_height=float(parsed_metrics["client_height"]),\n'
    "    )\n"
)


def test_flags_dereference_outside_the_guarded_block() -> None:
    issues = check_docstring_unguarded_malformed_payload_claim(
        _UNGUARDED_DEREFERENCE_BODY, PRODUCTION_FILE_PATH
    )
    assert len(issues) == 1
    assert "read_metrics" in issues[0]


def test_passes_when_dereference_sits_inside_the_guarded_block() -> None:
    content = (
        "def read_metrics(self, selector: str) -> object:\n"
        '    """Read the container geometry over CDP, or None on failure.\n'
        "\n"
        "    A missing element, a CDP error, or a malformed payload resolves to None\n"
        "    so the caller skips the drag.\n"
        '    """\n'
        "    try:\n"
        "        evaluate_payload = self.cdp.run(selector)\n"
        "        parsed_metrics = json.loads(evaluate_payload)\n"
        '        if not parsed_metrics.get("found"):\n'
        "            return None\n"
        "        return Metrics(\n"
        '            client_width=float(parsed_metrics["client_width"]),\n'
        '            client_height=float(parsed_metrics["client_height"]),\n'
        "        )\n"
        "    except (KeyError, TypeError, ValueError):\n"
        "        return None\n"
    )
    assert check_docstring_unguarded_malformed_payload_claim(content, PRODUCTION_FILE_PATH) == []


def test_passes_when_docstring_makes_no_malformed_payload_claim() -> None:
    content = (
        "def read_metrics(self, selector: str) -> object:\n"
        '    """Read the container geometry over CDP, or None on failure."""\n'
        "    try:\n"
        "        parsed_metrics = json.loads(self.cdp.run(selector))\n"
        "    except (KeyError, TypeError, ValueError):\n"
        "        return None\n"
        "    return Metrics(\n"
        '        client_width=float(parsed_metrics["client_width"]),\n'
        "    )\n"
    )
    assert check_docstring_unguarded_malformed_payload_claim(content, PRODUCTION_FILE_PATH) == []


def test_passes_when_no_subscript_dereference_follows_the_guard() -> None:
    content = (
        "def read_metrics(self, selector: str) -> object:\n"
        '    """Read the geometry over CDP, or None on failure.\n'
        "\n"
        "    A malformed payload resolves to None so the caller skips the drag.\n"
        '    """\n'
        "    try:\n"
        "        parsed_metrics = json.loads(self.cdp.run(selector))\n"
        "    except (KeyError, TypeError, ValueError):\n"
        "        return None\n"
        '    return parsed_metrics.get("found")\n'
    )
    assert check_docstring_unguarded_malformed_payload_claim(content, PRODUCTION_FILE_PATH) == []


def test_test_files_are_exempt() -> None:
    assert (
        check_docstring_unguarded_malformed_payload_claim(
            _UNGUARDED_DEREFERENCE_BODY, TEST_FILE_PATH
        )
        == []
    )


def test_hook_infrastructure_is_exempt() -> None:
    assert (
        check_docstring_unguarded_malformed_payload_claim(
            _UNGUARDED_DEREFERENCE_BODY, HOOK_INFRASTRUCTURE_PATH
        )
        == []
    )
