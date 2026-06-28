"""Tests for check_docstring_no_network_claim_with_metadata_access — Category O6.

A docstring promising a code path returns "without touching the network" drifts
when the body calls a path-metadata method (``is_file``, ``stat``, ...): on a
network share each metadata call is a round-trip over the wire, so the no-network
claim is false. This is the deterministic slice of Category O6 (docstring prose
versus implementation drift) for a no-network claim.
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


def check_docstring_no_network_claim(content: str, file_path: str) -> list[str]:
    return code_rules_enforcer.check_docstring_no_network_claim_with_metadata_access(
        content, file_path
    )


PRODUCTION_FILE_PATH = "/project/shared_utils/bws/secret_fetch.py"
TEST_FILE_PATH = "/project/shared_utils/bws/tests/test_secret_fetch.py"
HOOK_INFRASTRUCTURE_PATH = "/home/user/.claude/hooks/blocking/example.py"


def test_flags_no_network_claim_with_is_file_and_stat() -> None:
    content = (
        "def _ensure_local_bws_cache() -> str:\n"
        '    """Return the local cache path, repopulating when stale.\n'
        "\n"
        "    An existing cache is returned without touching the network; a\n"
        "    missing or size-mismatched cache is repopulated from the bundled\n"
        "    executable.\n"
        '    """\n'
        "    if BUNDLED_BWS_EXECUTABLE_PATH.is_file():\n"
        "        bundled_size = BUNDLED_BWS_EXECUTABLE_PATH.stat().st_size\n"
        "        return str(LOCAL_BWS_CACHE_PATH)\n"
        "    return str(LOCAL_BWS_CACHE_PATH)\n"
    )
    issues = check_docstring_no_network_claim(content, PRODUCTION_FILE_PATH)
    assert len(issues) == 1
    assert "_ensure_local_bws_cache" in issues[0]
    assert "without touching the network" in issues[0]


def test_flags_no_network_access_phrase_with_exists() -> None:
    content = (
        "def read_warm_cache(cache_path) -> str:\n"
        '    """Serve the warm cache with no network access."""\n'
        "    if cache_path.exists():\n"
        "        return cache_path.read_text()\n"
        "    return ''\n"
    )
    assert len(check_docstring_no_network_claim(content, PRODUCTION_FILE_PATH)) == 1


def test_passes_when_claim_present_but_no_metadata_access() -> None:
    content = (
        "def read_warm_cache(cache_path) -> str:\n"
        '    """Serve the warm cache without touching the network."""\n'
        "    return cache_path.read_text()\n"
    )
    assert check_docstring_no_network_claim(content, PRODUCTION_FILE_PATH) == []


def test_passes_when_metadata_access_but_no_network_claim() -> None:
    content = (
        "def _ensure_local_bws_cache(share_path) -> str:\n"
        '    """Return the local cache path, repopulating when stale.\n'
        "\n"
        "    The bundled share is stat-checked on every call to validate the\n"
        "    cache against the bundled executable size.\n"
        '    """\n'
        "    if share_path.is_file():\n"
        "        return str(share_path)\n"
        "    return ''\n"
    )
    assert check_docstring_no_network_claim(content, PRODUCTION_FILE_PATH) == []


def test_test_files_are_exempt() -> None:
    content = (
        "def _ensure_local_bws_cache(share_path) -> str:\n"
        '    """Return the cache without touching the network."""\n'
        "    if share_path.is_file():\n"
        "        return str(share_path)\n"
        "    return ''\n"
    )
    assert check_docstring_no_network_claim(content, TEST_FILE_PATH) == []


def test_hook_infrastructure_is_exempt() -> None:
    content = (
        "def _ensure_local_bws_cache(share_path) -> str:\n"
        '    """Return the cache without touching the network."""\n'
        "    if share_path.is_file():\n"
        "        return str(share_path)\n"
        "    return ''\n"
    )
    assert check_docstring_no_network_claim(content, HOOK_INFRASTRUCTURE_PATH) == []
