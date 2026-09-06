"""Persist scoped user requirements and emit host-specific companion context."""

from __future__ import annotations

import argparse
import copy
import difflib
import hashlib
import json
import os
import re
import sqlite3
import sys
from pathlib import Path

HOSTS = ("claude", "codex", "cursor")
SCOPES = ("turn", "task", "session", "unspecified")
SKILL_DIRECTORY = Path(__file__).resolve().parent
DOCUMENT_LIMIT = 262144
SOURCE_LIMIT = 1048576
NAMES = ("poteto-mode", "pstack:poteto-mode")
PROMPT_EVENTS = ("UserPromptSubmit", "beforeSubmitPrompt")


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def encode(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)


def invocation(prompt: str, host: str) -> str | None:
    """Recognize a complete direct first-line directive, never embedded prose."""
    lines = [line for line in prompt.splitlines() if line.strip()]
    if not lines or lines[0].startswith(("    ", "\t")):
        return None
    line = lines[0].strip()
    names = r"(?:Poteto|Potato) Mode"
    duration = r"(?: for (?:this |the )?(?:entire )?(?:session|task|turn))?"
    natural = rf"(?:(?:Use|Activate|Enable|Apply) {names}{duration}|{names} applies{duration}|poteto)"
    prefix = r"\$" if host == "codex" else "/"
    command = rf"{prefix}(?:pstack:)?poteto-mode{duration}"
    if not re.fullmatch(rf"(?:{natural}|{command})[.!]?", line, re.IGNORECASE):
        return None
    scope = re.search(r"\b(session|task|turn)\b", line, re.IGNORECASE)
    return scope.group(1).lower() if scope else "unspecified"


def session_path(root: Path, host: str, session: str) -> Path:
    if host not in HOSTS or not isinstance(session, str) or not session.strip():
        raise ValueError("A native host session identity is required; no latest-session fallback exists.")
    if len(session) > 512 or "\x00" in session:
        raise ValueError("Invalid native session identity.")
    return root.resolve() / host / (digest(session) + ".sqlite3")


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    connection = sqlite3.connect(str(path), timeout=10, isolation_level=None)
    os.chmod(path, 0o600)
    connection.execute("CREATE TABLE IF NOT EXISTS revisions (revision INTEGER PRIMARY KEY, document TEXT NOT NULL)")
    connection.execute("CREATE TABLE IF NOT EXISTS sources (hash TEXT PRIMARY KEY, content TEXT NOT NULL)")
    return connection


def current(connection: sqlite3.Connection) -> dict | None:
    row = connection.execute("SELECT document FROM revisions ORDER BY revision DESC LIMIT 1").fetchone()
    return json.loads(row[0]) if row else None


def save(connection: sqlite3.Connection, record: dict) -> dict:
    previous = current(connection)
    record["revision"] = previous["revision"] + 1 if previous else 1
    text = encode(record)
    if len(text.encode("utf-8")) > DOCUMENT_LIMIT:
        raise ValueError("Continuity record exceeds 256 KiB; narrow completed requirements explicitly.")
    connection.execute("INSERT INTO revisions VALUES (?, ?)", (record["revision"], text))
    return current(connection)


def read_source(path: str) -> str:
    source = Path(path)
    if not source.is_absolute() or source.name != "SKILL.md":
        raise ValueError("A skill source must be an absolute SKILL.md path.")
    with source.open("r", encoding="utf-8") as stream:
        text = stream.read(SOURCE_LIMIT + 1)
    if len(text) > SOURCE_LIMIT:
        raise ValueError("Skill source exceeds the 1 MiB loading limit.")
    return text


def poteto_source(skills: Path, explicit: str | None) -> str:
    if explicit:
        source = Path(explicit).expanduser()
        if not source.is_absolute() or source.name != "SKILL.md":
            raise ValueError("--poteto-source requires an absolute SKILL.md path.")
        return str(source.resolve())
    paths = [skills / "pstack" / "poteto-mode" / "SKILL.md", skills / "pstack" / "skills" / "poteto-mode" / "SKILL.md"]
    found = {str(path.resolve()) for path in paths if path.is_file()}
    if len(found) > 1:
        raise ValueError("Two pstack Poteto sources exist. Select the host's actual source with --poteto-source.")
    return next(iter(found)) if found else str(paths[0].resolve())


def initial(host: str, session: str, cwd: str, source: str, scope: str) -> dict:
    return {
        "schema": 1, "host": host, "session_id": session, "project_at_activation": cwd,
        "active": True, "revision": 0, "acknowledged_revision": 0,
        "requirements": {"pstack:poteto-mode": {
            "kind": "skill", "name": "Poteto Mode", "source": source, "scope": scope,
            "duration": "User-specified scope" if scope != "unspecified" else "Resolve from the direct user request before dependent work",
        }},
        "task": {"goal": "", "boundaries": [], "constraints": [], "completion": []},
        "checkpoint": "Companion activated; reconcile the current user request.",
        "remaining": [], "user_evidence": {}, "accepted_sources": {}, "loaded": {},
    }


def evidence(record: dict, prompt: str) -> str:
    key = digest(prompt)
    record["user_evidence"][key] = {"text": prompt, "authority": "direct-user-message-evidence"}
    record["latest_user_event"] = key
    return key


def source_status(connection: sqlite3.Connection, record: dict) -> list[dict]:
    result = []
    paths = {str(SKILL_DIRECTORY / "SKILL.md")}
    paths.update(item["source"] for item in record["requirements"].values() if item["kind"] == "skill")
    for path in sorted(paths):
        accepted = record["accepted_sources"].get(path)
        try:
            content = read_source(path)
        except (OSError, UnicodeError, ValueError) as error:
            result.append({"path": path, "state": "unavailable", "error": str(error)})
            continue
        observed = digest(content)
        state = "changed" if accepted and accepted != observed else "available"
        entry = {"path": path, "state": state, "accepted_sha256": accepted, "sha256": observed, "content": content}
        if state == "changed":
            old = connection.execute("SELECT content FROM sources WHERE hash = ?", (accepted,)).fetchone()
            entry["difference"] = "".join(difflib.unified_diff(
                old[0].splitlines(True) if old else [], content.splitlines(True),
                fromfile="accepted source", tofile="current source",
            ))
        result.append(entry)
    return result


def companion_context(path: Path, record: dict) -> str:
    skill = read_source(str(SKILL_DIRECTORY / "SKILL.md"))
    command = encode([sys.executable, str(Path(__file__).resolve()), "--host", record["host"],
                      "--session", record["session_id"], "--state-root", str(path.parent.parent)])
    return (
        "SESSION CONTINUITY. The following body is loaded from " + str(SKILL_DIRECTORY / "SKILL.md")
        + ". It accompanies Poteto Mode; its source and invocation are unchanged.\n" + skill
        + "\nExact durable record: " + str(path)
        + "\nReadback after transaction commit:\n" + encode(record)
        + "\nRuntime argv prefix, append the action. Use your host shell's quoting for each argument:\n" + command
        + "\nRun load now, read its complete output, reconcile direct user instructions, and acknowledge before dependent work."
    )


def hook(args: argparse.Namespace, payload: dict) -> dict:
    event = payload.get("hook_event_name", "")
    allowed = {"claude": {"UserPromptSubmit", "UserPromptExpansion", "SessionStart"},
               "codex": {"UserPromptSubmit", "SessionStart"},
               "cursor": {"beforeSubmitPrompt", "sessionStart", "preToolUse", "preCompact"}}
    if event not in allowed[args.host] or payload.get("agent_id"):
        return {}
    session = payload.get("conversation_id" if args.host == "cursor" else "session_id")
    path = session_path(args.state_root, args.host, session)
    prompt = payload.get("prompt", "") if event in PROMPT_EVENTS or event == "UserPromptExpansion" else ""
    if not isinstance(prompt, str):
        raise ValueError("The host prompt must be a string.")
    scope = invocation(prompt, args.host) if event in PROMPT_EVENTS else None
    if args.host == "claude" and event == "UserPromptSubmit" and prompt.lstrip().startswith("/"):
        scope = None
    if event == "UserPromptExpansion":
        if payload.get("expansion_type") != "slash_command" or payload.get("command_name") not in NAMES:
            return {}
        scope = invocation("/poteto-mode " + payload.get("command_args", ""), "claude") or "unspecified"
    deactivate = event in PROMPT_EVENTS and prompt.strip().lower().rstrip(".") == "deactivate session continuity"
    if not path.exists() and scope is None:
        return {}
    connection = connect(path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        record = current(connection)
        if scope is not None and (record is None or not record["active"]):
            record = initial(args.host, session, payload.get("cwd", ""),
                             poteto_source(args.skills_root, args.poteto_source), scope)
        if record is None:
            return {}
        if deactivate:
            record["active"] = False
            evidence(record, prompt)
        elif not record["active"]:
            return {}
        elif scope is not None:
            key = evidence(record, prompt)
            requirement = record["requirements"].setdefault("pstack:poteto-mode", {
                "kind": "skill", "name": "Poteto Mode", "source": poteto_source(args.skills_root, args.poteto_source),
                "scope": scope, "duration": "Resolve from the direct user request before dependent work",
            })
            requirement["user_event"] = key
            if scope != "unspecified":
                requirement["scope"] = scope
                requirement["duration"] = prompt.strip().splitlines()[0]
        elif event in PROMPT_EVENTS:
            evidence(record, prompt)
        record["acknowledged_revision"] = 0
        if event == "preToolUse":
            if record.get("cursor_context_delivered"):
                connection.execute("ROLLBACK")
                return {}
            record["cursor_context_delivered"] = True
        else:
            record["cursor_context_delivered"] = False
        record = save(connection, record)
        connection.execute("COMMIT")
        record = current(connection)
    finally:
        connection.close()
    if deactivate:
        message = "Session continuity deactivated. Poteto Mode is unchanged. Record: " + str(path)
        return {"continue": True} if args.host == "cursor" else {"systemMessage": message}
    if event in ("beforeSubmitPrompt", "preCompact"):
        return {"continue": True} if event == "beforeSubmitPrompt" else {}
    context = companion_context(path, record)
    notice = "Session-continuity record: " + str(path)
    if args.host == "cursor":
        if event == "preToolUse":
            return {"permission": "deny", "user_message": notice, "agent_message": context}
        return {"additional_context": context}
    return {"systemMessage": notice, "hookSpecificOutput": {"hookEventName": event, "additionalContext": context}}


def validate_update(record: dict, changes: dict) -> None:
    allowed = {"expected_revision", "user_event", "requirements", "task", "checkpoint", "remaining"}
    if set(changes) - allowed:
        raise ValueError("Unknown update fields.")
    if changes.get("expected_revision") != record["revision"]:
        raise ValueError("Revision conflict. Reload and reconcile the newer direct user instructions.")
    user_event = changes.get("user_event")
    if user_event not in record["user_evidence"]:
        raise ValueError("An update needs an existing direct-user evidence id.")
    requirements = changes.get("requirements", record["requirements"])
    if not isinstance(requirements, dict):
        raise ValueError("Requirements must be an object keyed by stable requirement ids.")
    for key, item in requirements.items():
        if not isinstance(key, str) or not key or not isinstance(item, dict):
            raise ValueError("Invalid requirement.")
        if item.get("scope") not in SCOPES or not isinstance(item.get("duration"), str):
            raise ValueError("Every requirement needs its actual scope and duration.")
        if item.get("kind") not in ("skill", "rule"):
            raise ValueError("Requirement kind must be skill or rule.")
        if item["kind"] == "skill":
            source = Path(item.get("source", ""))
            if not source.is_absolute() or source.name != "SKILL.md":
                raise ValueError("Skills need absolute authoritative SKILL.md locations.")
        elif not isinstance(item.get("text"), str) or not item["text"].strip():
            raise ValueError("A rule needs its user-authorized text.")
    if "task" in changes:
        task = changes["task"]
        if not isinstance(task, dict) or set(task) != {"goal", "boundaries", "constraints", "completion"}:
            raise ValueError("Task needs goal, boundaries, constraints, and completion.")
        if not isinstance(task["goal"], str) or any(not isinstance(task[key], list) for key in ("boundaries", "constraints", "completion")):
            raise ValueError("Invalid task fields.")
    if "checkpoint" in changes and not isinstance(changes["checkpoint"], str):
        raise ValueError("Checkpoint must be text.")
    if "remaining" in changes and not isinstance(changes["remaining"], list):
        raise ValueError("Remaining work must be a list.")


def operation(args: argparse.Namespace) -> dict:
    path = session_path(args.state_root, args.host, args.session)
    if not path.exists():
        raise ValueError("No record for this native session. Invoke Poteto Mode through a configured companion hook.")
    connection = connect(path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        record = current(connection)
        if record is None:
            raise ValueError("Empty continuity record.")
        if args.action == "show":
            return {"path": str(path), "record": record}
        if not record["active"]:
            raise ValueError("Record is deactivated. Only a new explicit invocation reactivates it.")
        data = json.loads(args.data) if args.data else {}
        if args.action == "load":
            sources = source_status(connection, record)
            loaded = {source["path"]: source["sha256"] for source in sources if source["state"] != "unavailable"}
            record["loaded"] = loaded
            record["acknowledged_revision"] = 0
            record = save(connection, record)
            connection.execute("COMMIT")
            record = current(connection)
            return {"path": str(path), "record": record, "sources": sources,
                    "instruction": "Read every complete source. Unavailable sources block dependent work. Report changed source differences before acknowledgement."}
        if args.action == "update":
            validate_update(record, data)
            for key in ("requirements", "task", "checkpoint", "remaining"):
                if key in data:
                    record[key] = data[key]
            record["last_update_user_event"] = data["user_event"]
            record["loaded"] = {}
            record["acknowledged_revision"] = 0
        elif args.action == "acknowledge":
            if data.get("expected_revision") != record["revision"]:
                raise ValueError("Revision conflict. Load the current record again.")
            sources = source_status(connection, record)
            for source in sources:
                if source["state"] == "unavailable":
                    raise ValueError("Unavailable skill source: " + source["path"])
                if record["loaded"].get(source["path"]) != source["sha256"]:
                    raise ValueError("Source has not been loaded at its current hash: " + source["path"])
                if source["state"] == "changed" and source["path"] not in data.get("accept_changed_sources", []):
                    raise ValueError("Report and explicitly accept changed source: " + source["path"])
                connection.execute("INSERT OR IGNORE INTO sources VALUES (?, ?)", (source["sha256"], source["content"]))
                record["accepted_sources"][source["path"]] = source["sha256"]
            record["acknowledged_revision"] = record["revision"] + 1
        elif args.action == "deactivate":
            record["active"] = False
        elif args.action == "handoff":
            target = session_path(args.state_root, args.target_host, args.target_session)
            if target.exists():
                raise ValueError("Handoff target already has a record; explicit reconciliation is required.")
            target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            descriptor = os.open(str(target), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(descriptor)
            destination = connect(target)
            try:
                transferred = copy.deepcopy(record)
                transferred.update(host=args.target_host, session_id=args.target_session, revision=0,
                                   acknowledged_revision=0, loaded={}, cursor_context_delivered=False,
                                   handoff_from={"host": args.host, "session_id": args.session})
                destination.execute("BEGIN IMMEDIATE")
                for source_hash, content in connection.execute("SELECT hash, content FROM sources"):
                    destination.execute("INSERT OR IGNORE INTO sources VALUES (?, ?)", (source_hash, content))
                transferred = save(destination, transferred)
                destination.execute("COMMIT")
                transferred = current(destination)
            finally:
                destination.close()
            return {"path": str(target), "record": transferred, "origin_unchanged": True}
        record = save(connection, record)
        connection.execute("COMMIT")
        record = current(connection)
        return {"path": str(path), "record": record}
    finally:
        connection.close()


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", choices=HOSTS, required=True)
    parser.add_argument("--session")
    parser.add_argument("--state-root", type=Path, default=SKILL_DIRECTORY.parents[1] / "session-continuity")
    parser.add_argument("--skills-root", type=Path, default=SKILL_DIRECTORY.parent)
    parser.add_argument("--poteto-source")
    parser.add_argument("--data")
    parser.add_argument("--target-host", choices=HOSTS)
    parser.add_argument("--target-session")
    parser.add_argument("action", choices=("hook", "show", "load", "update", "acknowledge", "deactivate", "handoff"))
    return parser.parse_args()


def main() -> int:
    args = arguments()
    try:
        if args.action == "hook":
            text = sys.stdin.read(DOCUMENT_LIMIT + 1)
            if len(text) > DOCUMENT_LIMIT:
                raise ValueError("Hook input exceeds 256 KiB.")
            payload = json.loads(text)
            if not isinstance(payload, dict):
                raise ValueError("Hook input must be one JSON object.")
            result = hook(args, payload)
        else:
            result = operation(args)
        print(encode(result))
        return 0
    except (OSError, ValueError, TypeError, KeyError, sqlite3.Error) as error:
        message = "Session continuity unavailable: " + str(error)
        if args.action == "hook":
            print(encode({"user_message": message} if args.host == "cursor" else {"systemMessage": message}))
            print(message, file=sys.stderr)
            return 0
        print(message, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
