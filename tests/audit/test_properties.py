"""Checks that each correctness property row cites a locked outside source."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

AUDIT_DATA_DIRECTORY = Path(__file__).resolve().parent / "data"
PROPERTIES_PATH = AUDIT_DATA_DIRECTORY / "properties.tsv"
INVENTORY_PATH = AUDIT_DATA_DIRECTORY / "inventory.tsv"
HOUSE_SOURCE_ID = "house"
CLASS_SEPARATOR = ";"
ALL_LOCKED_SOURCE_IDS = frozenset(
    {
        "W1",
        "W2",
        "W3",
        "W4",
        "W5",
        "W6",
        "W7",
        "W8",
        "W9",
        "W10",
        "S-MEMORY",
        "S-AGENTS",
        "S-COMMANDS",
        "S-PLUGINS",
        "S-SETTINGS",
        "S-CLI",
        "S-MARKET-SKILLCREATOR",
        "S-MARKET-CLAUDEMD",
        "S-MARKET-HOOKIFY",
        "S-PROMPT",
        "S-GH-SYNTAX",
        "S-GH-SECURITY",
        "S-STE",
        "S-UP-PYTHON",
        "S-UP-NODETEST",
        "S-UP-POWERSHELL",
        "G1",
        "G2",
        "G3",
        "G4",
        "G5",
        "G6",
        "G7",
        "PS-ORCHESTRATE",
        "PS-TEST-BEHAVIOR",
        "PS-SUBTRACT",
        "PS-READER-LOAD",
        "PS-ENCODE",
    }
)
ALL_TARGET_EVIDENCE_SOURCE_IDS = frozenset({"G1", "G2", "G3", "G4", "G5", "G6", "G7"})


def read_tsv_rows(tsv_path: Path) -> list[dict[str, str]]:
    with open(tsv_path, encoding="utf-8", newline="") as tsv_file:
        return list(csv.DictReader(tsv_file, delimiter="\t"))


def _source_faults(property_id: str, source_id: str, quote: str) -> list[str]:
    all_faults: list[str] = []
    if source_id != HOUSE_SOURCE_ID and source_id not in ALL_LOCKED_SOURCE_IDS:
        all_faults.append(f"{property_id}: unknown source id {source_id}")
    if source_id in ALL_TARGET_EVIDENCE_SOURCE_IDS:
        all_faults.append(f"{property_id}: target evidence {source_id} is no yardstick")
    if source_id != HOUSE_SOURCE_ID and not quote.strip():
        all_faults.append(f"{property_id}: empty quote on a sourced row")
    return all_faults


def _class_faults(
    property_id: str, class_field: str, all_inventory_classes: frozenset[str]
) -> list[str]:
    return [
        f"{property_id}: class {each_class!r} absent from inventory"
        for each_class in class_field.split(CLASS_SEPARATOR)
        if each_class not in all_inventory_classes
    ]


def find_property_faults(
    all_property_rows: list[dict[str, str]], all_inventory_classes: frozenset[str]
) -> list[str]:
    all_faults: list[str] = []
    for each_row in all_property_rows:
        property_id = each_row["property_id"]
        all_faults.extend(
            _source_faults(property_id, each_row["source_id"], each_row["quote"])
        )
        all_faults.extend(
            _class_faults(
                property_id, each_row["component_classes"], all_inventory_classes
            )
        )
    return all_faults


def inventory_classes() -> frozenset[str]:
    return frozenset(each_row["kind"] for each_row in read_tsv_rows(INVENTORY_PATH))


def valid_row() -> dict[str, str]:
    return {
        "property_id": "P-X",
        "source_id": "W1",
        "quote": "Exit 2 means a blocking error.",
        "component_classes": "hook_module",
    }


def test_should_find_no_fault_in_the_shipped_property_rows() -> None:
    all_property_rows = read_tsv_rows(PROPERTIES_PATH)
    assert all_property_rows
    assert find_property_faults(all_property_rows, inventory_classes()) == []


def test_should_give_each_property_a_unique_id() -> None:
    all_property_ids = [
        each_row["property_id"] for each_row in read_tsv_rows(PROPERTIES_PATH)
    ]
    assert len(all_property_ids) == len(set(all_property_ids))


def test_should_accept_the_valid_control_row() -> None:
    assert find_property_faults([valid_row()], frozenset({"hook_module"})) == []


@pytest.mark.parametrize(
    ("changed_field", "changed_value", "expected_fragment"),
    [
        ("source_id", "W99", "unknown source id"),
        ("source_id", "G4", "no yardstick"),
        ("quote", " ", "empty quote"),
        ("component_classes", "hook_module;ghost", "absent from inventory"),
    ],
)
def test_should_report_each_invalid_row(
    changed_field: str, changed_value: str, expected_fragment: str
) -> None:
    broken_row = {**valid_row(), changed_field: changed_value}
    all_faults = find_property_faults([broken_row], frozenset({"hook_module"}))
    assert len(all_faults) == 1
    assert expected_fragment in all_faults[0]


def test_should_accept_a_house_row_with_no_quote() -> None:
    house_row = {**valid_row(), "source_id": HOUSE_SOURCE_ID, "quote": ""}
    assert find_property_faults([house_row], frozenset({"hook_module"})) == []
