"""Keep an arm's sessions on the arm's own install instead of the live home.

::

    before:  python ~/.claude/scripts/gate.py          -> the owner's live copy
    after:   python <run>/work/.claude/scripts/gate.py -> the arm's copy, or nothing

Three parts work together. The rewrite edits installed text. The home link
gives child Pythons an arm home to find. The tripwire reads the transcript and
names every tool call that still reached for the live home.
"""

from __future__ import annotations

import os
import re
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

HOME_FORM_PATTERN = r"(?:~|\$\{HOME\}|\$HOME|%USERPROFILE%|\$env:USERPROFILE)"
NAME_END_PATTERN = r"(?![\w\-]|\.\w)"
REWRITE_EXPRESSION = re.compile(
    HOME_FORM_PATTERN + r"[/\\]\.(claude|agents)" + NAME_END_PATTERN, re.IGNORECASE
)
PYTHON_REDIRECT_DIRECTORY = Path(__file__).resolve().parent / "pyredirect"
ALL_LINKED_HOME_NAMES = (".claude", ".agents")


@dataclass(frozen=True)
class RewriteReport:
    replacement_count: int
    changed_file_count: int
    scanned_file_count: int


def _walk_files(root: Path) -> list[Path]:
    return [
        Path(each_directory) / each_name
        for each_directory, _, all_names in os.walk(root, followlinks=False)
        for each_name in all_names
    ]


def rewrite_live_home_references(
    all_roots: list[Path], config_directory: Path
) -> RewriteReport:
    """Replace each spelled-out live-home config path in installed text.

    ::

        ~/.claude/rules/a.md            -> <config>/rules/a.md
        %USERPROFILE%\\.claude\\x.ps1     -> <config>\\x.ps1
        $HOME/.agents/skills            -> <config>/../.agents/skills
        ok:   ~/.claude.json, ~/.claudette, ./.claude/settings.json stay as written

    Files that do not decode as UTF-8 are left byte for byte.
    """
    replacement_by_name = {
        "claude": config_directory.as_posix(),
        "agents": (config_directory.parent / ".agents").as_posix(),
    }
    replacement_count = 0
    changed_file_count = 0
    scanned_file_count = 0
    for each_root in all_roots:
        for each_path in _walk_files(each_root):
            try:
                original = each_path.read_bytes().decode("utf-8")
            except UnicodeDecodeError:
                continue
            scanned_file_count += 1
            rewritten, hit_count = REWRITE_EXPRESSION.subn(
                lambda each_match: replacement_by_name[each_match.group(1).lower()],
                original,
            )
            if hit_count:
                each_path.write_bytes(rewritten.encode("utf-8"))
                replacement_count += hit_count
                changed_file_count += 1
    return RewriteReport(replacement_count, changed_file_count, scanned_file_count)


def _make_directory_link(link_path: Path, target: Path) -> None:
    if sys.platform == "win32":
        import _winapi

        _winapi.CreateJunction(str(target), str(link_path))
    else:
        link_path.symlink_to(target, target_is_directory=True)


def link_arm_home(home_directory: Path, work_directory: Path) -> list[str]:
    """Make ``<home>/.claude`` and ``<home>/.agents`` open the arm's install."""
    all_linked: list[str] = []
    for each_name in ALL_LINKED_HOME_NAMES:
        target = work_directory / each_name
        link_path = home_directory / each_name
        if target.is_dir() and not link_path.exists():
            _make_directory_link(link_path, target)
            all_linked.append(each_name)
    return all_linked


def redirect_environment(
    home_directory: Path, config_directory: Path
) -> dict[str, str]:
    """Return the variables that send child processes to the arm's install.

    The redirect module is copied into the run directory first, so the path a
    session sees never points into the repository checkout.
    """
    inherited = os.environ.get("PYTHONPATH", "")
    run_redirect_directory = home_directory.parent / "pyredirect"
    run_redirect_directory.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(
        PYTHON_REDIRECT_DIRECTORY / "sitecustomize.py",
        run_redirect_directory / "sitecustomize.py",
    )
    return {
        "BENCH_ARM_HOME": str(home_directory),
        "CLAUDE_HOME": str(config_directory),
        "PYTHONPATH": str(run_redirect_directory)
        + (os.pathsep + inherited if inherited else ""),
    }


def _live_home_expression() -> re.Pattern[str]:
    live_config = (Path.home() / ".claude").as_posix().lower()
    drive, tail = live_config[0], live_config[2:]
    all_forms = [
        re.escape(live_config),
        re.escape(f"/{drive}{tail}"),
        re.escape(f"/mnt/{drive}{tail}"),
        HOME_FORM_PATTERN.lower() + r"/\.claude",
    ]
    return re.compile("(?:" + "|".join(all_forms) + ")" + NAME_END_PATTERN)


def _all_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [
            each for each_item in value.values() for each in _all_strings(each_item)
        ]
    if isinstance(value, list):
        return [each for each_item in value for each in _all_strings(each_item)]
    return []


def find_live_home_tool_calls(all_events: list[dict[str, Any]]) -> list[str]:
    """Name each tool call whose input points under the live config home.

    ::

        flag: Read  C:\\Users\\me\\.claude\\rules\\a.md
        flag: Bash  cat ~/.claude/rules/a.md
        ok:   Read  <run>\\work\\.claude\\rules\\a.md
        ok:   Bash  cat ~/.claude.json

    Only the model's own tool inputs are read. Text inside tool results is not.
    """
    expression = _live_home_expression()
    all_found: list[str] = []
    for each_event in all_events:
        if each_event.get("type") != "assistant":
            continue
        message = each_event.get("message")
        all_blocks = message.get("content", []) if isinstance(message, dict) else []
        for each_block in all_blocks:
            if not isinstance(each_block, dict) or each_block.get("type") != "tool_use":
                continue
            for each_text in _all_strings(each_block.get("input")):
                normalized = each_text.replace("\\", "/").lower()
                if expression.search(normalized):
                    all_found.append(f"{each_block.get('name')}: {each_text[:200]}")
                    break
    return all_found


ALL_FILE_WRITING_TOOLS = ("Write", "Edit", "MultiEdit", "NotebookEdit")
ALL_SHELL_TOOLS = ("Bash", "PowerShell")
MUTATING_VERB_EXPRESSION = re.compile(
    r"(?<![\w./-])(?:rm|rmdir|mv|cp|del|erase|rd|move|copy|touch|mkdir|tee|truncate|dd|ln"
    r"|chmod|unlink|remove-item|move-item|copy-item|rename-item|set-content|add-content"
    r"|out-file|new-item|clear-content|ri|mi|ni|shutil\.\w+|os\.remove|git\s+clean|sed\s+-i)"
    r"(?![\w.-])"
)
PATH_TOKEN_PATTERN = (
    r"(?:[a-z]:/|/[a-z0-9_.-]+/|~/|\$\{?home\}?/|\$env:\w+/|%\w+%/|\$\{?temp\}?/|(?:\.\./){2,})"
    r"[^\s\"'|;&<>)]*"
)
PATH_TOKEN_EXPRESSION = re.compile(r"(?<![\w.:/$-])" + PATH_TOKEN_PATTERN)
REDIRECT_TARGET_EXPRESSION = re.compile(r">>?\s*[\"']?(" + PATH_TOKEN_PATTERN + ")")
ALL_HARMLESS_TARGETS = ("/dev/null", "/dev/stdout", "/dev/stderr")
ALL_RUN_TEMP_VARIABLE_FORMS = (
    "$temp/",
    "${temp}/",
    "$tmp/",
    "$tmpdir/",
    "$env:temp/",
    "$env:tmp/",
    "%temp%/",
    "%tmp%/",
)


def _is_outside(token: str, run_root: Path) -> bool:
    inside = run_root.as_posix().lower()
    all_inside_forms = [inside, f"/{inside[0]}{inside[2:]}", f"/mnt/{inside[0]}{inside[2:]}"]
    temp_root = Path(tempfile.gettempdir()).as_posix().lower()
    if inside.startswith(temp_root + "/"):
        all_inside_forms.append("/tmp" + inside[len(temp_root) :])
    if token.startswith(ALL_HARMLESS_TARGETS) or token.endswith(".exe"):
        return False
    all_scratch_forms = ("/tmp", temp_root, f"/{temp_root[0]}{temp_root[2:]}")
    if token.startswith(ALL_RUN_TEMP_VARIABLE_FORMS):
        return False
    for each_form in all_scratch_forms:
        if token.startswith(each_form + "/") and not token.startswith(
            each_form + "/cde-bench"
        ):
            return False
    return not any(
        token == each_form or token.startswith(each_form + "/")
        for each_form in all_inside_forms
    )


def _outside_shell_target(command: str, run_root: Path) -> str | None:
    normalized = command.replace("\\", "/").lower()
    all_redirect_targets = REDIRECT_TARGET_EXPRESSION.findall(normalized)
    all_candidates = (
        PATH_TOKEN_EXPRESSION.findall(normalized)
        if MUTATING_VERB_EXPRESSION.search(normalized)
        else all_redirect_targets
    )
    for each_token in all_candidates:
        if _is_outside(each_token, run_root):
            return each_token
    return None


def find_outside_writes(
    all_events: list[dict[str, Any]],
    run_root: Path,
    all_denied_tool_use_ids: frozenset[str] = frozenset(),
) -> list[str]:
    """Name each write, delete, or move aimed outside the run's own directory.

    ::

        flag: Write       C:/Users/me/projects/app/a.txt
        flag: PowerShell  Remove-Item -Recurse 'C:/Users/me/projects/app/build'
        flag: Bash        rm -rf ../../other-run
        ok:   Bash        rm -rf build            (relative, stays in the work directory)
        ok:   Bash        cat C:/Users/me/projects/app/log.txt   (a read)

    A file tool counts when its absolute path leaves the run directory. A shell
    command counts when it holds a changing verb plus an outside path, or when
    it redirects output to an outside path. A call the CLI denied never ran,
    so it is skipped. The OS temp root, also spelled ``/tmp/``, is allowed as
    scratch, except its ``cde-bench`` tree that holds other runs. A path through
    a temp variable is inside, because the session's temp variables point into
    the run directory.
    """
    all_found: list[str] = []
    for each_event in all_events:
        if each_event.get("type") != "assistant":
            continue
        message = each_event.get("message")
        all_blocks = message.get("content", []) if isinstance(message, dict) else []
        for each_block in all_blocks:
            if not isinstance(each_block, dict) or each_block.get("type") != "tool_use":
                continue
            tool_name = str(each_block.get("name"))
            tool_input = each_block.get("input")
            if each_block.get("id") in all_denied_tool_use_ids:
                continue
            if not isinstance(tool_input, dict):
                continue
            target: str | None = None
            if tool_name in ALL_FILE_WRITING_TOOLS:
                file_path = str(
                    tool_input.get("file_path") or tool_input.get("notebook_path") or ""
                )
                normalized = file_path.replace("\\", "/").lower()
                if PATH_TOKEN_EXPRESSION.match(normalized) and _is_outside(
                    normalized, run_root
                ):
                    target = file_path
            elif tool_name in ALL_SHELL_TOOLS:
                target = _outside_shell_target(str(tool_input.get("command", "")), run_root)
            if target is not None:
                all_found.append(f"{tool_name}: {target[:200]}")
    return all_found
