"""Report authored prose that defines its subject against a rejected reading.

A contrast leaves the reader holding two readings where one would do. The
detector lives in ``scripts/contrast_framing.py`` and reads its pattern list
from ``scripts/dev_env_scripts_constants/contrast_framing_constants.py``, the
same list the durable post linter reads.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import ModuleType

from .config import constants
from .model import Diagnostic, Document, Location, Severity


def _scripts_module(module_name: str) -> ModuleType:
    scripts_directory = str(Path(__file__).resolve().parents[1])
    if scripts_directory not in sys.path:
        sys.path.insert(0, scripts_directory)
    return importlib.import_module(module_name)


def accepts_authored_markdown(document: Document) -> bool:
    """Return whether the document is Markdown an author wrote.

    Args:
        document: Candidate document.

    Returns:
        True for Markdown outside the generated documents.
    """
    if document.path.suffix.lower() not in constants.ALL_MARKDOWN_SUFFIXES:
        return False
    return document.path.name.lower() not in constants.ALL_GENERATED_DOCUMENT_NAMES


def contrast_framing_diagnostics(
    document: Document, repository_root: Path
) -> tuple[Diagnostic, ...]:
    """Report each contrast-framing occurrence in one document.

    Args:
        document: Current document text and path.
        repository_root: Request repository root, unused by this detector.

    Returns:
        Contrast-framing diagnostics in document order.
    """
    del repository_root
    detector = _scripts_module("contrast_framing")
    all_hits = detector.find_contrast_framing(document.text)
    return tuple(
        Diagnostic(
            constants.CONTRAST_FRAMING_RULE_ID,
            Severity.ERROR,
            detector.describe_contrast_framing(
                document.text, each_line_number, each_form_name
            ),
            Location(document.path, each_line_number, each_column),
        )
        for each_line_number, each_column, each_form_name in all_hits
    )
