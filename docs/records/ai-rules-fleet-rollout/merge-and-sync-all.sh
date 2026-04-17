#!/usr/bin/env bash
set -euo pipefail

log_info() { echo "[INFO] $*" >&2; }
log_warn() { echo "[WARN] $*" >&2; }

open_pr_targets=(
    "jl-cmd/agent-gate:92"
    "jl-cmd/claude-deep-research:2"
    "jl-cmd/claude-dream:2"
    "jl-cmd/claude-journal:2"
    "jl-cmd/claude-workflow:2"
    "jl-cmd/florida-blue-claim-filler:3"
    "jl-cmd/groq-prompt-scorer:2"
    "jl-cmd/jl-cmd:3"
    "jl-cmd/Learnit:2"
    "jl-cmd/one-great-ride-website:7"
    "jl-cmd/prompt-generator:34"
    "jl-cmd/redlib:12"
    "JonEcho/babysit-pr:23"
    "JonEcho/focus-zones-native:2"
    "JonEcho/JonEcho:2"
    "JonEcho/llm-settings:41"
    "JonEcho/python-automation:42"
    "JonEcho/python-automation-debug:17"
    "JonEcho/theme-asset-db:54"
    "JonEcho/theme-planning:14"
    "JonEcho/theme-skills:25"
    "JonEcho/us-paid-promotion:15"
)

for each_target in "${open_pr_targets[@]}"; do
    repo_full_name="${each_target%:*}"
    pr_number="${each_target#*:}"

    log_info "Merging ${repo_full_name}#${pr_number}..."
    if ! gh pr ready "${pr_number}" --repo "${repo_full_name}" 2>/dev/null; then
        log_warn "  Could not mark ready (may already be ready)"
    fi
    if ! gh pr merge "${pr_number}" --repo "${repo_full_name}" --squash --delete-branch 2>&1 | tail -1 >&2; then
        log_warn "  Merge failed for ${repo_full_name}#${pr_number}"
        continue
    fi
    log_info "  Merged"
done

log_info "All merges done. Sleeping 10s before triggering initial sync..."
sleep 10

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
    log_info "Dispatching initial sync to ${repo_full_name} with force_initial_overwrite=true..."
    if gh workflow run sync-ai-rules.yml --repo "${repo_full_name}" -f force_initial_overwrite=true 2>&1 | tail -1 >&2; then
        log_info "  Dispatched"
    else
        log_warn "  Dispatch failed"
    fi
    sleep 1
done

log_info "All dispatches sent. Sleep 45s then report results..."
sleep 45

for repo_full_name in "${all_targets[@]}"; do
    latest_status=$(gh run list --repo "${repo_full_name}" --workflow sync-ai-rules.yml --limit 1 --json status,conclusion --jq '.[0] | "\(.status)/\(.conclusion)"' 2>/dev/null)
    log_info "${repo_full_name}: ${latest_status}"
done
