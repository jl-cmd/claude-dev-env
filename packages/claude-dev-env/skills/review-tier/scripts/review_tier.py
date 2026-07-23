"""Build canonical pull-request evidence and select a review tier."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Mapping, Sequence

from review_tier_constants.config.constants import ALL_DEPENDENCY_MARKERS, ALL_HARD_TRIGGER_MARKERS, ALL_PACKAGE_ROOT_NAMES, ALL_PUBLIC_API_MARKERS, ALL_SOURCE_SUFFIXES, ALL_STATUS_ARGUMENTS, ALL_STATUS_DOMAINS, ALL_TIER_ORDER, ALL_UNTRACKED_ARGUMENTS, AMBIGUOUS_BASE_REF, DEFAULT_BRANCH_FALLBACK, GIT_COMMAND_FAILED, GIT_HEAD_REF, INVALID_BASE_REF, JSON_INDENT, MALFORMED_TIER_POLICY, MAX_AXIS_VALUE, MIN_NONEMPTY_RISK, PATH_SEPARATOR, PLUGIN_DATA_ENVIRONMENT, REMOTE_HEAD_REF, ROOT_PACKAGE, ROUTING_STATE_ROOT_TRACKED, STATUS_CODE_LENGTH, STATUS_PREFIX_LENGTH, UNAPPROVED_TIER_DOWNGRADE, UNKNOWN_TIER


def router_state_root(repo_root: str | Path, all_environment: Mapping[str, str] | None = None) -> Path:
    """Return the canonical router state root for a repository."""
    selected_environment = all_environment or os.environ
    plugin_root = Path(selected_environment.get(PLUGIN_DATA_ENVIRONMENT, Path(repo_root).resolve() / ".claude-plugin-data"))
    return (plugin_root / "review-routing" / "v1").resolve()


def router_state_directory(repo_root: str | Path, all_environment: Mapping[str, str] | None = None) -> Path:
    """Return the repository-specific directory under the router state root."""
    resolved_root = Path(repo_root).resolve()
    worktree_key = hashlib.sha256(str(resolved_root).encode()).hexdigest()
    return router_state_root(resolved_root, all_environment=all_environment) / worktree_key


def router_state_root_id(state_root: str | Path) -> str:
    """Return the stable identity digest for a canonical router state root."""
    return hashlib.sha256(str(Path(state_root).resolve()).casefold().encode()).hexdigest()


def _is_inside_state_root(repo_root: Path, relative_path: str, state_root: Path) -> bool:
    return (repo_root / relative_path).resolve().is_relative_to(state_root)

def _git(root: Path, all_arguments: Sequence[str], is_required: bool) -> bytes:
    command = ["git", *all_arguments]
    completed_process = subprocess.run(command, cwd=root, check=is_required, capture_output=True)
    if completed_process.returncode and is_required:
        raise ValueError(GIT_COMMAND_FAILED)
    return completed_process.stdout


def _resolve_base(root: Path, requested_base: str | None) -> tuple[str, str]:
    if requested_base:
        candidate = _git(root, ["rev-parse", "--verify", requested_base], is_required=False).decode().strip()
        if not candidate:
            raise ValueError(INVALID_BASE_REF)
        return requested_base, candidate
    remote_head = _git(root, ["symbolic-ref", "--quiet", REMOTE_HEAD_REF], is_required=False).decode().strip()
    if remote_head:
        candidate = _git(root, ["rev-parse", "--verify", remote_head], is_required=False).decode().strip()
        if candidate:
            return remote_head, candidate
    fallback = _git(root, ["rev-parse", "--verify", DEFAULT_BRANCH_FALLBACK], is_required=False).decode().strip()
    if fallback:
        return DEFAULT_BRANCH_FALLBACK, fallback
    raise ValueError(AMBIGUOUS_BASE_REF)


def _status_domains(root: Path, state_root: Path | None = None) -> dict[str, set[str]]:
    all_status_lines = _git(root, list(ALL_STATUS_ARGUMENTS), is_required=True).decode(errors="surrogateescape").split("\0")
    domains = {domain: set() for domain in ALL_STATUS_DOMAINS}
    for each_status_line in all_status_lines:
        if len(each_status_line) < STATUS_PREFIX_LENGTH:
            continue
        path = each_status_line[STATUS_PREFIX_LENGTH:]
        if state_root is not None and _is_inside_state_root(root, path, state_root):
            continue
        if each_status_line[:STATUS_CODE_LENGTH] == "??":
            domains["untracked"].add(path)
        else:
            if each_status_line[0] != " ":
                domains["staged"].add(path)
            if each_status_line[1] != " ":
                domains["unstaged"].add(path)
    return domains


def _untracked_paths(root: Path, state_root: Path | None = None) -> list[str]:
    untracked_listing = _git(root, ALL_UNTRACKED_ARGUMENTS, is_required=True)
    all_paths = [each_path.decode(errors="surrogateescape") for each_path in untracked_listing.split(b"\0") if each_path]
    return [each_path for each_path in all_paths if state_root is None or not _is_inside_state_root(root, each_path, state_root)]


def _record_content(root: Path, merge_base: str, relative_path: str) -> tuple[bytes, str]:
    file_path = root / relative_path
    if file_path.is_symlink():
        content = b""
        identity = hashlib.sha256(os.readlink(file_path).encode()).hexdigest()
    elif file_path.is_file():
        content = file_path.read_bytes()
        identity = hashlib.sha256(content).hexdigest()
    else:
        content = _git(root, ["show", f"{merge_base}:{relative_path}"], is_required=True)
        identity = hashlib.sha256(content).hexdigest()
    return content, identity


def _annotate_record(root: Path, merge_base: str, relative_path: str, all_record: dict[str, object], all_domains: dict[str, set[str]]) -> None:
    content, identity = _record_content(root, merge_base, relative_path)
    lower_path = relative_path.lower()
    all_record.update({"domains": sorted([each_domain for each_domain, all_paths in all_domains.items() if relative_path in all_paths] + (["committed"] if all_record["status"] != "?" else [])), "operation_by_domain": {}, "content_sha256": identity, "binary": b"\0" in content, "added": 0, "deleted": 0, "package": _package_key(relative_path), "public_api": int(any(marker.lower() in lower_path for marker in ALL_PUBLIC_API_MARKERS)), "dependency": int(any(marker.lower() in lower_path for marker in ALL_DEPENDENCY_MARKERS)), "call_path": int(lower_path.endswith(ALL_SOURCE_SUFFIXES))})
    all_record["operation_by_domain"] = {each_domain: ("A" if all_record["status"] == "?" else all_record["status"]) for each_domain in all_record["domains"]}


def _effective_records(root: Path, merge_base: str, all_domains: dict[str, set[str]], state_root: Path | None = None) -> list[dict[str, object]]:
    status_bytes = _git(root, ["diff", "--name-status", "-z", merge_base, "--"], is_required=True)
    status_tokens = status_bytes.split(b"\0")
    records_by_path: dict[str, dict[str, object]] = {}
    all_untracked_paths = _untracked_paths(root, state_root)
    index = 0
    while index < len(status_tokens) - 1:
        status = status_tokens[index].decode(errors="surrogateescape")
        index += 1
        if not status:
            continue
        prior_path = None
        if status[0] in {"R", "C"}:
            prior_path = status_tokens[index].decode(errors="surrogateescape")
            index += 1
        current_path = status_tokens[index].decode(errors="surrogateescape")
        index += 1
        records_by_path[current_path] = {"path": current_path, "prior_path": prior_path, "status": status[0]}
    for each_path in all_untracked_paths:
        records_by_path.setdefault(each_path, {"path": each_path, "prior_path": None, "status": "?"})
    if state_root is not None:
        tracked_state_paths = [each_path for each_path in records_by_path if _is_inside_state_root(root, each_path, state_root) and records_by_path[each_path]["status"] != "?"]
        if tracked_state_paths:
            raise ValueError(ROUTING_STATE_ROOT_TRACKED)
        records_by_path = {each_path: record for each_path, record in records_by_path.items() if not _is_inside_state_root(root, each_path, state_root)}
    for each_path, each_record in records_by_path.items():
        _annotate_record(root, merge_base, each_path, each_record, all_domains)
    numstat = _git(root, ["diff", "--numstat", "-z", merge_base, "--"], is_required=True).split(b"\0")
    index = 0
    while index + 1 < len(numstat):
        fields = numstat[index].split(b"\t")
        index += 1
        if len(fields) < STATUS_CODE_LENGTH:
            continue
        if len(fields) == STATUS_CODE_LENGTH:
            if index >= len(numstat):
                continue
            path = numstat[index].decode(errors="surrogateescape")
            index += 1
        else:
            path = fields[2].decode(errors="surrogateescape")
        record = records_by_path.get(path)
        if record is None:
            continue
        record["added"] = int(fields[0]) if fields[0].isdigit() else 0
        record["deleted"] = int(fields[1]) if fields[1].isdigit() else 0
        record["binary"] = fields[0] == b"-" or fields[1] == b"-"
    for each_path in all_untracked_paths:
        record = records_by_path[each_path]
        content = (root / each_path).read_bytes() if (root / each_path).is_file() else b""
        if b"\0" not in content:
            record["added"] = content.count(b"\n")
    return [records_by_path[each_path] for each_path in sorted(records_by_path)]


def _committed_paths(root: Path, merge_base: str) -> set[str]:
    committed_paths = _git(root, ["diff", "--name-only", "-z", f"{merge_base}..{GIT_HEAD_REF}"], is_required=True).decode(errors="surrogateescape")
    return {path for path in committed_paths.split("\0") if path}


def _hard_triggers(all_paths: set[str]) -> list[str]:
    lower_paths = {path.lower() for path in all_paths}
    return [name for name, markers in ALL_HARD_TRIGGER_MARKERS.items() if any(marker in path for path in lower_paths for marker in markers)]


def inventory_generation(repo_root: str | Path, base_ref: str | None = None, state_root: str | Path | None = None) -> dict[str, object]:
    """Return one hashed inventory covering committed and working-tree changes.

    Args:
        repo_root: Repository to inspect.
        base_ref: Optional validated base reference.
    Returns:
        Canonical evidence and domain metadata.
    """
    root = Path(repo_root).resolve()
    state_root = Path(state_root).resolve() if state_root is not None else None
    head = _git(root, ["rev-parse", "--verify", GIT_HEAD_REF], is_required=True).decode().strip()
    requested_base, base = _resolve_base(root, base_ref)
    merge_base = _git(root, ["merge-base", base, head], is_required=True)
    merge_base = merge_base.decode().strip()
    domains = _status_domains(root, state_root=state_root)
    committed = _committed_paths(root, merge_base)
    all_paths = committed | set().union(*domains.values())
    records = _effective_records(root, merge_base, domains, state_root=state_root)
    packages = {str(record["package"]) for record in records}
    public_api = int(any(record["public_api"] for record in records))
    dependencies = int(any(record["dependency"] for record in records))
    triggers = _hard_triggers(all_paths)
    patch_bytes = _git(root, ["diff", "--binary", "--full-index", "--no-ext-diff", merge_base, "--"], is_required=True)
    untracked_identities = [{"path": each_path, "sha256": record["content_sha256"]} for each_path, record in ((record["path"], record) for record in records) if "untracked" in record["domains"]]
    base_source = "explicit" if base_ref else ("remote_default" if requested_base == REMOTE_HEAD_REF else "configured_fallback")
    canonical = json.dumps({"base_ref": requested_base, "base_source": base_source, "base_sha": base, "merge_base_sha": merge_base, "head_sha": head, "domains": {each_domain: sorted(all_paths) for each_domain, all_paths in domains.items()}, "files": records, "untracked_identities": sorted(untracked_identities, key=lambda record: record["path"])}, sort_keys=True, separators=(",", ":")).encode() + patch_bytes
    lines = sum(int(record["added"]) + int(record["deleted"]) for record in records)
    digest = hashlib.sha256(canonical).hexdigest()
    return {"paths": [record["path"] for record in records], "files_by_domain": records, "committed": sorted(committed), "staged": sorted(domains["staged"]), "unstaged": sorted(domains["unstaged"]), "untracked": sorted(domains["untracked"]), "base_ref": requested_base, "base_source": base_source, "base_sha": base, "merge_base_sha": merge_base, "head_sha": head, "merge_base": merge_base, "HEAD": head, "inventory_hash": digest, "diff_hash": digest, "files": len(records), "lines": lines, "packages": len(packages), "risk": MIN_NONEMPTY_RISK if records else 0, "public_api": public_api, "dependencies": dependencies, "hard_triggers": triggers}


def _package_key(path: str) -> str:
    parts = path.split("/")
    if len(parts) > 1 and parts[0] in ALL_PACKAGE_ROOT_NAMES:
        return PATH_SEPARATOR.join(parts[:2])
    return parts[0] if len(parts) > 1 else ROOT_PACKAGE


def build_generation(repo_root: str | Path, requested_override: str | None = None, card_path: str | Path | None = None, base_ref: str | None = None, all_policy: Mapping[str, object] | None = None, state_root: str | Path | None = None) -> dict[str, object]:
    """Build and optionally persist one immutable tier card.

    Args:
        repo_root: Repository to inspect.
        requested_override: Optional requested tier.
        card_path: Optional destination for the card.
        base_ref: Optional base reference.
        all_policy: Optional tier policy.
    Returns:
        The generated decision card.
    """
    inventory = inventory_generation(repo_root, base_ref=base_ref, state_root=state_root)
    card = build_decision(inventory, str(inventory["base_ref"]), str(inventory["HEAD"]), str(Path(repo_root).resolve()), str(inventory["inventory_hash"]), requested_override=requested_override, all_policy=all_policy)
    card["inventory_hash"] = inventory["inventory_hash"]
    if card_path is not None:
        destination = Path(card_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("x", encoding="utf-8") as card_file:
            json.dump(card, card_file, sort_keys=True, indent=JSON_INDENT)
            card_file.write("\n")
    return card


def load_policy() -> dict[str, object]:
    """Load and validate versioned tier policy data.

    Args:
    Returns:
        Parsed policy mapping.
    Raises:
        ValueError: If the policy schema is invalid.
    """
    policy_path = Path(__file__).parent.parent / "reference" / "tier-policy.json"
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    if policy.get("version") != 1 or tuple(policy.get("tiers", ())) != ALL_TIER_ORDER or set(policy.get("thresholds", {})) != set(ALL_TIER_ORDER):
        raise ValueError(MALFORMED_TIER_POLICY)
    return policy


def policy_hash(all_policy: Mapping[str, object]) -> str:
    """Return the stable policy digest used by decision records.

    Args:
        all_policy: Parsed tier policy.
    Returns:
        Stable SHA-256 digest.
    """
    return canonical_json_hash(all_policy)


def canonical_json_hash(all_record: Mapping[str, object]) -> str:
    """Return the stable SHA-256 digest for a JSON-compatible mapping.

    Args:
        all_record: Mapping to encode.
    Returns:
        Stable SHA-256 digest.
    """
    encoded_record = json.dumps(all_record, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded_record).hexdigest()


def calculate_tier(all_evidence: Mapping[str, object], all_policy: Mapping[str, object] | None = None) -> str:
    """Calculate a tier from six bounded axes and hard triggers.

    Args:
        all_evidence: Bounded change evidence.
        all_policy: Optional tier policy.
    Returns:
        Automatic tier identifier.
    """
    selected_policy = all_policy or load_policy()
    if set(all_evidence.get("hard_triggers", ())).intersection(selected_policy["hard_triggers"]):
        return "T3"
    score = sum(min(MAX_AXIS_VALUE, int(all_evidence.get(axis, 0))) * int(weight) for axis, weight in selected_policy["axis_weights"].items())
    if score >= selected_policy["thresholds"]["T3"]:
        return "T3"
    if score >= selected_policy["thresholds"]["T2"]:
        return "T2"
    return "T1"


def effective_tier(calculated_tier: str, requested_override: str | None, all_policy: Mapping[str, object] | None = None) -> str:
    """Apply an approved explicit tier override.

    Args:
        calculated_tier: Automatic tier.
        requested_override: Optional requested tier.
        all_policy: Optional tier policy.
    Returns:
        Effective tier identifier.
    Raises:
        ValueError: If either tier is invalid or the downgrade is unapproved.
    """
    selected_policy = all_policy or load_policy()
    if calculated_tier not in ALL_TIER_ORDER or requested_override not in (*ALL_TIER_ORDER, None):
        raise ValueError(UNKNOWN_TIER)
    if requested_override is None or requested_override == calculated_tier or requested_override > calculated_tier:
        return requested_override or calculated_tier
    if requested_override in selected_policy["approved_downgrades"]:
        return requested_override
    raise ValueError(UNAPPROVED_TIER_DOWNGRADE)


def build_decision(all_change: Mapping[str, object], base: str, commit: str, worktree: str, diff_hash: str, requested_override: str | None = None, all_policy: Mapping[str, object] | None = None) -> dict[str, object]:
    """Build a serializable tier card with evidence and policy identity.

    Args:
        all_change: Canonical inventory evidence.
        base: Resolved base reference.
        commit: Current HEAD.
        worktree: Repository path.
        diff_hash: Canonical evidence digest.
        requested_override: Optional requested tier.
    Returns:
        Serializable decision card.
    """
    selected_policy = all_policy or load_policy()
    calculated = calculate_tier(all_change, all_policy=selected_policy)
    return {"calculated_tier": calculated, "requested_override": requested_override, "effective_tier": effective_tier(calculated, requested_override, all_policy=selected_policy), "evidence": dict(all_change), "policy_hash": policy_hash(selected_policy), "base_ref": base, "base_source": all_change.get("base_source"), "merge_base": all_change.get("merge_base"), "HEAD": commit, "worktree": str(Path(worktree).resolve()), "diff_hash": diff_hash}
