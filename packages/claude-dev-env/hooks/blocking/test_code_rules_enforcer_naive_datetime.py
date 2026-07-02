"""Tests for the naive-datetime-construction check in code_rules_imports_logging.py.

The check catches the DST-fold-ambiguity class Copilot flagged on
python-automation PR #557: ``datetime.fromtimestamp(epoch)`` builds a datetime
with no timezone, and a later ``.astimezone()`` on that naive value has to guess
the local offset. The check flags the naive-producing constructors
(``fromtimestamp``/``utcfromtimestamp`` without ``tz=``, and ``utcnow``) and
leaves a ``tz=``-carrying call, and a plain ``now()``, alone.
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

PRODUCTION_FILE_PATH = "/project/src/export_verification.py"
TEST_FILE_PATH = "/project/src/test_export_verification.py"


def check_naive_datetime_construction(content: str, file_path: str) -> list[str]:
    return code_rules_enforcer.check_naive_datetime_construction(content, file_path)


def test_flags_fromtimestamp_without_timezone() -> None:
    content = (
        "from datetime import datetime\n"
        "def describe(stamp: float) -> str:\n"
        "    return datetime.fromtimestamp(stamp).astimezone().isoformat()\n"
    )
    issues = check_naive_datetime_construction(content, PRODUCTION_FILE_PATH)
    assert len(issues) == 1
    assert "fromtimestamp" in issues[0]
    assert "tz=" in issues[0]


def test_flags_utcfromtimestamp_and_utcnow() -> None:
    content = (
        "from datetime import datetime\n"
        "def build(stamp: float) -> tuple[object, object]:\n"
        "    return datetime.utcfromtimestamp(stamp), datetime.utcnow()\n"
    )
    issues = check_naive_datetime_construction(content, PRODUCTION_FILE_PATH)
    assert len(issues) == 2


def test_flags_module_qualified_datetime_call() -> None:
    content = (
        "import datetime\n"
        "def describe(stamp: float) -> object:\n"
        "    return datetime.datetime.fromtimestamp(stamp)\n"
    )
    issues = check_naive_datetime_construction(content, PRODUCTION_FILE_PATH)
    assert len(issues) == 1


def test_allows_fromtimestamp_with_timezone_keyword() -> None:
    content = (
        "from datetime import datetime, timezone\n"
        "def describe(stamp: float) -> str:\n"
        "    return datetime.fromtimestamp(stamp, tz=timezone.utc).isoformat()\n"
    )
    issues = check_naive_datetime_construction(content, PRODUCTION_FILE_PATH)
    assert issues == []


def test_allows_fromtimestamp_with_positional_timezone() -> None:
    content = (
        "from datetime import datetime, timezone\n"
        "def describe(stamp: float) -> str:\n"
        "    return datetime.fromtimestamp(stamp, timezone.utc).isoformat()\n"
    )
    issues = check_naive_datetime_construction(content, PRODUCTION_FILE_PATH)
    assert issues == []


def test_allows_module_qualified_fromtimestamp_with_positional_timezone() -> None:
    content = (
        "import datetime\n"
        "def describe(stamp: float) -> object:\n"
        "    return datetime.datetime.fromtimestamp(stamp, datetime.timezone.utc)\n"
    )
    issues = check_naive_datetime_construction(content, PRODUCTION_FILE_PATH)
    assert issues == []


def test_flags_utcfromtimestamp_with_second_positional_argument() -> None:
    content = (
        "from datetime import datetime\n"
        "def describe(stamp: float, other: float) -> object:\n"
        "    return datetime.utcfromtimestamp(stamp, other)\n"
    )
    issues = check_naive_datetime_construction(content, PRODUCTION_FILE_PATH)
    assert len(issues) == 1


def test_allows_plain_now() -> None:
    content = (
        "from datetime import datetime\n"
        "def stamp() -> str:\n"
        "    return datetime.now().isoformat()\n"
    )
    issues = check_naive_datetime_construction(content, PRODUCTION_FILE_PATH)
    assert issues == []


def test_exempts_test_files() -> None:
    content = (
        "from datetime import datetime\n"
        "def describe(stamp: float) -> object:\n"
        "    return datetime.fromtimestamp(stamp)\n"
    )
    issues = check_naive_datetime_construction(content, TEST_FILE_PATH)
    assert issues == []
