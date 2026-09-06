"""Install only the session-continuity hook entries in existing host settings."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

from session_continuity import SKILL_DIRECTORY, encode, poteto_source, read_source


def atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".session-continuity-", dir=str(path.parent))
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(encode(value) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def command_for(host: str, source: str, state_root: Path) -> str:
    arguments = [sys.executable, str(SKILL_DIRECTORY / "session_continuity.py"),
                 "--host", host, "--poteto-source", source, "--state-root", str(state_root.resolve()), "hook"]
    return subprocess.list2cmdline(arguments) if os.name == "nt" else " ".join(shlex.quote(part) for part in arguments)


def entries(host: str, command: str) -> dict:
    events = {"claude": ("UserPromptSubmit", "UserPromptExpansion", "SessionStart"),
              "codex": ("UserPromptSubmit", "SessionStart"),
              "cursor": ("beforeSubmitPrompt", "sessionStart", "preToolUse", "preCompact")}[host]
    if host == "cursor":
        return {event: [{"command": command}] for event in events}
    result = {}
    for event in events:
        handler = {"type": "command", "command": command, "timeout": 15}
        if host == "codex":
            handler["additionalContextLimit"] = 12000
        group = {"hooks": [handler]}
        if event == "UserPromptExpansion":
            group["matcher"] = "^(pstack:)?poteto-mode$"
        result[event] = [group]
    return result


def merge(configuration: dict, additions: dict, previous_commands: list[str], host: str) -> dict:
    hooks = configuration.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise ValueError("Existing hooks must be a JSON object.")
    for event, groups in list(hooks.items()):
        retained = []
        for group in groups:
            if host == "cursor":
                if group.get("command") not in previous_commands:
                    retained.append(group)
            else:
                handlers = [handler for handler in group.get("hooks", []) if handler.get("command") not in previous_commands]
                if handlers:
                    retained.append({**group, "hooks": handlers})
        if retained:
            hooks[event] = retained
        else:
            del hooks[event]
    for event, groups in additions.items():
        hooks.setdefault(event, []).extend(groups)
    if host == "cursor":
        if configuration.get("version", 1) != 1:
            raise ValueError("Cursor hooks config version must be 1.")
        configuration["version"] = 1
    return configuration


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hosts", default="claude,codex,cursor")
    parser.add_argument("--claude-home", type=Path, default=Path(os.environ.get("CLAUDE_CONFIG_DIR", str(Path.home() / ".claude"))))
    parser.add_argument("--codex-home", type=Path, default=Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))))
    parser.add_argument("--cursor-home", type=Path, default=Path.home() / ".cursor")
    parser.add_argument("--poteto-source")
    parser.add_argument("--state-root", type=Path, default=SKILL_DIRECTORY.parents[1] / "session-continuity")
    parser.add_argument("--remove", action="store_true")
    args = parser.parse_args()
    hosts = args.hosts.split(",")
    if not set(hosts) <= {"claude", "codex", "cursor"}:
        parser.error("--hosts accepts claude,codex,cursor")
    source = poteto_source(SKILL_DIRECTORY.parent, args.poteto_source)
    if not args.remove:
        read_source(source)
    manifest_path = args.state_root.resolve() / "installation.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    destinations = {"claude": args.claude_home / "settings.json", "codex": args.codex_home / "hooks.json", "cursor": args.cursor_home / "hooks.json"}
    for host in hosts:
        path = destinations[host].expanduser().resolve()
        key = str(path)
        command = command_for(host, source, args.state_root)
        prior = manifest.get(key, [])
        configuration = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        if not isinstance(configuration, dict):
            raise ValueError("Existing host configuration must be a JSON object: " + key)
        updated = merge(configuration, {} if args.remove else entries(host, command), list(set(prior + [command])), host)
        atomic_json(path, updated)
        manifest[key] = [] if args.remove else [command]
        atomic_json(manifest_path, manifest)
        print(encode({"host": host, "path": key, "readback": json.loads(path.read_text(encoding="utf-8"))}))
    if not args.remove:
        print("Review and trust the installed hooks in each host. Codex requires /hooks trust review.")
        print("Cursor uses first-tool feedback. Prompt-only and Custom Mode selection activation remain unsupported.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError) as error:
        print("Session-continuity installation failed: " + str(error), file=sys.stderr)
        raise SystemExit(1)
