#!/usr/bin/env python3
"""Groq-powered PR bug auditor and auto-fixer.

Single-pass adaptation of the ``bugteam`` skill that replaces the multi-agent
orchestration with direct calls to Groq's chat completions API. No orchestrated
team, no 10-loop convergence: one audit call, one fix call, one commit and
push per PR.

Stateless and PII-free. All GitHub identifiers arrive on stdin as JSON;
``GROQ_API_KEY`` is read from the environment after loading
``packages/claude-dev-env/.env`` when that file exists (gitignored; see
``.env.example``). Output is JSON on stdout.

Pipeline (per invocation):
  1. Read PR metadata, unified diff, file contents from stdin.
  2. Call Groq with the audit prompt. Parse findings as JSON.
  3. For each finding, call Groq with the fix prompt. Parse a file patch.
  4. Write patched files to the worktree, stage, commit, push.
  5. Emit JSON: findings, fix outcomes, commit sha, review body.

The caller is responsible for PR review posting -- this script emits a
``review_body`` string but does not talk to the GitHub API.

Stdin schema::

    {
      "pr_number": int,
      "owner": str,
      "repo": str,
      "base_ref": str,
      "head_ref": str,
      "diff": str,                    # unified diff text
      "files_content": {path: str},   # current content of each file in diff
      "worktree_path": str,           # absolute path to a worktree on head_ref
      "apply_fixes": bool             # default true
    }

Stdout schema::

    {
      "findings": [ {severity, category, file, line, title, description}, ... ],
      "fix_outcomes": [ {finding_index, status, reason?}, ... ],
      "commit_sha": str,
      "review_body": str,
      "audit_model": str,
      "fix_model": str,
      "error": str                   # only on hard failure
    }
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

from config.groq_bugteam_config import (
    AUDIT_SYSTEM_PROMPT,
    FIX_SYSTEM_PROMPT,
    GROQ_API_ENDPOINT,
    GROQ_AUDIT_MAX_COMPLETION_TOKENS,
    GROQ_AUDIT_TEMPERATURE,
    GROQ_FALLBACK_MODEL,
    GROQ_FIX_MAX_COMPLETION_TOKENS,
    GROQ_FIX_TEMPERATURE,
    GROQ_PRIMARY_MODEL,
    GROQ_REQUEST_TIMEOUT_SECONDS,
    GROQ_RETRY_BACKOFF_SECONDS,
    JSON_INDENT_SPACES,
    MAXIMUM_DIFF_CHARACTERS,
    MAXIMUM_FILE_CONTENT_CHARACTERS,
    MAXIMUM_FINDINGS_PER_PR,
    MISSING_API_KEY_ERROR,
    NO_FINDINGS_REVIEW_BODY,
    PIPELINE_FAILURE_EXIT_CODE,
    REVIEW_BODY_HEADER_TEMPLATE,
    TEXT_CLAMP_HEAD_PARTS,
    TEXT_CLAMP_TOTAL_PARTS,
)

from groq_bugteam_dotenv import load_claude_dev_env_dotenv_file


@dataclass(frozen=True)
class GroqCallResult:
    content: str
    model: str


def is_recoverable_http_error(error: urllib.error.HTTPError) -> bool:
    return error.code in (408, 429, 500, 502, 503, 504)


def should_skip_to_next_model(error: urllib.error.HTTPError) -> bool:
    return error.code == 413


def clamp_text(text: str, max_characters: int) -> str:
    if len(text) <= max_characters:
        return text
    truncated_count = len(text)
    while True:
        truncation_marker = f"\n\n... [truncated {truncated_count} chars] ...\n\n"
        if len(truncation_marker) >= max_characters:
            return text[:max_characters]
        content_budget = max_characters - len(truncation_marker)
        refined_truncated_count = len(text) - content_budget
        if refined_truncated_count == truncated_count:
            break
        truncated_count = refined_truncated_count
    head_length = content_budget * TEXT_CLAMP_HEAD_PARTS // TEXT_CLAMP_TOTAL_PARTS
    tail_length = content_budget - head_length
    head = text[:head_length]
    tail = text[-tail_length:] if tail_length else ""
    return f"{head}{truncation_marker}{tail}"


def post_to_groq(
    api_key: str,
    model: str,
    messages: list,
    temperature: float,
    max_completion_tokens: int,
) -> str:
    payload = json.dumps(
        {
            "model": model,
            "messages": messages,
            "response_format": {"type": "json_object"},
            "temperature": temperature,
            "max_completion_tokens": max_completion_tokens,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        GROQ_API_ENDPOINT,
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "groq-bugteam/1.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(
        request, timeout=GROQ_REQUEST_TIMEOUT_SECONDS
    ) as open_connection:
        raw_response_bytes = open_connection.read()
    parsed = json.loads(raw_response_bytes.decode("utf-8"))
    return parsed["choices"][0]["message"]["content"]


def call_groq_with_fallback(
    api_key: str, messages: list, temperature: float, max_completion_tokens: int
) -> GroqCallResult:
    last_error: Exception | None = None
    for model in (GROQ_PRIMARY_MODEL, GROQ_FALLBACK_MODEL):
        for attempt_index, backoff_seconds in enumerate(
            (0, *GROQ_RETRY_BACKOFF_SECONDS)
        ):
            if backoff_seconds:
                time.sleep(backoff_seconds)
            try:
                content = post_to_groq(
                    api_key, model, messages, temperature, max_completion_tokens
                )
                return GroqCallResult(content=content, model=model)
            except urllib.error.HTTPError as http_error:
                last_error = http_error
                if should_skip_to_next_model(http_error):
                    break
                if not is_recoverable_http_error(http_error):
                    raise RuntimeError(
                        f"Groq request failed with non-recoverable HTTP error: {http_error}"
                    ) from http_error
            except (
                urllib.error.URLError,
                TimeoutError,
                json.JSONDecodeError,
            ) as transport_error:
                last_error = transport_error
    raise RuntimeError(f"Groq request failed after fallbacks: {last_error}")


def parse_json_object(raw_text: str) -> dict:
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{[\s\S]*\}", raw_text)
    if not match:
        raise ValueError("Groq response did not contain a JSON object")
    return json.loads(match.group(0))


def coerce_indexes_to_int_set(raw_indexes: list | None) -> set[int]:
    coerced: set[int] = set()
    for each_raw_index in raw_indexes or []:
        try:
            coerced.add(int(each_raw_index))
        except (TypeError, ValueError):
            continue
    return coerced


def coerce_skipped_entries(raw_skipped: list | None) -> dict[int, str]:
    coerced: dict[int, str] = {}
    for each_entry in raw_skipped or []:
        if not isinstance(each_entry, dict):
            continue
        try:
            finding_index = int(each_entry.get("finding_index"))
        except (TypeError, ValueError):
            continue
        raw_reason = each_entry.get("reason", "")
        coerced[finding_index] = "" if raw_reason is None else str(raw_reason)
    return coerced


def normalize_findings(raw_findings: list, files_content: dict) -> list:
    normalized = []
    for each_raw in raw_findings:
        file_path = str(each_raw.get("file", "")).strip()
        if not file_path or file_path not in files_content:
            continue
        try:
            line_number = int(each_raw.get("line", 0))
        except (TypeError, ValueError):
            line_number = 0
        severity = str(each_raw.get("severity", "P2")).upper()
        if severity not in ("P0", "P1", "P2"):
            severity = "P2"
        category = str(each_raw.get("category", "J")).upper()[:1]
        normalized.append(
            {
                "severity": severity,
                "category": category,
                "file": file_path,
                "line": line_number,
                "title": str(each_raw.get("title", "")).strip()[:200],
                "description": str(each_raw.get("description", "")).strip(),
            }
        )
    return normalized


def run_audit(api_key: str, diff_text: str, files_content: dict) -> tuple:
    clamped_diff = clamp_text(diff_text, MAXIMUM_DIFF_CHARACTERS)
    files_block_parts = []
    for each_path, each_content in files_content.items():
        clamped_content = clamp_text(each_content, MAXIMUM_FILE_CONTENT_CHARACTERS)
        files_block_parts.append(f"--- FILE: {each_path} ---\n{clamped_content}")
    user_message = (
        "Audit the following pull request diff.\n\n"
        "<diff>\n"
        f"{clamped_diff}\n"
        "</diff>\n\n"
        "<files_post_change>\n"
        + "\n\n".join(files_block_parts)
        + "\n</files_post_change>\n"
    )
    groq_result = call_groq_with_fallback(
        api_key,
        messages=[
            {"role": "system", "content": AUDIT_SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        temperature=GROQ_AUDIT_TEMPERATURE,
        max_completion_tokens=GROQ_AUDIT_MAX_COMPLETION_TOKENS,
    )
    parsed_content = parse_json_object(groq_result.content)
    raw_findings = parsed_content.get("findings", [])[:MAXIMUM_FINDINGS_PER_PR]
    return normalize_findings(raw_findings, files_content), groq_result.model


def should_write_fixed_file(
    applied_indexes: set, updated_content: str, current_content: str
) -> bool:
    if not applied_indexes:
        return False
    return updated_content != current_content


def is_safe_relative_path(each_path: str) -> bool:
    if os.path.isabs(each_path):
        return False
    posix_style_each_path = each_path.replace("\\", "/")
    if posix_style_each_path.startswith("/"):
        return False
    if each_path.startswith("\\"):
        return False
    normalized = os.path.normpath(each_path)
    if normalized.startswith(".." + os.sep) or normalized == "..":
        return False
    parts = normalized.replace("\\", "/").split("/")
    if ".." in parts:
        return False
    return True


def decode_subprocess_stderr(stderr_value) -> str:
    if stderr_value is None:
        return ""
    if isinstance(stderr_value, bytes):
        return stderr_value.decode("utf-8", "replace")
    return str(stderr_value)


def build_fix_user_message(file_path: str, current_content: str, findings_block: str) -> str:
    trailing_separator = "" if current_content.endswith("\n") else "\n"
    return (
        f"Fix the findings listed below in file `{file_path}`.\n\n"
        "<findings>\n"
        f"{findings_block}\n"
        "</findings>\n\n"
        "<current_file_contents>\n"
        f"{current_content}"
        f"{trailing_separator}</current_file_contents>\n"
    )


def preserve_trailing_newline(original: str, updated: str) -> str:
    original_ends_with_newline = original.endswith("\n")
    updated_ends_with_newline = updated.endswith("\n")
    if original_ends_with_newline and not updated_ends_with_newline:
        return updated + "\n"
    if not original_ends_with_newline and updated_ends_with_newline:
        return updated.rstrip("\n")
    return updated


def group_findings_by_file(findings: list) -> dict:
    grouped: dict = {}
    for each_index, each_finding in enumerate(findings):
        grouped.setdefault(each_finding["file"], []).append((each_index, each_finding))
    return grouped


def generate_fix_for_file(
    api_key: str,
    file_path: str,
    current_content: str,
    findings_for_file: list,
) -> tuple:
    findings_block = json.dumps(
        [
            {
                "finding_index": each_global_index,
                "severity": each_finding["severity"],
                "category": each_finding["category"],
                "line": each_finding["line"],
                "title": each_finding["title"],
                "description": each_finding["description"],
            }
            for each_global_index, each_finding in findings_for_file
        ],
        indent=JSON_INDENT_SPACES,
    )
    user_message = build_fix_user_message(file_path, current_content, findings_block)
    groq_result = call_groq_with_fallback(
        api_key,
        messages=[
            {"role": "system", "content": FIX_SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        temperature=GROQ_FIX_TEMPERATURE,
        max_completion_tokens=GROQ_FIX_MAX_COMPLETION_TOKENS,
    )
    return parse_json_object(groq_result.content), groq_result.model


def apply_fixes_and_commit(
    worktree_path: str,
    fixes: dict,
    commit_message: str,
) -> str:
    if not fixes:
        return ""
    worktree_root = os.path.realpath(worktree_path)
    for each_path, each_new_content in fixes.items():
        if not is_safe_relative_path(each_path):
            raise ValueError(
                f"Refusing to write unsafe path from Groq response: {each_path!r}"
            )
        absolute_path = os.path.join(worktree_root, each_path)
        resolved_path = os.path.realpath(absolute_path)
        if (
            resolved_path != worktree_root
            and not resolved_path.startswith(worktree_root + os.sep)
        ):
            raise ValueError(
                f"Refusing to write path that escapes worktree: {each_path!r}"
            )
        parent_directory = os.path.dirname(absolute_path)
        if parent_directory:
            os.makedirs(parent_directory, exist_ok=True)
        with open(absolute_path, "w", encoding="utf-8", newline="\n") as fix_handle:
            fix_handle.write(each_new_content)
    changed_paths = list(fixes.keys())
    subprocess.run(
        ["git", "-C", worktree_path, "add", "--", *changed_paths],
        check=True,
        capture_output=True,
    )
    status_result = subprocess.run(
        ["git", "-C", worktree_path, "status", "--porcelain"],
        check=True,
        capture_output=True,
        text=True,
    )
    if not status_result.stdout.strip():
        return ""
    subprocess.run(
        ["git", "-C", worktree_path, "commit", "-m", commit_message],
        check=True,
        capture_output=True,
    )
    rev_parse_result = subprocess.run(
        ["git", "-C", worktree_path, "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return rev_parse_result.stdout.strip()


def push_current_branch(worktree_path: str, head_ref: str) -> None:
    subprocess.run(
        ["git", "-C", worktree_path, "push", "origin", f"HEAD:{head_ref}"],
        check=True,
        capture_output=True,
    )


def build_review_body(
    findings: list, audit_model: str, commit_sha: str, fix_outcomes: list
) -> str:
    if not findings:
        return NO_FINDINGS_REVIEW_BODY.format(model=audit_model)
    severity_counts = {"P0": 0, "P1": 0, "P2": 0}
    for each_finding in findings:
        severity_counts[each_finding["severity"]] += 1
    header = REVIEW_BODY_HEADER_TEMPLATE.format(
        p0=severity_counts["P0"], p1=severity_counts["P1"], p2=severity_counts["P2"]
    )
    lines = [header, ""]
    if commit_sha:
        lines.append(f"Auto-fix commit: `{commit_sha[:7]}`")
        lines.append("")
    lines.append(f"Audit model: `{audit_model}`")
    lines.append("")
    lines.append("### Findings")
    lines.append("")
    for each_index, each_finding in enumerate(findings):
        status_for_finding = next(
            (
                each_outcome
                for each_outcome in fix_outcomes
                if each_outcome["finding_index"] == each_index
            ),
            None,
        )
        status_label = "not attempted"
        if status_for_finding:
            status_label = status_for_finding["status"]
            if status_for_finding.get("reason"):
                status_label = f"{status_label}: {status_for_finding['reason']}"
        lines.append(
            f"- **[{each_finding['severity']} / {each_finding['category']}] "
            f"{each_finding['title']}** — `{each_finding['file']}:{each_finding['line']}` "
            f"— _{status_label}_"
        )
        lines.append(f"  {each_finding['description']}")
    return "\n".join(lines)


def run_pipeline(input_data: dict) -> dict:
    load_claude_dev_env_dotenv_file()
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key:
        return {"error": MISSING_API_KEY_ERROR}

    diff_text = input_data.get("diff", "")
    files_content = input_data.get("files_content", {})
    worktree_path = input_data.get("worktree_path", "")
    head_ref = input_data.get("head_ref", "")
    pr_number = input_data.get("pr_number", 0)
    apply_fixes_requested = bool(input_data.get("apply_fixes", True))

    if not diff_text.strip():
        return {"error": "diff is empty; nothing to audit"}
    if apply_fixes_requested and (not worktree_path or not head_ref):
        return {"error": "apply_fixes requires worktree_path and head_ref"}

    findings, audit_model = run_audit(api_key, diff_text, files_content)

    fix_outcomes: list = []
    files_to_write: dict = {}
    fix_model = ""

    if findings and apply_fixes_requested:
        grouped = group_findings_by_file(findings)
        for each_file_path, each_findings_for_file in grouped.items():
            current_content = files_content.get(each_file_path, "")
            try:
                fix_result, fix_model = generate_fix_for_file(
                    api_key, each_file_path, current_content, each_findings_for_file
                )
            except Exception as fix_error:
                for each_global_index, _each_finding in each_findings_for_file:
                    fix_outcomes.append(
                        {
                            "finding_index": each_global_index,
                            "status": "fix_call_failed",
                            "reason": str(fix_error)[:200],
                        }
                    )
                continue
            raw_updated_content = fix_result.get("updated_content", current_content)
            applied_indexes = coerce_indexes_to_int_set(
                fix_result.get("applied_finding_indexes", [])
            )
            skipped_entries = coerce_skipped_entries(fix_result.get("skipped", []))
            updated_content = preserve_trailing_newline(current_content, raw_updated_content)
            content_changed = updated_content != current_content
            if should_write_fixed_file(applied_indexes, updated_content, current_content):
                files_to_write[each_file_path] = updated_content
            for each_global_index, _each_finding in each_findings_for_file:
                if each_global_index in applied_indexes and content_changed:
                    fix_outcomes.append(
                        {"finding_index": each_global_index, "status": "fixed"}
                    )
                elif each_global_index in applied_indexes:
                    fix_outcomes.append(
                        {
                            "finding_index": each_global_index,
                            "status": "skipped",
                            "reason": "model claimed fix applied but file content is unchanged",
                        }
                    )
                elif each_global_index in skipped_entries:
                    fix_outcomes.append(
                        {
                            "finding_index": each_global_index,
                            "status": "skipped",
                            "reason": skipped_entries[each_global_index][:200],
                        }
                    )
                else:
                    fix_outcomes.append(
                        {"finding_index": each_global_index, "status": "not_addressed"}
                    )

    commit_sha = ""
    if files_to_write and apply_fixes_requested:
        applied_count = sum(
            1 for each_outcome in fix_outcomes if each_outcome["status"] == "fixed"
        )
        commit_message = (
            f"fix(groq-bugteam): auto-fix audit findings for PR #{pr_number}\n\n"
            f"Addressed {applied_count} of {len(findings)} findings from groq-bugteam audit."
        )
        try:
            commit_sha = apply_fixes_and_commit(
                worktree_path, files_to_write, commit_message
            )
            if commit_sha:
                push_current_branch(worktree_path, head_ref)
        except subprocess.CalledProcessError as git_error:
            stderr_preview = decode_subprocess_stderr(git_error.stderr)[:500]
            return {
                "findings": findings,
                "fix_outcomes": fix_outcomes,
                "commit_sha": "",
                "review_body": build_review_body(
                    findings, audit_model, "", fix_outcomes
                ),
                "audit_model": audit_model,
                "fix_model": fix_model,
                "error": f"git operation failed: {stderr_preview}",
            }
        except ValueError as unsafe_path_error:
            return {
                "findings": findings,
                "fix_outcomes": fix_outcomes,
                "commit_sha": "",
                "review_body": build_review_body(
                    findings, audit_model, "", fix_outcomes
                ),
                "audit_model": audit_model,
                "fix_model": fix_model,
                "error": f"unsafe fix rejected: {unsafe_path_error}",
            }

    review_body = build_review_body(findings, audit_model, commit_sha, fix_outcomes)

    return {
        "findings": findings,
        "fix_outcomes": fix_outcomes,
        "commit_sha": commit_sha,
        "review_body": review_body,
        "audit_model": audit_model,
        "fix_model": fix_model,
    }


def run_default_pipeline_main() -> None:
    try:
        stdin_text = sys.stdin.read()
        input_data = json.loads(stdin_text)
    except (json.JSONDecodeError, ValueError) as parse_error:
        json.dump({"error": f"stdin is not valid JSON: {parse_error}"}, sys.stdout)
        sys.exit(1)

    try:
        pipeline_outcome = run_pipeline(input_data)
    except Exception as pipeline_error:
        pipeline_outcome = {"error": f"pipeline failed: {pipeline_error}"}

    json.dump(pipeline_outcome, sys.stdout, indent=JSON_INDENT_SPACES)
    sys.stdout.write("\n")
    if "error" in pipeline_outcome:
        sys.exit(PIPELINE_FAILURE_EXIT_CODE)


from groq_bugteam_spec import (
    apply_fix_from_spec,
    is_spec_mode_invocation,
    run_spec_mode_main,
)


def main() -> None:
    load_claude_dev_env_dotenv_file()
    if is_spec_mode_invocation(sys.argv[1:]):
        run_spec_mode_main()
        return
    run_default_pipeline_main()


if __name__ == "__main__":
    main()
