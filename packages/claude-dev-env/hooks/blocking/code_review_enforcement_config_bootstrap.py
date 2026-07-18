"""Deterministic loader for the code-review enforcement constants module.

The stamp store and every code-review gate import their shared constants as
``from config.code_review_enforcement_constants import ...``. In the installed
hook tree a second, unrelated ``config`` package can sit ahead of this package
on ``sys.path`` and win that dotted name by path order, so the import binds to
the wrong file and raises ImportError on any constant the stale copy lacks.
This module binds the dotted name to its sibling ``config/`` file by explicit
location, so resolution never depends on ``sys.path`` order.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def register_code_review_enforcement_constants() -> None:
    """Bind the code-review enforcement constants dotted name to its config file.

    ::

        sys.path = ["<installed hooks>", "<blocking>"]  # foreign config first
        register_code_review_enforcement_constants()
        from config.code_review_enforcement_constants import STAMP_DIRECTORY_NAME
        ok: bound to <blocking>/config/code_review_enforcement_constants.py

    A ``from config.code_review_enforcement_constants import`` that follows this
    call reads the entry straight from ``sys.modules``, so it resolves to this
    file whatever else owns the ``config`` name. An entry already cached is left
    in place, so the call is idempotent and never displaces a module a caller
    loaded on purpose.

    Returns:
        None. The effect is the ``sys.modules`` registration.
    """
    _bind_config_module_by_location(
        "config.code_review_enforcement_constants",
        Path(__file__).resolve().parent / "config" / "code_review_enforcement_constants.py",
    )


def _bind_config_module_by_location(dotted_name: str, constants_file_path: Path) -> None:
    """Register a dotted config name against an explicit file path in sys.modules."""
    if dotted_name in sys.modules:
        return
    module_spec = importlib.util.spec_from_file_location(dotted_name, constants_file_path)
    if module_spec is None or module_spec.loader is None:
        return
    constants_module = importlib.util.module_from_spec(module_spec)
    sys.modules[dotted_name] = constants_module
    module_spec.loader.exec_module(constants_module)
