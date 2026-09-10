"""Detect rules prose that credits a hook module which runs nowhere.

A hook module runs when ``hooks/hooks.json`` registers it or a dispatcher
roster hosts it. A module that survives on disk while appearing in neither
one reaches no tool call, so prose that gives it a present-tense action
describes a gate the reader never faces.
"""

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath

from .config import constants
from .model import Diagnostic, Document, Location, Severity


def accepts_rules_markdown(document: Document) -> bool:
    """Return whether the document is Markdown in a rules directory.

    Args:
        document: Candidate document.

    Returns:
        True for a Markdown file directly under a ``rules`` directory.
    """
    return (
        document.path.suffix.lower() in constants.ALL_MARKDOWN_SUFFIXES
        and document.path.parent.name == constants.RULES_DIRECTORY_NAME
    )


def _package_root(repository_root: Path, document: Document) -> Path:
    return repository_root / document.path.parent.parent.as_posix()


def _read_text(path: Path) -> str:
    if not path.is_file():
        return ""
    return path.read_text(
        encoding="utf-8", errors=constants.REPLACEMENT_CHARACTER_ERRORS
    )


def _registered_hook_stems(hooks_root: Path) -> frozenset[str]:
    all_stems = set(
        re.findall(
            constants.HOOKS_JSON_PATH_PATTERN,
            _read_text(hooks_root / constants.HOOKS_CONFIGURATION_FILE_NAME),
        )
    )
    constants_root = hooks_root / constants.HOOK_CONSTANTS_DIRECTORY_NAME
    if constants_root.is_dir():
        for each_path in sorted(
            constants_root.glob(constants.DISPATCHER_CONSTANTS_GLOB)
        ):
            all_stems.update(
                PurePosixPath(each_relative_path).stem
                for each_relative_path in re.findall(
                    constants.QUOTED_HOOK_PATH_PATTERN, _read_text(each_path)
                )
            )
    return frozenset(all_stems)


def _present_hook_stems(hooks_root: Path) -> frozenset[str]:
    if not hooks_root.is_dir():
        return frozenset()
    return frozenset(
        each_path.stem for each_path in hooks_root.rglob(constants.PYTHON_GLOB)
    )


def _retired_roster_stems(package_root: Path) -> frozenset[str]:
    installer_path = package_root.joinpath(*constants.ALL_INSTALLER_PATH_SEGMENTS)
    maybe_roster = re.search(
        constants.RETIRED_ROSTER_PATTERN, _read_text(installer_path)
    )
    if maybe_roster is None:
        return frozenset()
    return frozenset(
        PurePosixPath(each_relative_path).stem
        for each_relative_path in re.findall(
            constants.QUOTED_HOOK_PATH_PATTERN, maybe_roster.group(1)
        )
    )


def _hook_stem_in_span(span_text: str) -> str | None:
    candidate_name = (
        span_text.strip()
        .rsplit(constants.PATH_SEPARATOR, 1)[-1]
        .removesuffix(constants.PYTHON_SUFFIX)
    )
    if not re.fullmatch(constants.HOOK_MODULE_NAME_PATTERN, candidate_name):
        return None
    if not candidate_name.endswith(constants.ALL_HOOK_MODULE_NAME_SUFFIXES):
        return None
    return candidate_name


def _names_a_live_action(segment_text: str) -> bool:
    return any(
        each_word in constants.ALL_LIVE_CLAIM_VERBS
        for each_word in re.findall(
            constants.PROSE_WORD_PATTERN, segment_text.lower()
        )
    )


def _describes_a_replacement(line_text: str) -> bool:
    normalized_line = line_text.lower()
    return any(
        each_phrase in normalized_line
        for each_phrase in constants.ALL_REPLACEMENT_DELIVERY_PHRASES
    )


def _claim_segment_end(
    line_text: str, all_spans: tuple[re.Match[str], ...], span_index: int
) -> int:
    maybe_sentence_end = re.compile(constants.SENTENCE_BOUNDARY_PATTERN).search(
        line_text, all_spans[span_index].end()
    )
    segment_end = (
        len(line_text) if maybe_sentence_end is None else maybe_sentence_end.start()
    )
    for each_span in all_spans[span_index + 1 :]:
        if each_span.start() >= segment_end:
            break
        if _hook_stem_in_span(each_span.group(1)) is not None:
            return each_span.start()
    return segment_end


def _line_diagnostics(
    document: Document,
    line_text: str,
    line_number: int,
    all_known_stems: frozenset[str],
    all_registered_stems: frozenset[str],
) -> tuple[Diagnostic, ...]:
    all_spans = tuple(re.finditer(constants.INLINE_CODE_PATTERN, line_text))
    all_diagnostics: list[Diagnostic] = []
    for each_index, each_span in enumerate(all_spans):
        maybe_stem = _hook_stem_in_span(each_span.group(1))
        if maybe_stem is None or maybe_stem not in all_known_stems:
            continue
        if maybe_stem in all_registered_stems:
            continue
        claim_end = _claim_segment_end(line_text, all_spans, each_index)
        if not _names_a_live_action(line_text[each_span.end() : claim_end]):
            continue
        all_diagnostics.append(
            Diagnostic(
                constants.RETIRED_HOOK_PROSE_RULE_ID,
                Severity.ERROR,
                constants.RETIRED_HOOK_PROSE_MESSAGE.format(hook_name=maybe_stem),
                Location(document.path, line_number, each_span.start() + 1),
            )
        )
    return tuple(all_diagnostics)


def _hook_stem_sets(package_root: Path) -> tuple[frozenset[str], frozenset[str]]:
    hooks_root = package_root / constants.HOOKS_DIRECTORY_NAME
    all_known_stems = _present_hook_stems(hooks_root) | _retired_roster_stems(
        package_root
    )
    return all_known_stems, _registered_hook_stems(hooks_root)


def retired_hook_prose_diagnostics(
    document: Document, repository_root: Path
) -> tuple[Diagnostic, ...]:
    """Report rules prose that credits an unregistered hook with a live action.

    Args:
        document: Current rules Markdown text and path.
        repository_root: Request repository root for package resolution.

    Returns:
        One diagnostic for each live claim about a hook that runs nowhere.
    """
    all_known_stems, all_registered_stems = _hook_stem_sets(
        _package_root(repository_root, document)
    )
    all_diagnostics: list[Diagnostic] = []
    for each_line_number, each_line in enumerate(document.text.splitlines(), 1):
        if _describes_a_replacement(each_line):
            continue
        all_diagnostics.extend(
            _line_diagnostics(
                document,
                each_line,
                each_line_number,
                all_known_stems,
                all_registered_stems,
            )
        )
    return tuple(all_diagnostics)
