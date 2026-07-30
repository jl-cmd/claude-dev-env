"""Parity gates for the AGENTS.md / CODE_RULES / enforcer policy surface.

::

    type-ignore justification   ok: AGENTS + CODE_RULES + enforcer agree
    constant location           ok: config/ named in AGENTS + CODE_RULES
    enforcer table rows         ok: named check_* callables exist
    BugBot projection           ok: sync_ai_rules.py --check exits 0
    session policy refs         ok: question-routing and task-tracking files exist

These checks fail when a projection restates a rule with divergent wording or
when the hand-maintained enforcer drops a mechanical rule the AGENTS table
still names.
"""

from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from pathlib import Path

REPOSITORY_ROOT: Path = Path(__file__).resolve().parent.parent
AGENTS_PATH: Path = REPOSITORY_ROOT / "AGENTS.md"
CODE_RULES_PATH: Path = (
    REPOSITORY_ROOT / "packages" / "claude-dev-env" / "docs" / "CODE_RULES.md"
)
CODE_STANDARDS_PATH: Path = (
    REPOSITORY_ROOT
    / "packages"
    / "claude-dev-env"
    / "rules"
    / "code-standards.md"
)
ENFORCER_PATH: Path = (
    REPOSITORY_ROOT
    / "packages"
    / "claude-dev-env"
    / "hooks"
    / "blocking"
    / "code_rules_enforcer.py"
)
QUESTION_ROUTING_RULE_PATH: Path = (
    REPOSITORY_ROOT
    / "packages"
    / "claude-dev-env"
    / "rules"
    / "ask-user-question-required.md"
)
TASK_TRACKING_RULE_PATH: Path = (
    REPOSITORY_ROOT
    / "packages"
    / "claude-dev-env"
    / "rules"
    / "workers-done-before-complete.md"
)
CLEAN_CODER_PATH: Path = (
    REPOSITORY_ROOT
    / "packages"
    / "claude-dev-env"
    / "agents"
    / "clean-coder.md"
)
SYNC_SCRIPT_PATH: Path = REPOSITORY_ROOT / ".github" / "scripts" / "sync_ai_rules.py"

TYPE_IGNORE_JUSTIFICATION_TOKEN: str = "≥5 characters of justification"
TYPE_IGNORE_FIVE_CHAR_TOKEN: str = "five characters"
CONSTANT_LOCATION_TOKEN: str = "config/"
ENFORCER_TABLE_CHECK_PATTERN: re.Pattern[str] = re.compile(
    r"code_rules_enforcer\.py::(check_[a-z0-9_]+)"
)
MINIMUM_ENFORCER_TABLE_CHECKS: int = 1


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _load_enforcer_module() -> object:
    blocking_dir = ENFORCER_PATH.parent
    hooks_dir = blocking_dir.parent
    package_root = hooks_dir.parent
    for each_path in (str(package_root), str(hooks_dir), str(blocking_dir)):
        if each_path not in sys.path:
            sys.path.insert(0, each_path)
    module_spec = importlib.util.spec_from_file_location(
        "code_rules_enforcer_under_test",
        ENFORCER_PATH,
    )
    assert module_spec is not None
    assert module_spec.loader is not None
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    return module


def test_code_standards_names_three_policy_layers() -> None:
    standards_text = _read_text(CODE_STANDARDS_PATH)
    assert "AGENTS.md" in standards_text
    assert "canonical" in standards_text.lower()
    assert "CODE_RULES.md" in standards_text
    assert "projection" in standards_text.lower()
    assert "code_rules_enforcer.py" in standards_text
    assert "hand-maintained" in standards_text.lower()


def test_type_ignore_semantics_agree_across_projections() -> None:
    agents_text = _read_text(AGENTS_PATH)
    code_rules_text = _read_text(CODE_RULES_PATH)
    assert TYPE_IGNORE_JUSTIFICATION_TOKEN in agents_text
    assert (
        TYPE_IGNORE_FIVE_CHAR_TOKEN in code_rules_text
        or TYPE_IGNORE_JUSTIFICATION_TOKEN in code_rules_text
    )
    assert "type: ignore" in code_rules_text
    bare_ignore_source = "x = 1  # type: ignore\n"
    justified_ignore_source = (
        "x = 1  # type: ignore[misc]  # stubs missing in foo library\n"
    )
    enforcer = _load_enforcer_module()
    validate_content = getattr(enforcer, "validate_content", None)
    assert callable(validate_content)
    bare_issues = validate_content(bare_ignore_source, "sample.py")
    justified_issues = validate_content(justified_ignore_source, "sample.py")
    assert any("type: ignore" in str(each_issue).lower() for each_issue in bare_issues)
    assert not any(
        "type: ignore" in str(each_issue).lower() for each_issue in justified_issues
    )


def test_constant_location_semantics_agree_across_projections() -> None:
    agents_text = _read_text(AGENTS_PATH)
    code_rules_text = _read_text(CODE_RULES_PATH)
    assert CONSTANT_LOCATION_TOKEN in agents_text
    assert "UPPER_SNAKE" in agents_text or "UPPER_SNAKE_CASE" in agents_text
    assert CONSTANT_LOCATION_TOKEN in code_rules_text
    assert "config/" in code_rules_text


def test_agents_hook_table_check_names_exist_on_enforcer() -> None:
    agents_text = _read_text(AGENTS_PATH)
    all_check_names = ENFORCER_TABLE_CHECK_PATTERN.findall(agents_text)
    assert len(all_check_names) >= MINIMUM_ENFORCER_TABLE_CHECKS
    enforcer = _load_enforcer_module()
    missing_names = [
        each_name
        for each_name in all_check_names
        if not callable(getattr(enforcer, each_name, None))
    ]
    assert missing_names == [], (
        "AGENTS.md names enforcer checks that are not callables: "
        + ", ".join(missing_names)
    )


def test_question_routing_and_task_tracking_rule_files_exist() -> None:
    assert QUESTION_ROUTING_RULE_PATH.is_file()
    assert TASK_TRACKING_RULE_PATH.is_file()
    question_text = _read_text(QUESTION_ROUTING_RULE_PATH)
    task_text = _read_text(TASK_TRACKING_RULE_PATH)
    assert "AskUserQuestion" in question_text
    assert "workers" in task_text.lower() or "completed" in task_text.lower()
    standards_text = _read_text(CODE_STANDARDS_PATH)
    assert "ask-user-question-required.md" in standards_text
    assert "workers-done-before-complete.md" in standards_text


def test_clean_coder_does_not_instruct_reading_dotenv() -> None:
    clean_coder_text = _read_text(CLEAN_CODER_PATH)
    assert "AGENTS.md" in clean_coder_text or "canonical" in clean_coder_text.lower()
    has_dotenv_ban = (
        "Never open `.env`" in clean_coder_text
        or "Do **not** glob or open `.env`" in clean_coder_text
    )
    assert has_dotenv_ban
    assert "`**/.env`" not in clean_coder_text
    assert "`**/.env.*`" not in clean_coder_text


def test_sync_ai_rules_check_exits_zero() -> None:
    completed = subprocess.run(
        [sys.executable, str(SYNC_SCRIPT_PATH), "--check"],
        cwd=str(REPOSITORY_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, (
        f"stdout={completed.stdout!r} stderr={completed.stderr!r}"
    )
