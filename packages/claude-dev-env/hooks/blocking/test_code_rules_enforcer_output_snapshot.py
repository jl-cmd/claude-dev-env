"""Golden-output snapshot for the phase-split validators, guarding both phases.

Records the full-gate phase's ordered issue list for three representative
fixtures — a Python cross-file duplicate-body hit, a JavaScript boolean-naming
hit, and a Python-built-HTML orphan-CSS-class hit — so a decomposition that
reorders or drops a dispatch line shows up as a changed list, not a
still-green suite. Each fixture also records the edit-lane phase's list, which
matches the full-gate list except for the cross-file finding the edit lane
skips.
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
EXPECTED_PYTHON_CROSS_FILE_EDIT_LANE_ISSUES = [
    "Line 3: Magic value 2 - extract to named constant",
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
EXPECTED_CSS_EDIT_LANE_ISSUES = [
    "Line 3: Constant STATUS_MARKUP - move to config/",
    "Line 4: Constant STYLE_BLOCK - move to config/",
]


def test_python_cross_file_duplicate_snapshot_is_unchanged(tmp_path: Path) -> None:
    """Both phases' ordered output for a cross-file duplicate stays fixed.

    ``file_path`` is a fixed classification-only path, never opened, so the
    real ``tmp_path`` sibling scan (which embeds this test's own name, a
    ``test_`` match) never misclassifies the fixture as a test file.
    """
    sibling_dir = tmp_path / "sibling_dir"
    sibling_dir.mkdir()
    (sibling_dir / "shipping_helper.py").write_text(_DUPLICATE_FUNCTION_SOURCE, encoding="utf-8")
    classification_only_file_path = "/repo/packages/demo/shipping/shipping_target.py"

    full_gate_issues = code_rules_enforcer.validate_content_for_full_gate(
        _DUPLICATE_FUNCTION_SOURCE,
        classification_only_file_path,
        "",
        sibling_directory=sibling_dir,
    )
    edit_lane_issues = code_rules_enforcer.validate_content_for_edit_lane(
        _DUPLICATE_FUNCTION_SOURCE,
        classification_only_file_path,
        "",
        sibling_directory=sibling_dir,
    )

    assert full_gate_issues == EXPECTED_PYTHON_CROSS_FILE_ISSUES
    assert edit_lane_issues == EXPECTED_PYTHON_CROSS_FILE_EDIT_LANE_ISSUES


def test_javascript_boolean_naming_snapshot_is_unchanged() -> None:
    full_gate_issues = code_rules_enforcer.validate_content_for_full_gate(
        _JS_BOOLEAN_SOURCE, "packages/app/frontend/status.js", ""
    )
    edit_lane_issues = code_rules_enforcer.validate_content_for_edit_lane(
        _JS_BOOLEAN_SOURCE, "packages/app/frontend/status.js", ""
    )
    assert full_gate_issues == EXPECTED_JS_ISSUES
    assert edit_lane_issues == EXPECTED_JS_ISSUES


def test_python_orphan_css_class_snapshot_is_unchanged() -> None:
    full_gate_issues = code_rules_enforcer.validate_content_for_full_gate(
        _CSS_ORPHAN_CLASS_SOURCE, "packages/app/widgets/status_widget.py", ""
    )
    edit_lane_issues = code_rules_enforcer.validate_content_for_edit_lane(
        _CSS_ORPHAN_CLASS_SOURCE, "packages/app/widgets/status_widget.py", ""
    )
    assert full_gate_issues == EXPECTED_CSS_ISSUES
    assert edit_lane_issues == EXPECTED_CSS_EDIT_LANE_ISSUES
