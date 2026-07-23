import subprocess
from pathlib import Path

import pytest

from review_tier import build_generation, inventory_generation, router_state_directory, router_state_root, router_state_root_id


def test_generation_uses_live_git_surface(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / "tracked.py").write_text("x = 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "tracked.py"], cwd=tmp_path, check=True)
    subprocess.run(["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-qm", "init"], cwd=tmp_path, check=True)
    (tmp_path / "untracked.py").write_text("y = 2\n", encoding="utf-8")
    inventory = inventory_generation(tmp_path)
    assert "untracked.py" in inventory["untracked"]
    card = build_generation(tmp_path, card_path=tmp_path / "card.json")
    assert card["inventory_hash"] == inventory["inventory_hash"]


def test_router_state_root_id_is_stable_for_normalized_roots(tmp_path: Path) -> None:
    (tmp_path / "data").mkdir()
    (tmp_path / "data-link").symlink_to(tmp_path / "data", target_is_directory=True)
    state_root = router_state_root(tmp_path, {"CLAUDE_PLUGIN_DATA": str(tmp_path / "data" / ".." / "data")})
    symlink_root = router_state_root(tmp_path, {"CLAUDE_PLUGIN_DATA": str(tmp_path / "data-link")})
    assert state_root == symlink_root
    assert router_state_root_id(state_root) == router_state_root_id(symlink_root)


def test_router_state_directory_is_scoped_under_the_router_root(tmp_path: Path) -> None:
    state_directory = router_state_directory(tmp_path)
    custom_environment = {"CLAUDE_PLUGIN_DATA": str(tmp_path / "custom-data")}
    custom_state_directory = router_state_directory(tmp_path, custom_environment)

    assert state_directory.parent == router_state_root(tmp_path)
    assert custom_state_directory == router_state_root(tmp_path, custom_environment) / state_directory.name
    assert custom_state_directory != state_directory
    assert len(state_directory.name) == 64


def test_generation_records_committed_and_working_domains_once(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repository, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repository, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repository, check=True)
    tracked = repository / "packages" / "feature.py"
    tracked.parent.mkdir()
    tracked.write_text("one\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repository, check=True)
    subprocess.run(["git", "commit", "-qm", "initial"], cwd=repository, check=True)
    initial_commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repository, check=True, capture_output=True, text=True).stdout.strip()
    tracked.write_text("one\nbase\n", encoding="utf-8")
    subprocess.run(["git", "add", str(tracked)], cwd=repository, check=True)
    subprocess.run(["git", "commit", "-qm", "feature"], cwd=repository, check=True)
    tracked.write_text("one\ntwo\n", encoding="utf-8")
    subprocess.run(["git", "add", str(tracked)], cwd=repository, check=True)
    tracked.write_text("one\ntwo\nthree\n", encoding="utf-8")
    (repository / "new.py").write_text("new\n", encoding="utf-8")
    inventory = inventory_generation(repository, initial_commit)
    records = {record["path"]: record["domains"] for record in inventory["files_by_domain"]}
    assert records["packages/feature.py"] == ["committed", "staged", "unstaged"]
    assert records["new.py"] == ["untracked"]
    assert inventory["base_ref"] and inventory["merge_base"] and inventory["HEAD"]


@pytest.mark.parametrize("base_ref", ["missing", "HEAD~99"])
def test_invalid_base_writes_no_card(tmp_path: Path, base_ref: str) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repository, check=True)
    (repository / "seed.txt").write_text("seed\n", encoding="utf-8")
    subprocess.run(["git", "add", "seed.txt"], cwd=repository, check=True)
    subprocess.run(["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-qm", "initial"], cwd=repository, check=True)
    with pytest.raises(ValueError, match="INVALID_BASE_REF"):
        build_generation(repository, base_ref=base_ref, card_path=tmp_path / "card.json")
    assert not (tmp_path / "card.json").exists()


def _git_repository(root: Path) -> None:
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True)
    (root / "seed.txt").write_text("seed\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(["git", "commit", "-qm", "initial"], cwd=root, check=True)


def test_diff_hash_changes_when_same_path_content_changes(tmp_path: Path) -> None:
    _git_repository(tmp_path)
    tracked_path = tmp_path / "seed.txt"
    first_hash = inventory_generation(tmp_path)["diff_hash"]
    tracked_path.write_text("changed\n", encoding="utf-8")
    assert inventory_generation(tmp_path)["diff_hash"] != first_hash


def test_effective_lines_include_committed_staged_unstaged_and_untracked(tmp_path: Path) -> None:
    _git_repository(tmp_path)
    committed_path = tmp_path / "committed.txt"
    committed_path.write_text("one\ntwo\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "committed"], cwd=tmp_path, check=True)
    staged_path = tmp_path / "staged.txt"
    staged_path.write_text("one\ntwo\n", encoding="utf-8")
    subprocess.run(["git", "add", str(staged_path)], cwd=tmp_path, check=True)
    staged_path.write_text("one\ntwo\nthree\n", encoding="utf-8")
    unstaged_path = tmp_path / "seed.txt"
    unstaged_path.write_text("seed\nchanged\n", encoding="utf-8")
    (tmp_path / "untracked.txt").write_text("one\ntwo\n", encoding="utf-8")
    inventory = inventory_generation(tmp_path)
    assert inventory["lines"] >= 6


def test_inventory_preserves_rename_prior_path_and_operations(tmp_path: Path) -> None:
    _git_repository(tmp_path)
    old_path = tmp_path / "old name.txt"
    old_path.write_text("content\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "rename source"], cwd=tmp_path, check=True)
    new_path = tmp_path / "new name.txt"
    old_path.rename(new_path)
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    records = {record["path"]: record for record in inventory_generation(tmp_path)["files_by_domain"]}
    assert records["new name.txt"]["prior_path"] == "old name.txt"
    assert records["new name.txt"]["operation_by_domain"]["staged"] == "R"


def test_inventory_preserves_delete_binary_space_unicode_and_symlink_identity(tmp_path: Path) -> None:
    _git_repository(tmp_path)
    deleted = tmp_path / "deleted file.txt"
    deleted.write_text("delete me\n", encoding="utf-8")
    binary = tmp_path / "binary.bin"
    binary.write_bytes(b"\0\xff")
    unicode_path = tmp_path / "café.txt"
    unicode_path.write_text("unicode\n", encoding="utf-8")
    link = tmp_path / "link.txt"
    link.symlink_to("seed.txt")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "surface"], cwd=tmp_path, check=True)
    surface_commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=tmp_path, check=True, capture_output=True, text=True).stdout.strip()
    deleted.unlink()
    binary.write_bytes(b"\0\x00changed")
    unicode_path.write_text("unicode changed\n", encoding="utf-8")
    link.unlink()
    link.symlink_to("café.txt")
    subprocess.run(["git", "add", "-u"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    records = {record["path"]: record for record in inventory_generation(tmp_path, surface_commit)["files_by_domain"]}
    assert records["deleted file.txt"]["content_sha256"] != "0" * 64
    assert records["binary.bin"]["binary"] is True
    assert records["café.txt"]["path"] == "café.txt"
    assert records["link.txt"]["content_sha256"]


def test_package_count_uses_distinct_monorepo_package_keys(tmp_path: Path) -> None:
    _git_repository(tmp_path)
    for path in ("packages/one/a.py", "packages/one/b.py", "apps/two/c.py", "root.py"):
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("x\n", encoding="utf-8")
    assert inventory_generation(tmp_path)["packages"] == 3


def test_explicit_and_default_base_provenance_fields_are_exact(tmp_path: Path) -> None:
    _git_repository(tmp_path)
    default_inventory = inventory_generation(tmp_path)
    explicit_inventory = inventory_generation(tmp_path, "HEAD")
    assert default_inventory["base_source"] == "configured_fallback"
    assert explicit_inventory["base_source"] == "explicit"
    for field in ("base_ref", "base_source", "base_sha", "merge_base_sha", "head_sha"):
        assert default_inventory[field]
