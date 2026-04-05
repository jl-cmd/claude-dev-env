"""Tests for GitHub Action workflow YAML validity."""

from pathlib import Path

import yaml


def test_workflow_is_valid_yaml() -> None:
    """Test that the workflow file is valid YAML."""
    workflow_path = Path(__file__).parent / "pre-push-review.yml"
    assert workflow_path.exists(), "Workflow file must exist"

    with open(workflow_path) as f:
        data = yaml.safe_load(f)

    assert "name" in data
    assert "on" in data or True in data
    assert "jobs" in data


def test_workflow_has_validate_job() -> None:
    """Test that workflow has a validate job with required steps."""
    workflow_path = Path(__file__).parent / "pre-push-review.yml"

    with open(workflow_path) as f:
        data = yaml.safe_load(f)

    assert "validate" in data["jobs"]
    job = data["jobs"]["validate"]
    assert "steps" in job
    step_names = [s.get("name", "") for s in job["steps"]]
    assert "Checkout code" in step_names
    assert "Set up Python" in step_names
