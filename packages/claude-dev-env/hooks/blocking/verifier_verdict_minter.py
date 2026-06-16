"""SubagentStop hook: mint a commit-gate verdict when code-verifier finishes.

Only this hook writes verdict files — the main session is denied writes to
the verdict directory, so a session cannot fabricate a passing verdict. The
SubagentStop payload names the stopping subagent's own transcript
(``agent_transcript_path``), which sits beside a harness-written
``agent-<id>.meta.json`` sidecar naming the spawning ``agentType``. The hook
reads that type from the sidecar, so it resolves identically in interactive,
background, and worktree-switched sessions. When that type is
``code-verifier``, the hook pulls the verdict block out of the agent's own
transcript (``agent_transcript_path``); the main session writes neither that
transcript nor the sidecar, so text it prints can never mint — recomputes the
live change-surface hash for the session repository, and writes the verdict
bound to that hash. The companion ``verified_commit_gate.py`` (PreToolUse)
then allows ``git commit`` / ``git push`` only while the work tree still
matches the verified state.

The verifier's final message must end with a fenced block::

    ```verdict
    {"all_pass": true, "findings": []}
    ```

A missing or unparseable block mints nothing, which leaves the gate closed.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

blocking_directory = str(Path(__file__).resolve().parent)
if blocking_directory not in sys.path:
    sys.path.insert(0, blocking_directory)

from config.verified_commit_constants import (
    MINTING_AGENT_TYPE,
    VERDICT_KEY_MANIFEST_SHA256,
)
from verification_verdict_store import (
    branch_surface_manifest,
    manifest_sha256,
    resolve_merge_base,
    resolve_repo_root,
    write_verdict,
)


def assistant_text_blocks(transcript_path: str) -> list[str]:
    """Collect every assistant text block from a transcript JSONL file.

    Args:
        transcript_path: Path to the subagent's transcript.

    Returns:
        The text of each assistant content block, in transcript order;
        empty when the file is missing or holds no assistant text.
    """
    collected_blocks: list[str] = []
    try:
        transcript_lines = (
            Path(transcript_path).read_text(encoding="utf-8", errors="replace").splitlines()
        )
    except OSError:
        return collected_blocks
    for each_line in transcript_lines:
        try:
            transcript_entry = json.loads(each_line)
        except json.JSONDecodeError:
            continue
        if not isinstance(transcript_entry, dict):
            continue
        if transcript_entry.get("type") != "assistant":
            continue
        message_body = transcript_entry.get("message")
        if not isinstance(message_body, dict):
            continue
        content_blocks = message_body.get("content")
        if not isinstance(content_blocks, list):
            continue
        for each_block in content_blocks:
            if isinstance(each_block, dict) and each_block.get("type") == "text":
                block_text = each_block.get("text")
                if isinstance(block_text, str):
                    collected_blocks.append(block_text)
    return collected_blocks


def last_verdict_in_blocks(all_text_blocks: list[str]) -> dict | None:
    """Extract the final verdict fence from assistant text blocks.

    Args:
        all_text_blocks: Assistant text blocks in transcript order.

    Returns:
        The parsed verdict mapping carrying a boolean ``all_pass`` and a
        list ``findings``, or None when no block holds a wellformed fence.
    """
    verdict_fence_pattern = re.compile(r"```verdict\s*\n(.*?)```", re.DOTALL)
    fence_bodies: list[str] = []
    for each_block in all_text_blocks:
        fence_bodies.extend(verdict_fence_pattern.findall(each_block))
    for each_fence_body in reversed(fence_bodies):
        try:
            verdict_record = json.loads(each_fence_body)
        except json.JSONDecodeError:
            continue
        if not isinstance(verdict_record, dict):
            continue
        if not isinstance(verdict_record.get("all_pass"), bool):
            continue
        if not isinstance(verdict_record.get("findings"), list):
            continue
        return verdict_record
    return None


def _agent_type_from_meta_sidecar(agent_transcript_path: str) -> str | None:
    """Read the spawning agentType from a subagent transcript's sidecar.

    Each subagent transcript ``agent-<id>.jsonl`` sits beside a harness-written
    ``agent-<id>.meta.json`` naming the spawning ``agentType``. Reading the type
    from this sidecar binds it to the stopping subagent itself, so it resolves
    identically in interactive, background, and worktree-switched sessions and
    needs no parent-transcript scan or flush retry.

    Args:
        agent_transcript_path: The stopping subagent's own transcript path from
            the SubagentStop payload.

    Returns:
        The recorded ``agentType``, or None when the path is empty, the sidecar
        is absent or cannot be read or parsed, it does not hold a JSON object,
        or it names no string ``agentType``.
    """
    if not agent_transcript_path:
        return None
    transcript_file = Path(agent_transcript_path)
    sidecar_file = transcript_file.with_name(f"{transcript_file.stem}.meta.json")
    try:
        sidecar_record = json.loads(sidecar_file.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(sidecar_record, dict):
        return None
    recorded_type = sidecar_record.get("agentType")
    return recorded_type if isinstance(recorded_type, str) else None


def resolved_subagent_type(subagent_stop_payload: dict) -> str | None:
    """Recover the spawning agent type for a SubagentStop payload.

    The stopping subagent's own transcript (``agent_transcript_path``) sits
    beside a harness-written ``agent-<id>.meta.json`` sidecar naming its
    ``agentType``. Reading the type from that sidecar binds it to the subagent
    itself, so it resolves the same across interactive, background, and
    worktree-switched sessions.

    Args:
        subagent_stop_payload: The SubagentStop hook payload.

    Returns:
        The agent type this subagent was spawned with, or None when the
        ``agent_transcript_path`` is empty, the sidecar is absent or cannot be
        read or parsed, it does not hold a JSON object, or it names no string
        ``agentType``.
    """
    return _agent_type_from_meta_sidecar(
        subagent_stop_payload.get("agent_transcript_path", "")
    )


def _attested_or_recomputed_hash(verdict_record: dict, repo_root: str) -> str | None:
    """Choose the surface hash the minted verdict binds to.

    A code-verifier that verifies a work tree other than the stop event's cwd
    attests the surface it checked by emitting ``manifest_sha256`` in its
    verdict fence (computed against the verified work tree via the
    ``--manifest-hash`` CLI). Binding the minted verdict to that attested hash
    keeps the verdict tied to the code actually verified rather than the
    subagent's cwd, so a verdict earned for one work tree clears a commit in a
    sibling work tree of the same surface. When the fence attests no hash, the
    minter recomputes one from the cwd work tree, which is correct whenever the
    verifier ran in the work tree it verified.

    Args:
        verdict_record: The parsed verdict fence from the verifier transcript.
        repo_root: The work-tree root resolved from the stop event's cwd, used
            for the recompute fallback.

    Returns:
        The attested ``manifest_sha256`` when the fence carries a non-empty
        string one; otherwise the cwd work tree's recomputed surface hash, or
        None when no upstream base or surface manifest resolves for it.
    """
    attested_manifest_sha256 = verdict_record.get(VERDICT_KEY_MANIFEST_SHA256)
    if isinstance(attested_manifest_sha256, str) and attested_manifest_sha256:
        return attested_manifest_sha256
    merge_base_sha = resolve_merge_base(repo_root)
    if merge_base_sha is None:
        return None
    surface_manifest_text = branch_surface_manifest(repo_root, merge_base_sha)
    if surface_manifest_text is None:
        return None
    return manifest_sha256(surface_manifest_text)


def mint_for_payload(subagent_stop_payload: dict) -> Path | None:
    """Mint a verdict file for a code-verifier stop event.

    Args:
        subagent_stop_payload: The SubagentStop hook payload.

    Returns:
        The verdict file path when minted; None when the payload is not a
        code-verifier stop, the transcript holds no verdict, the cwd is not a
        work tree, or — for a verdict that attests no ``manifest_sha256`` of
        its own — that work tree has no upstream base to recompute the surface
        hash from.
    """
    if resolved_subagent_type(subagent_stop_payload) != MINTING_AGENT_TYPE:
        return None
    agent_transcript_path = subagent_stop_payload.get("agent_transcript_path", "")
    if not agent_transcript_path:
        return None
    verdict_record = last_verdict_in_blocks(assistant_text_blocks(agent_transcript_path))
    if verdict_record is None:
        return None
    repo_root = resolve_repo_root(subagent_stop_payload.get("cwd", "."))
    if repo_root is None:
        return None
    bound_manifest_sha256 = _attested_or_recomputed_hash(verdict_record, repo_root)
    if bound_manifest_sha256 is None:
        return None
    return write_verdict(
        repo_root,
        bound_manifest_sha256,
        verdict_record["all_pass"],
        verdict_record["findings"],
        str(subagent_stop_payload.get("agent_id", "")),
    )


def main() -> None:
    """Read the SubagentStop payload and mint a verdict when one applies."""
    try:
        subagent_stop_payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return
    if not isinstance(subagent_stop_payload, dict):
        return
    mint_for_payload(subagent_stop_payload)


if __name__ == "__main__":
    main()
