"""Resolution check for relative paths written as inline code rather than links.

``test_markdown_link_integrity`` resolves markdown link targets — the text
between ``](`` and ``)``. A skill doc names most of its neighbours a second way,
as a backticked path in prose, and that shape carries no link syntax for the
link check to find. A relocation that shifts a directory's depth leaves those
references pointing one level off, and nothing fails::

    ok:   `../../_shared/pr-loop/worker-spawn.md`   resolves to a file on disk
    flag: `../_shared/pr-loop/worker-spawn.md`     one level short after the move

This check walks every markdown file the package holds — a wider set than the
link check, which stays inside ``skills/``. It reads each inline-code span that
names a concrete file (it carries an extension) or a directory (it ends in a
slash), and resolves it against the file's own directory. A span carrying a
placeholder segment or a space is left alone, since it names no file this package
ships. A span whose target is absent is reported with its file and line number.

Fenced code blocks are skipped: a fence shows a command a reader runs from some
other working directory, so its paths do not resolve from the doc's directory. A
fence closes only on a backtick run at least as long as the one that opened it,
so a ``` block nested inside a ```` block stays content rather than flipping the
state.
"""

from __future__ import annotations

import re
from pathlib import Path


PACKAGE_ROOT = Path(__file__).parent.parent

INLINE_CODE_PATTERN = re.compile(r"`([^`\n]+)`")
RELATIVE_PATH_PREFIXES = ("./", "../")
FENCE_MARKER = "```"
PLACEHOLDER_MARKERS = ("<", ">", "*", "…", "{", "}")
TRAILING_PUNCTUATION = ",.;:)"
DIRECTORIES_TO_SKIP = frozenset(
    {
        ".git",
        "__pycache__",
        "node_modules",
        ".venv",
        "venv",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
    }
)
EGG_INFO_DIRECTORY_SUFFIX = ".egg-info"


def _iter_markdown_files() -> list[Path]:
    """List every markdown file this check covers.

    Version-control, dependency, and build-artifact trees are left out, so an
    installed dependency's own README never turns this check red::

        read: skills/pr-converge/SKILL.md
        skip: node_modules/some-package/README.md
        skip: claude_dev_env.egg-info/PKG-INFO.md

    Returns:
        Every ``.md`` file under the package directory outside those trees, so a
        reference that crosses from one top-level tree into another is resolved
        from both ends.
    """
    return sorted(
        each_markdown_path
        for each_markdown_path in PACKAGE_ROOT.rglob("*.md")
        if not _is_skipped_path(each_markdown_path.relative_to(PACKAGE_ROOT))
    )


def _is_skipped_path(relative_path: Path) -> bool:
    """Decide whether a path sits inside a tree this check leaves alone.

    ::

        skills/pr-converge/SKILL.md      -> False
        node_modules/dep/README.md       -> True
        claude_dev_env.egg-info/PKG.md   -> True

    Args:
        relative_path: A markdown path taken relative to the package root.

    Returns:
        True when any segment names a skipped directory or an egg-info tree.
    """
    return any(
        each_part in DIRECTORIES_TO_SKIP
        or each_part.endswith(EGG_INFO_DIRECTORY_SUFFIX)
        for each_part in relative_path.parts
    )


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


def _leading_fence_length(line_text: str) -> int:
    """Count the backticks opening or closing a fence on one line.

    ::

        "```python"   -> 3
        "````"        -> 4
        "a `path` b"  -> 0

    Args:
        line_text: One raw line of a markdown file.

    Returns:
        The run length when the line starts a fence, and 0 otherwise.
    """
    stripped_line = line_text.lstrip()
    fence_run_length = len(stripped_line) - len(stripped_line.lstrip(FENCE_MARKER[0]))
    return fence_run_length if fence_run_length >= len(FENCE_MARKER) else 0


def _fence_length_after(fence_run_length: int, open_fence_length: int) -> int:
    """Track which fence is open, so a nested fence never inverts the state.

    ::

        open 4, sees 3  -> 4   the inner fence is content, not a close
        open 4, sees 4  -> 0   a run this long or longer closes it
        open 0, sees 3  -> 3   a fence opens

    Args:
        fence_run_length: Backticks opening this line, or 0 when it is prose.
        open_fence_length: Backticks that opened the fence now standing open.

    Returns:
        The open fence length after reading the line.
    """
    if fence_run_length == 0:
        return open_fence_length
    if open_fence_length == 0:
        return fence_run_length
    return 0 if fence_run_length >= open_fence_length else open_fence_length


def _broken_references_in_line(markdown_path: Path, line_text: str) -> list[str]:
    """Resolve each inline-code relative path on one line of prose.

    Args:
        markdown_path: The markdown file the line belongs to.
        line_text: One line sitting outside every fence.

    Returns:
        The span text of each reference naming a path absent from disk.
    """
    all_broken_spans: list[str] = []
    for each_match in INLINE_CODE_PATTERN.finditer(line_text):
        span_text = each_match.group(1).strip()
        reference_path = span_text.split("#", 1)[0].rstrip(TRAILING_PUNCTUATION)
        if not _is_resolvable_reference(reference_path):
            continue
        if not (markdown_path.parent / reference_path).resolve().exists():
            all_broken_spans.append(span_text)
    return all_broken_spans


def _collect_broken_references(markdown_path: Path) -> list[str]:
    """Resolve every inline-code relative path in one markdown file.

    Args:
        markdown_path: The markdown file whose references are resolved.

    Returns:
        One ``file:line -> reference`` description per unresolvable reference.
    """
    all_broken_references: list[str] = []
    open_fence_length = 0
    for line_number, each_line in enumerate(
        markdown_path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        fence_run_length = _leading_fence_length(each_line)
        open_fence_length = _fence_length_after(fence_run_length, open_fence_length)
        if fence_run_length or open_fence_length:
            continue
        for each_span in _broken_references_in_line(markdown_path, each_line):
            all_broken_references.append(f"{markdown_path}:{line_number} -> {each_span}")
    return all_broken_references


def test_should_skip_a_reference_inside_a_plain_fence(tmp_path: Path) -> None:
    markdown_path = tmp_path / "doc.md"
    markdown_path.write_text(
        "```\nrun `./absent-from-disk.md` here\n```\n", encoding="utf-8"
    )

    assert _collect_broken_references(markdown_path) == []


def test_should_skip_a_reference_inside_a_fence_nested_in_a_longer_fence(
    tmp_path: Path,
) -> None:
    markdown_path = tmp_path / "doc.md"
    markdown_path.write_text(
        "````markdown\n```text\nsee `./absent-from-disk.md`\n```\nstill fenced\n````\n",
        encoding="utf-8",
    )

    assert _collect_broken_references(markdown_path) == []


def test_should_report_a_broken_reference_sitting_in_prose(tmp_path: Path) -> None:
    markdown_path = tmp_path / "doc.md"
    markdown_path.write_text("see `./absent-from-disk.md` here\n", encoding="utf-8")

    all_broken_references = _collect_broken_references(markdown_path)

    assert len(all_broken_references) == 1
    assert "./absent-from-disk.md" in all_broken_references[0]


def test_should_report_a_broken_reference_closing_a_sentence(tmp_path: Path) -> None:
    markdown_path = tmp_path / "doc.md"
    markdown_path.write_text("named in `./absent-from-disk.md`.\n", encoding="utf-8")

    assert len(_collect_broken_references(markdown_path)) == 1


def test_should_resolve_a_reference_wrapped_in_parentheses(tmp_path: Path) -> None:
    (tmp_path / "neighbour.md").write_text("x\n", encoding="utf-8")
    markdown_path = tmp_path / "doc.md"
    markdown_path.write_text("(see `./neighbour.md`)\n", encoding="utf-8")

    assert _collect_broken_references(markdown_path) == []


def test_should_leave_a_dependency_readme_out_of_the_walk() -> None:
    assert _is_skipped_path(Path("node_modules/dep/README.md")) is True
    assert _is_skipped_path(Path("claude_dev_env.egg-info/PKG-INFO.md")) is True
    assert _is_skipped_path(Path("skills/pr-converge/SKILL.md")) is False


def test_every_inline_code_relative_reference_resolves() -> None:
    all_broken_references: list[str] = []
    for each_markdown_path in _iter_markdown_files():
        all_broken_references.extend(_collect_broken_references(each_markdown_path))
    broken_reference_report = "\n".join(all_broken_references)
    assert not all_broken_references, (
        f"Unresolvable relative references written as inline code:\n"
        f"{broken_reference_report}"
    )
