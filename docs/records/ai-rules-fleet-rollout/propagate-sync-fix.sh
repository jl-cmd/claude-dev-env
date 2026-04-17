#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
LISTENER_SCRIPT_SOURCE="${REPO_ROOT}/.github/scripts/sync_ai_rules.py"
LISTENER_SCRIPT_DEST=".github/scripts/sync_ai_rules.py"
BOOTSTRAP_BRANCH_NAME="chore/bootstrap-ai-rules-sync-v1"
MERGED_REPO="jl-cmd/snake-game"

log_info() { echo "[INFO] $*" >&2; }
log_warn() { echo "[WARN] $*" >&2; }

all_targets=(
    "jl-cmd/agent-gate"
    "jl-cmd/claude-deep-research"
    "jl-cmd/claude-dream"
    "jl-cmd/claude-journal"
    "jl-cmd/claude-workflow"
    "jl-cmd/florida-blue-claim-filler"
    "jl-cmd/groq-prompt-scorer"
    "jl-cmd/jl-cmd"
    "jl-cmd/Learnit"
    "jl-cmd/one-great-ride-website"
    "jl-cmd/prompt-generator"
    "jl-cmd/redlib"
    "jl-cmd/snake-game"
    "JonEcho/babysit-pr"
    "JonEcho/focus-zones-native"
    "JonEcho/JonEcho"
    "JonEcho/llm-settings"
    "JonEcho/python-automation"
    "JonEcho/python-automation-debug"
    "JonEcho/theme-asset-db"
    "JonEcho/theme-planning"
    "JonEcho/theme-skills"
    "JonEcho/us-paid-promotion"
)

for repo_full_name in "${all_targets[@]}"; do
    work_dir=$(mktemp -d)

    if [[ "${repo_full_name}" == "${MERGED_REPO}" ]]; then
        target_branch="main"
        commit_message="fix: pick up env-var-fallback correction from claude-code-config"
    else
        target_branch="${BOOTSTRAP_BRANCH_NAME}"
        commit_message="chore: refresh listener script with env-var-fallback fix"
    fi

    log_info "Updating ${repo_full_name} on ${target_branch}..."

    if ! gh repo clone "${repo_full_name}" "${work_dir}" -- --depth 1 --branch "${target_branch}" --quiet --config core.longpaths=true 2>/dev/null; then
        log_warn "  Failed to clone ${repo_full_name} branch ${target_branch}, skipping"
        rm -rf "${work_dir}"
        continue
    fi

    if cmp -s "${LISTENER_SCRIPT_SOURCE}" "${work_dir}/${LISTENER_SCRIPT_DEST}"; then
        log_info "  Already up to date, skipping"
        rm -rf "${work_dir}"
        continue
    fi

    cp "${LISTENER_SCRIPT_SOURCE}" "${work_dir}/${LISTENER_SCRIPT_DEST}"
    git -C "${work_dir}" add -f "${LISTENER_SCRIPT_DEST}" >/dev/null 2>&1
    git -C "${work_dir}" commit -m "${commit_message}" >/dev/null 2>&1
    git -C "${work_dir}" push origin "${target_branch}" >/dev/null 2>&1

    log_info "  Pushed fix to ${repo_full_name}:${target_branch}"
    rm -rf "${work_dir}"
done

log_info "Done."
