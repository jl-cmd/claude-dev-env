"""Link-integrity check for every installer-owned Markdown root.

Walks every markdown file under the package roots the installer ships
(``skills/``, ``rules/``, ``agents/``, ``commands/``, ``docs/``,
``system-prompts/``, ``audit-rubrics/``, ``_shared/``) and resolves each
relative markdown link target against the linking file's directory. A link
whose target file or directory does not exist on disk is reported with its
source file and line number, and the test fails.

External URLs, anchors, absolute paths, and placeholders stay outside this
deterministic check.
"""

from __future__ import annotations

import re
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parent.parent

INSTALLER_MARKDOWN_ROOTS: tuple[Path, ...] = (
    PACKAGE_ROOT / "skills",
    PACKAGE_ROOT / "rules",
    PACKAGE_ROOT / "agents",
    PACKAGE_ROOT / "commands",
    PACKAGE_ROOT / "docs",
    PACKAGE_ROOT / "system-prompts",
    PACKAGE_ROOT / "audit-rubrics",
    PACKAGE_ROOT / "_shared",
)

MARKDOWN_LINK_PATTERN = re.compile(r"\]\(([^)\s]+)\)")
FENCE_MARKER = "```"

SKIPPED_TARGET_PREFIXES = (
    "http://",
    "https://",
    "mailto:",
    "#",
    "/",
    "$",
    "~",
    "<",
)


def _iter_markdown_files() -> list[Path]:
    """List every markdown file under installer-owned roots.

    Returns:
        All ``.md`` files under each existing installer Markdown root.
    """
    all_markdown_files: list[Path] = []
    for each_root in INSTALLER_MARKDOWN_ROOTS:
        if not each_root.is_dir():
            continue
        all_markdown_files.extend(sorted(each_root.rglob("*.md")))
    return all_markdown_files


def _is_checkable_target(link_target: str) -> bool:
    """Decide whether a markdown link target names a local relative path.

    Args:
        link_target: The raw text between ``](`` and ``)`` in a markdown link.

    Returns:
        True when the target is a relative filesystem path this check can
        resolve; False for URLs, anchors, absolute paths, environment-variable
        paths, home-relative paths, and angle-bracket placeholders.
    """
    if link_target.startswith(SKIPPED_TARGET_PREFIXES):
        return False
    if "\\" in link_target and link_target.count(":") > 0:
        return False
    return True


def _collect_broken_links(markdown_path: Path) -> list[str]:
    """Resolve every relative link in one markdown file.

    Fenced code blocks are skipped, and a ``#fragment`` suffix is stripped
    before resolution.

    Args:
        markdown_path: The markdown file whose links are resolved.

    Returns:
        One ``file:line -> target`` description per unresolvable link.
    """
    all_broken_links: list[str] = []
    is_inside_fence = False
    for line_number, each_line in enumerate(
        markdown_path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if each_line.lstrip().startswith(FENCE_MARKER):
            is_inside_fence = not is_inside_fence
            continue
        if is_inside_fence:
            continue
        for each_match in MARKDOWN_LINK_PATTERN.finditer(each_line):
            link_target = each_match.group(1).split("#", 1)[0]
            if not link_target or not _is_checkable_target(link_target):
                continue
            resolved_target = (markdown_path.parent / link_target).resolve()
            if not resolved_target.exists():
                all_broken_links.append(
                    f"{markdown_path}:{line_number} -> {each_match.group(1)}"
                )
    return all_broken_links


def test_every_relative_markdown_link_resolves() -> None:
    all_broken_links: list[str] = []
    for each_markdown_path in _iter_markdown_files():
        all_broken_links.extend(_collect_broken_links(each_markdown_path))
    broken_link_report = "\n".join(all_broken_links)
    assert not all_broken_links, (
        f"Unresolvable relative markdown links:\n{broken_link_report}"
    )


def test_installer_markdown_roots_include_rules() -> None:
    rules_root = PACKAGE_ROOT / "rules"
    assert rules_root in INSTALLER_MARKDOWN_ROOTS
    assert rules_root.is_dir()
    all_paths = _iter_markdown_files()
    assert any(each_path.is_relative_to(rules_root) for each_path in all_paths)


def test_eli11_shell_invocation_link_resolves() -> None:
    eli11_path = PACKAGE_ROOT / "rules" / "eli11-replies.md"
    shell_path = PACKAGE_ROOT / "rules" / "shell-invocation.md"
    assert shell_path.is_file()
    broken = _collect_broken_links(eli11_path)
    assert not any("shell-invocation" in each for each in broken), broken
