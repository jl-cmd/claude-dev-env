"""Golden-output snapshot for validate_content, guarding the pure decomposition.

Records ``validate_content``'s ordered issue list for three representative
fixtures — a Python cross-file duplicate-body hit, a JavaScript boolean-naming
hit, and a Python-built-HTML orphan-CSS-class hit — so a decomposition that
reorders or drops a dispatch line shows up as a changed list, not a
still-green suite.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


def _load_module_from_path(module_name: str, module_path: Path) -> ModuleType:
    """Load and execute the module found at module_path, under module_name."""
    specification = importlib.util.spec_from_file_location(module_name, module_path)
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


_BLOCKING_DIRECTORY = Path(__file__).resolve().parent
code_rules_enforcer = _load_module_from_path(
    "code_rules_enforcer", _BLOCKING_DIRECTORY / "code_rules_enforcer.py"
)

_DUPLICATE_FUNCTION_SOURCE = (
    "def compute_shipping_total(order_total: float, tax_rate: float) -> float:\n"
    "    taxed_total = order_total * (1 + tax_rate)\n"
    "    rounded_total = round(taxed_total, 2)\n"
    "    return rounded_total\n"
)
_JS_BOOLEAN_SOURCE = "const active = true;\n"
_CSS_ORPHAN_CLASS_SOURCE = (
    '"""Render a status badge."""\n\n'
    "STATUS_MARKUP = '<div class=\"status-badge\">Active</div>'\n"
    "STYLE_BLOCK = '<style>.status-pill { color: green; }</style>'\n"
)

EXPECTED_PYTHON_CROSS_FILE_ISSUES = [
    "Line 3: Magic value 2 - extract to named constant",
    "Function 'compute_shipping_total' duplicates shipping_helper.py::compute_shipping_total"
    " — this function body is identical to one in a sibling module; extract a single shared"
    " helper (for example in hooks_constants/) and import it from both modules instead of"
    " copying it (Reuse before create / DRY) (duplicate body span at line 1, spanning 4 lines)",
]
EXPECTED_JS_ISSUES = [
    "Line 1: Boolean active - prefix with is/has/should/can/was/did",
]
EXPECTED_CSS_ISSUES = [
    "Line 3: Constant STATUS_MARKUP - move to config/",
    "Line 4: Constant STYLE_BLOCK - move to config/",
    "Line 3: CSS class 'status-badge' used in markup has no matching '.status-badge' selector"
    " - add a matching '.<class>' selector to the <style> block, or drop the unused class"
    " attribute (CODE_RULES self-documenting markup)",
]


def test_python_cross_file_duplicate_snapshot_is_unchanged(tmp_path: Path) -> None:
    """validate_content's ordered output for a cross-file duplicate stays fixed.

    ::

        sibling_dir/shipping_helper.py         -> the real on-disk sibling module
        "/repo/.../shipping_target.py"         -> the classification-only file_path
        -> validate_content reports the exact ordered issues recorded here

    ``file_path`` names a path that is never opened — it only drives
    extension and test/config classification — while ``sibling_directory``
    points at the real ``tmp_path`` sibling scan. A pytest ``tmp_path``
    segment starts with the test's own name, which starts with ``test_``, so
    using it as ``file_path`` would misclassify this production fixture as a
    test file and silently skip every production-only check.
    """
    sibling_dir = tmp_path / "sibling_dir"
    sibling_dir.mkdir()
    (sibling_dir / "shipping_helper.py").write_text(_DUPLICATE_FUNCTION_SOURCE, encoding="utf-8")
    classification_only_file_path = "/repo/packages/demo/shipping/shipping_target.py"

    issues = code_rules_enforcer.validate_content(
        _DUPLICATE_FUNCTION_SOURCE,
        classification_only_file_path,
        "",
        sibling_directory=sibling_dir,
    )

    assert issues == EXPECTED_PYTHON_CROSS_FILE_ISSUES


def test_javascript_boolean_naming_snapshot_is_unchanged() -> None:
    issues = code_rules_enforcer.validate_content(
        _JS_BOOLEAN_SOURCE, "packages/app/frontend/status.js", ""
    )
    assert issues == EXPECTED_JS_ISSUES


def test_python_orphan_css_class_snapshot_is_unchanged() -> None:
    issues = code_rules_enforcer.validate_content(
        _CSS_ORPHAN_CLASS_SOURCE, "packages/app/widgets/status_widget.py", ""
    )
    assert issues == EXPECTED_CSS_ISSUES
