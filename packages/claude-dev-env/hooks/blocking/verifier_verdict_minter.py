"""SubagentStop hook: mint a commit-gate verdict when code-verifier finishes.

Only this hook writes verdict files — the main session is denied writes to
the verdict directory, so a session cannot fabricate a passing verdict. The
SubagentStop payload names the stopping subagent by ``agent_id``. The hook
recovers the spawning agent type from the parent transcript
(``transcript_path``), where the agent's completion record carries its
identity as sibling ``agentId`` and ``agentType`` keys. When that type is
``code-verifier``, the hook pulls the verdict block out of the agent's own
transcript — the payload key ``agent_transcript_path``; the parent
``transcript_path`` supplies only the spawning type and never the verdict, so
text printed by the main session can never mint — recomputes the live
change-surface hash for the session
repository, and writes the verdict bound to that hash. The companion
``verified_commit_gate.py`` (PreToolUse) then allows ``git commit`` /
``git push`` only while the work tree still matches the verified state.

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
import time
from pathlib import Path

blocking_directory = str(Path(__file__).resolve().parent)
if blocking_directory not in sys.path:
    sys.path.insert(0, blocking_directory)

from config.verified_commit_constants import (
    MINTING_AGENT_TYPE,
    SPAWN_LOOKUP_ATTEMPT_COUNT,
    SPAWN_LOOKUP_RETRY_DELAY_SECONDS,
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


def _transcript_entries(transcript_path: str) -> list[dict]:
    """Parse every JSON object line of a transcript file.

    Args:
        transcript_path: Path to the parent session transcript.

    Returns:
        Each parseable object entry in transcript order; empty when the
        file is missing or holds no object lines.
    """
    parsed_entries: list[dict] = []
    try:
        transcript_lines = (
            Path(transcript_path).read_text(encoding="utf-8", errors="replace").splitlines()
        )
    except OSError:
        return parsed_entries
    for each_line in transcript_lines:
        try:
            transcript_entry = json.loads(each_line)
        except json.JSONDecodeError:
            continue
        if isinstance(transcript_entry, dict):
            parsed_entries.append(transcript_entry)
    return parsed_entries


def _agent_type_in_node(transcript_node: object, agent_id: str) -> str | None:
    """Search one parsed transcript value for a spawn record naming an agent.

    Walks a transcript value and its nested mappings and sequences for a
    mapping whose ``agentId`` equals the stopping agent and whose
    ``agentType`` is a string. Only a structured ``agentType`` key counts, so
    a main-session text block that merely quotes the words cannot match.

    Args:
        transcript_node: A JSON value drawn from a parsed transcript entry.
        agent_id: The stopping subagent's id from the payload.

    Returns:
        The ``agentType`` of the matching mapping, or None when no nested
        value names this agent.
    """
    if isinstance(transcript_node, dict):
        recorded_type = transcript_node.get("agentType")
        if transcript_node.get("agentId") == agent_id and isinstance(recorded_type, str):
            return recorded_type
        for each_value in transcript_node.values():
            nested_type = _agent_type_in_node(each_value, agent_id)
            if nested_type is not None:
                return nested_type
        return None
    if isinstance(transcript_node, list):
        for each_item in transcript_node:
            nested_type = _agent_type_in_node(each_item, agent_id)
            if nested_type is not None:
                return nested_type
    return None


def _agent_type_from_entries(all_entries: list[dict], agent_id: str) -> str | None:
    """Find the spawn record naming an agent across parent-transcript entries.

    Args:
        all_entries: Parsed parent-transcript entries.
        agent_id: The stopping subagent's id from the payload.

    Returns:
        The ``agentType`` recorded for the agent, or None when no entry's
        spawn record names it.
    """
    for each_entry in all_entries:
        recorded_type = _agent_type_in_node(each_entry, agent_id)
        if recorded_type is not None:
            return recorded_type
    return None


def _resolve_agent_type_with_retry(transcript_path: str, agent_id: str) -> str | None:
    """Read the parent transcript and resolve the agent's type, with retry.

    The agent's completion record is not reliably flushed to the parent
    transcript at the instant SubagentStop fires, so a single read can miss it
    and silently mint nothing. Each attempt re-reads the transcript; a bounded
    sleep separates attempts so a late-arriving record resolves on a later read.

    Args:
        transcript_path: Path to the parent session transcript.
        agent_id: The stopping subagent's id from the payload.

    Returns:
        The recorded ``agentType``, or None when no attempt finds the spawn
        record naming this agent.
    """
    for each_attempt_index in range(SPAWN_LOOKUP_ATTEMPT_COUNT):
        all_entries = _transcript_entries(transcript_path)
        recorded_type = _agent_type_from_entries(all_entries, agent_id)
        if recorded_type is not None:
            return recorded_type
        if each_attempt_index < SPAWN_LOOKUP_ATTEMPT_COUNT - 1:
            time.sleep(SPAWN_LOOKUP_RETRY_DELAY_SECONDS)
    return None


def resolved_subagent_type(subagent_stop_payload: dict) -> str | None:
    """Recover the spawning agent type for a SubagentStop payload.

    The payload names the stopping subagent by ``agent_id``. Its spawn type
    lives on the agent's completion record in the parent transcript, attached
    as sibling ``agentId`` and ``agentType`` keys, so the type is read from
    that record. The read retries because the record may not be flushed at the
    instant the hook fires.

    Args:
        subagent_stop_payload: The SubagentStop hook payload.

    Returns:
        The agent type this subagent was spawned with, or None when the agent
        id is absent or no spawn record names its type.
    """
    agent_id = subagent_stop_payload.get("agent_id", "")
    if not agent_id:
        return None
    return _resolve_agent_type_with_retry(
        subagent_stop_payload.get("transcript_path", ""), agent_id
    )


def mint_for_payload(subagent_stop_payload: dict) -> Path | None:
    """Mint a verdict file for a code-verifier stop event.

    Args:
        subagent_stop_payload: The SubagentStop hook payload.

    Returns:
        The verdict file path when minted; None when the payload is not a
        code-verifier stop, the transcript holds no verdict, or the
        session directory is not a work tree with an upstream base.
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
    merge_base_sha = resolve_merge_base(repo_root)
    if merge_base_sha is None:
        return None
    surface_manifest_text = branch_surface_manifest(repo_root, merge_base_sha)
    if surface_manifest_text is None:
        return None
    return write_verdict(
        repo_root,
        manifest_sha256(surface_manifest_text),
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
