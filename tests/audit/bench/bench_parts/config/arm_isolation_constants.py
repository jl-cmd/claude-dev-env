"""Constants the arm-isolation rewrite, home link, and tripwire import.

::

    rewrite   ->   the patterns that match a spelled-out live-home path
    link      ->   the two home directory names the arm links
    redirect  ->   the environment variables a child session inherits
    tripwire  ->   the tool names, verbs, and path forms a finding reads

The path spellings sit together because one Windows directory reaches a
session three ways: a drive letter, a leading slash, and a mount prefix.
"""

from __future__ import annotations

import re

HOME_FORM_PATTERN = r"(?:~|\$\{HOME\}|\$HOME|%USERPROFILE%|\$env:USERPROFILE)"
NAME_END_PATTERN = r"(?![\w\-]|\.\w)"
REWRITE_EXPRESSION = re.compile(
    HOME_FORM_PATTERN + r"[/\\]\.(claude|agents)" + NAME_END_PATTERN, re.IGNORECASE
)
LIVE_CONFIG_HOME_PATTERN = r"/\.claude"

CLAUDE_CONFIG_DIRECTORY_NAME = ".claude"
AGENTS_DIRECTORY_NAME = ".agents"
ALL_LINKED_HOME_NAMES = (CLAUDE_CONFIG_DIRECTORY_NAME, AGENTS_DIRECTORY_NAME)

ARM_HOME_VARIABLE = "BENCH_ARM_HOME"
CONFIG_HOME_VARIABLE = "CLAUDE_HOME"
PYTHON_PATH_VARIABLE = "PYTHONPATH"
REDIRECT_DIRECTORY_NAME = "pyredirect"
REDIRECT_MODULE_NAME = "sitecustomize.py"

MOUNT_PREFIX = "/mnt/"
POSIX_SCRATCH_ROOT = "/tmp"
BENCH_SCRATCH_DIRECTORY_NAME = "cde-bench"
DRIVE_PREFIX_LENGTH = 2
ALTERNATION_SEPARATOR = "|"
DETAIL_CHARACTER_LIMIT = 200
EXECUTABLE_SUFFIX = ".exe"

ALL_FILE_WRITING_TOOLS = ("Write", "Edit", "MultiEdit", "NotebookEdit")
ALL_SHELL_TOOLS = ("Bash", "PowerShell")
MUTATING_VERB_EXPRESSION = re.compile(
    r"(?<![\w./-])(?:rm|rmdir|mv|cp|del|erase|rd|move|copy|touch|mkdir|tee|truncate|dd|ln"
    r"|chmod|unlink|remove-item|move-item|copy-item|rename-item|set-content|add-content"
    r"|out-file|new-item|clear-content|ri|mi|ni|shutil\.\w+|os\.remove|git\s+clean|sed\s+-i)"
    r"(?![\w.-])"
)
PATH_SEGMENT_PATTERN = (
    r"(?:[a-z]:/|/[a-z0-9_.-]+/|~/|\$\{?home\}?/|\$env:\w+/|%\w+%/|\$\{?temp\}?/|(?:\.\./){2,})"
    r"[^\s\"'|;&<>)]*"
)
PATH_SEGMENT_EXPRESSION = re.compile(r"(?<![\w.:/$-])" + PATH_SEGMENT_PATTERN)
REDIRECT_TARGET_EXPRESSION = re.compile(r">>?\s*[\"']?(" + PATH_SEGMENT_PATTERN + ")")
ALL_HARMLESS_TARGETS = ("/dev/null", "/dev/stdout", "/dev/stderr")
ALL_RUN_SCRATCH_VARIABLE_FORMS = (
    "$temp/",
    "${temp}/",
    "$tmp/",
    "$tmpdir/",
    "$env:temp/",
    "$env:tmp/",
    "%temp%/",
    "%tmp%/",
)
