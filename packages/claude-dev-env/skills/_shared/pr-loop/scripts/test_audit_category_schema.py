"""Parity tests for the A-Q audit-category schema and projections."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from skills_pr_loop_constants.path_resolver_constants import ALL_AUDIT_CATEGORY_ENTRIES


def _load_audit_category_schema() -> ModuleType:
    module_path = _SCRIPTS_DIR / "audit_category_schema.py"
    spec = importlib.util.spec_from_file_location("audit_category_schema", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["audit_category_schema"] = module
    spec.loader.exec_module(module)
    return module


audit_category_schema = _load_audit_category_schema()


def test_schema_lists_a_through_q_in_order() -> None:
    schema = audit_category_schema.load_audit_category_schema()
    all_ids = [each_category["id"] for each_category in schema["categories"]]
    assert all_ids == list("ABCDEFGHIJKLMNOPQ")


def test_schema_entries_match_constant_export() -> None:
    assert (
        audit_category_schema.category_id_title_entries()
        == list(ALL_AUDIT_CATEGORY_ENTRIES)
    )


def test_validate_projections_matches_rubrics_and_prompts() -> None:
    all_findings = audit_category_schema.validate_projections()
    assert all_findings == [], all_findings


def test_skeleton_projection_is_byte_stable() -> None:
    schema = audit_category_schema.load_audit_category_schema()
    first_render = audit_category_schema.render_skeleton_projections(schema)
    second_render = audit_category_schema.render_skeleton_projections(
        json.loads(json.dumps(schema))
    )
    assert first_render == second_render
    assert "A1" in first_render["A"]
    assert first_render["A"].count("\n") >= 1


def test_schema_omits_worked_example_prose() -> None:
    schema_path = audit_category_schema.audit_category_schema_path()
    schema_text = schema_path.read_text(encoding="utf-8")
    assert "Examples of Category" not in schema_text
    assert "Sample prompt" not in schema_text
