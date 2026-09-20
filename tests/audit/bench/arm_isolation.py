"""Keep an arm's sessions on the arm's own install.

::

    python <run>/work/.claude/scripts/gate.py   ->   the arm's own copy
    python ~/.claude/scripts/gate.py            ->   the tripwire names it

Three parts work together. The rewrite edits installed text. The home link
gives child Pythons an arm home to find. The tripwire reads the transcript and
names every tool call that reached for the live home.
"""

from __future__ import annotations

import os
import re
import shutil
import sys
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from config.arm_isolation_constants import (
    AGENTS_DIRECTORY_NAME,
    ALL_FILE_WRITING_TOOLS,
    ALL_HARMLESS_TARGETS,
    ALL_LINKED_HOME_NAMES,
    ALL_RUN_SCRATCH_VARIABLE_FORMS,
    ALL_SHELL_TOOLS,
    ALTERNATION_SEPARATOR,
    ARM_HOME_VARIABLE,
    BENCH_SCRATCH_DIRECTORY_NAME,
    CLAUDE_CONFIG_DIRECTORY_NAME,
    CONFIG_HOME_VARIABLE,
    DETAIL_CHARACTER_LIMIT,
    DRIVE_PREFIX_LENGTH,
    EXECUTABLE_SUFFIX,
    HOME_FORM_PATTERN,
    LIVE_CONFIG_HOME_PATTERN,
    MOUNT_PREFIX,
    MUTATING_VERB_EXPRESSION,
    NAME_END_PATTERN,
    PATH_SEGMENT_EXPRESSION,
    POSIX_SCRATCH_ROOT,
    PYTHON_PATH_VARIABLE,
    REDIRECT_DIRECTORY_NAME,
    REDIRECT_MODULE_NAME,
    REDIRECT_TARGET_EXPRESSION,
    REWRITE_EXPRESSION,
)

if sys.platform == "win32":
    import _winapi

TranscriptEvent = Mapping[str, object]


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


def _rewrite_one_file(text_path: Path, replacement_by_name: Mapping[str, str]) -> int | None:
    """Rewrite one file's live-home paths and say how many it carried.

    ::

        a.md holding '~/.claude/rules/a.md'   ->   1, and the file is written
        a.md holding no live-home path        ->   0, and the file is left
        an image that fails to decode         ->   None

    Args:
        text_path: The file to read, rewrite, and write back.
        replacement_by_name: The replacement path for each config name.

    Returns:
        The number of replacements, or None when the bytes are not UTF-8.
    """
    try:
        original = text_path.read_bytes().decode("utf-8")
    except UnicodeDecodeError:
        return None
    rewritten, hit_count = REWRITE_EXPRESSION.subn(
        lambda each_match: replacement_by_name[each_match.group(1).lower()],
        original,
    )
    if hit_count:
        text_path.write_bytes(rewritten.encode("utf-8"))
    return hit_count


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

    Args:
        all_roots: The installed trees to walk.
        config_directory: The arm's own config directory.

    Returns:
        A RewriteReport counting replacements, changed files, and scanned files.
    """
    replacement_by_name = {
        "claude": config_directory.as_posix(),
        "agents": (config_directory.parent / AGENTS_DIRECTORY_NAME).as_posix(),
    }
    all_paths = [
        each_path for each_root in all_roots for each_path in _walk_files(each_root)
    ]
    replacement_count = 0
    changed_file_count = 0
    scanned_file_count = 0
    for each_path in all_paths:
        hit_count = _rewrite_one_file(each_path, replacement_by_name)
        if hit_count is None:
            continue
        scanned_file_count += 1
        replacement_count += hit_count
        changed_file_count += 1 if hit_count else 0
    return RewriteReport(replacement_count, changed_file_count, scanned_file_count)


def _make_directory_link(link_path: Path, target: Path) -> None:
    if sys.platform == "win32":
        _winapi.CreateJunction(str(target), str(link_path))
    else:
        link_path.symlink_to(target, target_is_directory=True)


def link_arm_home(home_directory: Path, work_directory: Path) -> list[str]:
    """Make ``<home>/.claude`` and ``<home>/.agents`` open the arm's install.

    ::

        work holds .claude, home holds neither   ->   ['.claude']
        home already holds .claude               ->   []

    Args:
        home_directory: The arm's home directory, where the links are made.
        work_directory: The arm's install, where the links point.

    Returns:
        The names that gained a link on this call.
    """
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

    Args:
        home_directory: The arm's home directory.
        config_directory: The arm's own config directory.

    Returns:
        The environment variables a child process inherits.
    """
    inherited = os.environ.get(PYTHON_PATH_VARIABLE, "")
    run_redirect_directory = home_directory.parent / REDIRECT_DIRECTORY_NAME
    run_redirect_directory.mkdir(parents=True, exist_ok=True)
    source_directory = Path(__file__).resolve().parent / REDIRECT_DIRECTORY_NAME
    shutil.copyfile(
        source_directory / REDIRECT_MODULE_NAME,
        run_redirect_directory / REDIRECT_MODULE_NAME,
    )
    return {
        ARM_HOME_VARIABLE: str(home_directory),
        CONFIG_HOME_VARIABLE: str(config_directory),
        PYTHON_PATH_VARIABLE: str(run_redirect_directory)
        + (os.pathsep + inherited if inherited else ""),
    }


def _drive_letter_forms(posix_path: str) -> list[str]:
    all_forms = [posix_path[0] + posix_path[DRIVE_PREFIX_LENGTH:]]
    return [f"/{all_forms[0]}", MOUNT_PREFIX + all_forms[0]]


def _live_home_expression() -> re.Pattern[str]:
    live_config = (Path.home() / CLAUDE_CONFIG_DIRECTORY_NAME).as_posix().lower()
    all_forms = [
        re.escape(live_config),
        *[re.escape(each_form) for each_form in _drive_letter_forms(live_config)],
        HOME_FORM_PATTERN.lower() + LIVE_CONFIG_HOME_PATTERN,
    ]
    joined = ALTERNATION_SEPARATOR.join(all_forms)
    return re.compile("(?:" + joined + ")" + NAME_END_PATTERN)


def _all_strings(payload: object) -> list[str]:
    if isinstance(payload, str):
        return [payload]
    if isinstance(payload, dict):
        return [
            each_string
            for each_member in payload.values()
            for each_string in _all_strings(each_member)
        ]
    if isinstance(payload, list):
        return [
            each_string
            for each_member in payload
            for each_string in _all_strings(each_member)
        ]
    return []


def _all_tool_use_blocks(all_events: list[TranscriptEvent]) -> list[TranscriptEvent]:
    all_blocks: list[TranscriptEvent] = []
    for each_event in all_events:
        if each_event.get("type") != "assistant":
            continue
        message = each_event.get("message")
        content = message.get("content", []) if isinstance(message, dict) else []
        all_blocks.extend(
            each_block
            for each_block in content
            if isinstance(each_block, dict) and each_block.get("type") == "tool_use"
        )
    return all_blocks


def _live_home_finding(
    block: TranscriptEvent, expression: re.Pattern[str]
) -> str | None:
    for each_text in _all_strings(block.get("input")):
        if expression.search(each_text.replace("\\", "/").lower()):
            return f"{block.get('name')}: {each_text[:DETAIL_CHARACTER_LIMIT]}"
    return None


def find_live_home_tool_calls(all_events: list[TranscriptEvent]) -> list[str]:
    """Name each tool call whose input points under the live config home.

    ::

        flag: Read  C:\\Users\\me\\.claude\\rules\\a.md
        flag: Bash  cat ~/.claude/rules/a.md
        ok:   Read  <run>\\work\\.claude\\rules\\a.md
        ok:   Bash  cat ~/.claude.json

    Only the model's own tool inputs are read. Text inside tool results is not.

    Args:
        all_events: The transcript events a session wrote.

    Returns:
        One line per flagged call, naming the tool and the input text.
    """
    expression = _live_home_expression()
    all_found: list[str] = []
    for each_block in _all_tool_use_blocks(all_events):
        finding = _live_home_finding(each_block, expression)
        if finding is not None:
            all_found.append(finding)
    return all_found


def _all_inside_forms(run_root: Path) -> list[str]:
    inside = run_root.as_posix().lower()
    all_forms = [inside, *_drive_letter_forms(inside)]
    scratch_root = Path(tempfile.gettempdir()).as_posix().lower()
    if inside.startswith(scratch_root + "/"):
        all_forms.append(POSIX_SCRATCH_ROOT + inside[len(scratch_root) :])
    return all_forms


def _is_shared_scratch(candidate_path: str) -> bool:
    scratch_root = Path(tempfile.gettempdir()).as_posix().lower()
    all_scratch_forms = (
        POSIX_SCRATCH_ROOT,
        scratch_root,
        _drive_letter_forms(scratch_root)[0],
    )
    return any(
        candidate_path.startswith(each_form + "/")
        and not candidate_path.startswith(
            each_form + "/" + BENCH_SCRATCH_DIRECTORY_NAME
        )
        for each_form in all_scratch_forms
    )


def _is_outside(candidate_path: str, run_root: Path) -> bool:
    if candidate_path.startswith(ALL_HARMLESS_TARGETS) or candidate_path.endswith(
        EXECUTABLE_SUFFIX
    ):
        return False
    if candidate_path.startswith(ALL_RUN_SCRATCH_VARIABLE_FORMS):
        return False
    if _is_shared_scratch(candidate_path):
        return False
    return not any(
        candidate_path == each_form or candidate_path.startswith(each_form + "/")
        for each_form in _all_inside_forms(run_root)
    )


def _outside_shell_target(command: str, run_root: Path) -> str | None:
    normalized = command.replace("\\", "/").lower()
    all_redirect_targets = REDIRECT_TARGET_EXPRESSION.findall(normalized)
    all_candidates = (
        PATH_SEGMENT_EXPRESSION.findall(normalized)
        if MUTATING_VERB_EXPRESSION.search(normalized)
        else all_redirect_targets
    )
    for each_candidate in all_candidates:
        if _is_outside(each_candidate, run_root):
            return each_candidate
    return None


def _outside_file_target(all_tool_input: Mapping[str, object], run_root: Path) -> str | None:
    file_path = str(
        all_tool_input.get("file_path") or all_tool_input.get("notebook_path") or ""
    )
    normalized = file_path.replace("\\", "/").lower()
    if PATH_SEGMENT_EXPRESSION.match(normalized) and _is_outside(normalized, run_root):
        return file_path
    return None


def _outside_write_target(block: TranscriptEvent, run_root: Path) -> str | None:
    tool_name = str(block.get("name"))
    all_tool_input = block.get("input")
    if not isinstance(all_tool_input, dict):
        return None
    if tool_name in ALL_FILE_WRITING_TOOLS:
        return _outside_file_target(all_tool_input, run_root)
    if tool_name in ALL_SHELL_TOOLS:
        return _outside_shell_target(str(all_tool_input.get("command", "")), run_root)
    return None


def find_outside_writes(
    all_events: list[TranscriptEvent],
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

    Args:
        all_events: The transcript events a session wrote.
        run_root: The run directory every write is measured against.
        all_denied_tool_use_ids: The call ids the CLI refused.

    Returns:
        One line per flagged call, naming the tool and the target path.
    """
    all_found: list[str] = []
    for each_block in _all_tool_use_blocks(all_events):
        if each_block.get("id") in all_denied_tool_use_ids:
            continue
        target = _outside_write_target(each_block, run_root)
        if target is not None:
            all_found.append(
                f"{each_block.get('name')}: {target[:DETAIL_CHARACTER_LIMIT]}"
            )
    return all_found
