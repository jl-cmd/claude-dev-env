"""Exercise the protocol validator through its command-line interface."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from validate_protocol import ProtocolValidationError, validate_record

SCRIPT_PATH = Path(__file__).with_name("validate_protocol.py")
SCHEMA_PATH = SCRIPT_PATH.parent.parent / "reference" / "run-record.schema.json"


def valid_record() -> dict[str, object]:
    verification = {"acceptance_output": "passed: pytest", "verifier_output": "passed: clean", "verified_commit_gate": "passed: exact surface", "surface_hash": "a" * 64}
    return {
        "task_identity": "task-3", "deliverable": "validator", "allowed_files": ["validator.py"],
        "acceptance_check": "pytest", "baseline": "clean", "worker_route": "implementation worker; effort=low", "commit": "a1b2c3d",
        "review_record": {"resolved_model": "Luna", "effort": "low", "command": "/e-code-review low", "findings": [], "repair_status": "clean", "surface_hash": "a" * 64, "findings_only": True, "has_repair_flag": False},
        "repair_record": {"resolved_model": "Luna", "effort": "low", "confirmed_findings": [], "repair_status": "not-required", "surface_hash": "a" * 64},
        "reverification_record": verification, "verification_record": verification.copy(),
    }


def run_validator(record_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(SCRIPT_PATH), str(record_path)], capture_output=True, text=True, check=False)


def test_cli_accepts_valid_record(tmp_path: Path) -> None:
    record_path = tmp_path / "record.json"
    record_path.write_text(json.dumps(valid_record()), encoding="utf-8")
    completed_run = run_validator(record_path)
    assert completed_run.returncode == 0
    assert completed_run.stdout.strip() == "protocol validation passed"
    assert completed_run.stderr == ""


def test_cli_rejects_invalid_utf8_record(tmp_path: Path) -> None:
    record_path = tmp_path / "invalid-utf8.json"
    record_path.write_bytes(b"{\xff")

    completed_run = run_validator(record_path)

    assert completed_run.returncode == 2
    assert completed_run.stdout == ""
    assert completed_run.stderr == "protocol validation failed: invalid UTF-8\n"


def test_cli_rejects_invalid_mutations(tmp_path: Path) -> None:
    mutations = (("bad-commit", "commit", "not-a-commit"), ("bad-review", "findings_only", False), ("missing-evidence", "verification_record", None), ("bad-type", "allowed_files", "file.py"), ("empty-allowed-files", "allowed_files", []), ("extra-review-field", "review_extra", "unexpected"))
    for each_name, each_field, mutated_field in mutations:
        record = valid_record()
        if each_field == "findings_only":
            review_record = record["review_record"]
            assert isinstance(review_record, dict)
            review_record[each_field] = mutated_field
        elif each_field == "review_extra":
            review_record = record["review_record"]
            assert isinstance(review_record, dict)
            review_record[each_field] = mutated_field
        elif mutated_field is None:
            del record[each_field]
        else:
            record[each_field] = mutated_field
        record_path = tmp_path / f"{each_name}.json"
        record_path.write_text(json.dumps(record), encoding="utf-8")
        completed_run = run_validator(record_path)
        assert completed_run.returncode == 2
        assert completed_run.stdout == ""
        assert completed_run.stderr.startswith("protocol validation failed:")


def test_validate_record_rejects_absolute_allowed_file_paths() -> None:
    for each_absolute_path in ("/absolute/file.py", r"C:\absolute\file.py", "C:/absolute/file.py"):
        record = valid_record()
        record["allowed_files"] = [each_absolute_path]

        try:
            validate_record(record, SCHEMA_PATH)
        except ProtocolValidationError as error:
            assert str(error) == "allowed_files contains an absolute path"
        else:
            raise AssertionError("absolute allowed file paths must be rejected")


def test_validate_record_enforces_modified_schema(tmp_path: Path) -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    assert isinstance(schema, dict)
    required_fields = schema["required"]
    assert isinstance(required_fields, list)
    required_fields.append("schema_added_field")
    modified_schema_path = tmp_path / "modified-schema.json"
    modified_schema_path.write_text(json.dumps(schema), encoding="utf-8")

    try:
        validate_record(valid_record(), modified_schema_path)
    except ProtocolValidationError as error:
        assert "schema_added_field" in str(error)
    else:
        raise AssertionError("modified schema must reject a record missing its new required field")


def test_validate_record_accepts_worktree_with_matching_committed_surface_hash(tmp_path: Path) -> None:
    worktree_path = tmp_path / "worktree"
    worktree_path.mkdir()
    subprocess.run(["git", "init"], cwd=worktree_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=worktree_path, check=True)
    subprocess.run(["git", "config", "user.name", "Protocol Test"], cwd=worktree_path, check=True)
    tracked_file = worktree_path / "validator.py"
    tracked_file.write_text("baseline\n", encoding="utf-8")
    subprocess.run(["git", "add", "validator.py"], cwd=worktree_path, check=True)
    subprocess.run(["git", "commit", "-m", "baseline"], cwd=worktree_path, check=True, capture_output=True)
    tracked_file.write_text("validated\n", encoding="utf-8")
    subprocess.run(["git", "add", "validator.py"], cwd=worktree_path, check=True)
    subprocess.run(["git", "commit", "-m", "validated"], cwd=worktree_path, check=True, capture_output=True)
    commit_hash = subprocess.run(["git", "rev-parse", "HEAD"], cwd=worktree_path, check=True, capture_output=True, text=True).stdout.strip()
    committed_surface = subprocess.run(["git", "diff", f"{commit_hash}^", commit_hash, "--", "validator.py"], cwd=worktree_path, check=True, capture_output=True).stdout
    surface_hash = hashlib.sha256(committed_surface).hexdigest()
    record = valid_record()
    record["worktree"] = str(worktree_path)
    record["commit"] = commit_hash
    for each_field_name in ("review_record", "repair_record", "reverification_record", "verification_record"):
        nested_record = record[each_field_name]
        assert isinstance(nested_record, dict)
        nested_record["surface_hash"] = surface_hash

    validate_record(record, SCHEMA_PATH)
