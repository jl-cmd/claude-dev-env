"""Resolution check for relative paths written as inline code rather than links.

``test_markdown_link_integrity`` resolves markdown link targets — the text
between ``](`` and ``)``. A skill doc names most of its neighbours a second way,
as a backticked path in prose, and that shape carries no link syntax for the
link check to find. A relocation that shifts a directory's depth leaves those
references pointing one level off, and nothing fails::

    ok:   `../_shared/pr-loop/worker-spawn.md`   resolves to a file on disk
    flag: `../_shared/pr-loop/worker-spawn.md`   after the tree moved one level

This check walks the same markdown files, reads every inline-code span holding a
``./`` or ``../`` path, and resolves it against the file's own directory. A span
whose target is absent is reported with its file and line number.

Fenced code blocks are skipped: a fence shows a command a reader runs from some
other working directory, so its paths do not resolve from the doc's directory.
"""

from __future__ import annotations

import re
from pathlib import Path


PACKAGE_ROOT = Path(__file__).parent.parent

INLINE_CODE_PATTERN = re.compile(r"`([^`\n]+)`")
RELATIVE_PATH_PREFIXES = ("./", "../")
FENCE_MARKER = "```"
PLACEHOLDER_MARKERS = ("<", ">", "*", "…", "{", "}")
TRAILING_PUNCTUATION = ",.;:"


def _iter_markdown_files() -> list[Path]:
    """List every markdown file this check covers.

    Returns:
        Every ``.md`` file the package ships, so a reference that crosses from
        one top-level tree into another is resolved from both ends.
    """
    return sorted(PACKAGE_ROOT.rglob("*.md"))


def _is_resolvable_reference(span_text: str) -> bool:
    """Decide whether one inline-code span names a path this check can resolve.

    Args:
        span_text: The text between a pair of backticks.

    Returns:
        True when the span names a concrete file (it carries an extension) or a
        directory (it ends in a slash); False for prose, for a path carrying a
        placeholder segment, for a shell command, and for an extensionless
        literal such as the ``../../etc/passwd`` payload a security rubric
        quotes, which names no file this package ships.
    """
    if not span_text.startswith(RELATIVE_PATH_PREFIXES):
        return False
    if any(each_marker in span_text for each_marker in PLACEHOLDER_MARKERS):
        return False
    if " " in span_text:
        return False
    return span_text.endswith("/") or bool(Path(span_text).suffix)


def _collect_broken_references(markdown_path: Path) -> list[str]:
    """Resolve every inline-code relative path in one markdown file.

    Args:
        markdown_path: The markdown file whose references are resolved.

    Returns:
        One ``file:line -> reference`` description per unresolvable reference.
    """
    all_broken_references: list[str] = []
    is_inside_fence = False
    for line_number, each_line in enumerate(
        markdown_path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if each_line.lstrip().startswith(FENCE_MARKER):
            is_inside_fence = not is_inside_fence
            continue
        if is_inside_fence:
            continue
        for each_match in INLINE_CODE_PATTERN.finditer(each_line):
            span_text = each_match.group(1).strip()
            if not _is_resolvable_reference(span_text):
                continue
            reference_path = span_text.split("#", 1)[0].rstrip(TRAILING_PUNCTUATION)
            if not (markdown_path.parent / reference_path).resolve().exists():
                all_broken_references.append(
                    f"{markdown_path}:{line_number} -> {span_text}"
                )
    return all_broken_references


def test_every_inline_code_relative_reference_resolves() -> None:
    all_broken_references: list[str] = []
    for each_markdown_path in _iter_markdown_files():
        all_broken_references.extend(_collect_broken_references(each_markdown_path))
    broken_reference_report = "\n".join(all_broken_references)
    assert not all_broken_references, (
        f"Unresolvable relative references written as inline code:\n"
        f"{broken_reference_report}"
    )
