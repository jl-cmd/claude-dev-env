#!/usr/bin/env bash
# Deploys the sync-ai-rules listener workflow and script to every active target repo.
# Idempotent: skips repos that already have the canonical content, detects open PRs.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

LISTENER_WORKFLOW_SOURCE="${REPO_ROOT}/.github/workflows/sync-ai-rules.yml"
LISTENER_SCRIPT_SOURCE="${REPO_ROOT}/.github/scripts/sync_ai_rules.py"
LISTENER_WORKFLOW_DEST=".github/workflows/sync-ai-rules.yml"
LISTENER_SCRIPT_DEST=".github/scripts/sync_ai_rules.py"
BOOTSTRAP_BRANCH_NAME="chore/bootstrap-ai-rules-sync-v1"
PR_TITLE="chore: bootstrap AI rules sync listener (v1)"
DOCS_LINK="https://github.com/jl-cmd/claude-code-config/blob/main/docs/ai-rules-sync.md"
SOURCE_REPO="jl-cmd/claude-code-config"
OPT_OUT_SENTINEL_PATH=".github/sync-ai-rules.optout"

OWNERS=("JonEcho" "jl-cmd")
DRY_RUN=false
AUTO_MERGE=false
SKIP_REPOS=()
REPORT_FILE="bootstrap-report.json"

print_usage() {
    cat <<EOF
Usage: bootstrap-listeners.sh [OPTIONS]

Deploys the sync-ai-rules listener to all active JonEcho/jl-cmd repos.

Options:
  --dry-run            Preview changes without creating branches or PRs
  --owner <name>       Limit to a specific owner (repeatable; default: JonEcho jl-cmd)
  --auto-merge         Enable auto-merge on created PRs
  --skip <repo>        Skip a specific repo full name (repeatable)
  --version <n>        Bootstrap version suffix (default: 1)
  --help               Show this message
EOF
}

log_info() { echo "[INFO] $*" >&2; }
log_warn() { echo "[WARN] $*" >&2; }
log_error() { echo "[ERROR] $*" >&2; }

check_prerequisites() {
    if ! command -v gh &>/dev/null; then
        log_error "gh CLI not found. Install from https://cli.github.com and authenticate."
        exit 1
    fi
    if ! gh auth status &>/dev/null; then
        log_error "gh CLI not authenticated. Run: gh auth login"
        exit 1
    fi
}

enumerate_target_repos() {
    local all_repos=()
    for owner in "${OWNERS[@]}"; do
        while IFS= read -r repo_json; do
            all_repos+=("${repo_json}")
        done < <(
            gh repo list "${owner}" \
                --no-archived \
                --limit 1000 \
                --json nameWithOwner,viewerPermission,isFork,parent \
                --jq '.[] | select(
                    (.viewerPermission == "ADMIN" or .viewerPermission == "MAINTAIN" or .viewerPermission == "WRITE")
                    and (
                        .isFork == false
                        or (.parent.owner.login == "JonEcho" or .parent.owner.login == "jl-cmd")
                    )
                ) | .nameWithOwner'
        )
    done
    printf '%s\n' "${all_repos[@]}" | sort -u
}

is_skipped() {
    local repo_full_name="$1"
    for skipped_repo in "${SKIP_REPOS[@]}"; do
        if [[ "${repo_full_name}" == "${skipped_repo}" ]]; then
            return 0
        fi
    done
    return 1
}

has_opt_out_sentinel() {
    local repo_full_name="$1"
    gh api "repos/${repo_full_name}/contents/${OPT_OUT_SENTINEL_PATH}" &>/dev/null
}

workflow_content_matches() {
    local repo_full_name="$1"
    local remote_content
    remote_content=$(gh api "repos/${repo_full_name}/contents/${LISTENER_WORKFLOW_DEST}" \
        --jq '.content' 2>/dev/null | base64 --decode 2>/dev/null || true)
    local local_content
    local_content=$(cat "${LISTENER_WORKFLOW_SOURCE}")
    [[ "${remote_content}" == "${local_content}" ]]
}

open_pr_exists() {
    local repo_full_name="$1"
    gh pr list \
        --repo "${repo_full_name}" \
        --head "${BOOTSTRAP_BRANCH_NAME}" \
        --state open \
        --json number \
        --jq 'length > 0' 2>/dev/null | grep -q "true"
}

deploy_to_repo() {
    local repo_full_name="$1"
    local work_dir
    work_dir=$(mktemp -d)
    trap 'rm -rf "${work_dir}"' RETURN

    log_info "Cloning ${repo_full_name} (shallow)..."
    if ! gh repo clone "${repo_full_name}" "${work_dir}" -- --depth 1 --quiet --config core.longpaths=true 2>&1 | grep -v "^Cloning into" >/dev/null; then
        :
    fi
    if [[ ! -d "${work_dir}/.git" ]]; then
        log_warn "Failed to clone ${repo_full_name}, skipping"
        echo "clone-failed"
        return
    fi

    local workflow_matches=0
    local script_matches=0
    if [[ -f "${work_dir}/${LISTENER_WORKFLOW_DEST}" ]] && cmp -s "${LISTENER_WORKFLOW_SOURCE}" "${work_dir}/${LISTENER_WORKFLOW_DEST}"; then
        workflow_matches=1
    fi
    if [[ -f "${work_dir}/${LISTENER_SCRIPT_DEST}" ]] && cmp -s "${LISTENER_SCRIPT_SOURCE}" "${work_dir}/${LISTENER_SCRIPT_DEST}"; then
        script_matches=1
    fi

    if [[ ${workflow_matches} -eq 1 && ${script_matches} -eq 1 ]]; then
        log_info "${repo_full_name}: already up to date, skipping"
        echo "skipped"
        return
    fi

    mkdir -p "${work_dir}/.github/workflows"
    mkdir -p "${work_dir}/.github/scripts"

    cp "${LISTENER_WORKFLOW_SOURCE}" "${work_dir}/${LISTENER_WORKFLOW_DEST}"
    cp "${LISTENER_SCRIPT_SOURCE}" "${work_dir}/${LISTENER_SCRIPT_DEST}"

    if [[ "${DRY_RUN}" == "true" ]]; then
        log_info "[DRY RUN] Would create branch and PR in ${repo_full_name}"
        echo "dry-run"
        return
    fi

    git -C "${work_dir}" checkout -b "${BOOTSTRAP_BRANCH_NAME}" >/dev/null 2>&1
    git -C "${work_dir}" add -f \
        "${LISTENER_WORKFLOW_DEST}" \
        "${LISTENER_SCRIPT_DEST}" >/dev/null 2>&1
    git -C "${work_dir}" commit -m "chore: bootstrap AI rules sync listener (v1)" >/dev/null 2>&1
    git -C "${work_dir}" push origin "${BOOTSTRAP_BRANCH_NAME}" >/dev/null 2>&1

    local pr_body
    pr_body=$(cat <<EOF
## Bootstrap AI Rules Sync Listener

This PR installs the sync-ai-rules listener workflow and helper script.

**What it does:** On each \`repository_dispatch\` event from \`${SOURCE_REPO}\`, this workflow
syncs \`.github/copilot-instructions.md\` and \`.cursor/BUGBOT.md\` from the canonical
source of truth. No new secrets are required — only the default \`GITHUB_TOKEN\` is used.

**Docs:** ${DOCS_LINK}

**To opt out permanently:** Create \`.github/sync-ai-rules.optout\` in this repo.
EOF
)

    local pr_flags=("--repo" "${repo_full_name}" "--draft" "--title" "${PR_TITLE}" "--body" "${pr_body}" "--head" "${BOOTSTRAP_BRANCH_NAME}")
    if [[ "${AUTO_MERGE}" == "true" ]]; then
        pr_flags+=("--auto-merge")
    fi

    gh pr create "${pr_flags[@]}"
    echo "pr-created"
}

main() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --dry-run) DRY_RUN=true; shift ;;
            --auto-merge) AUTO_MERGE=true; shift ;;
            --owner) OWNERS=("$2"); shift 2 ;;
            --skip) SKIP_REPOS+=("$2"); shift 2 ;;
            --version) BOOTSTRAP_BRANCH_NAME="chore/bootstrap-ai-rules-sync-v$2"; shift 2 ;;
            --help) print_usage; exit 0 ;;
            *) log_error "Unknown option: $1"; print_usage; exit 1 ;;
        esac
    done

    check_prerequisites

    log_info "Enumerating target repos for owners: ${OWNERS[*]}"
    local report_entries=()
    local all_target_repos
    mapfile -t all_target_repos < <(enumerate_target_repos)

    for repo_full_name in "${all_target_repos[@]}"; do
        if [[ "${repo_full_name}" == "${SOURCE_REPO}" ]]; then
            continue
        fi

        if is_skipped "${repo_full_name}"; then
            log_info "${repo_full_name}: skipped by --skip flag"
            report_entries+=("{\"repo\":\"${repo_full_name}\",\"status\":\"skipped-by-flag\"}")
            continue
        fi

        if has_opt_out_sentinel "${repo_full_name}"; then
            log_info "${repo_full_name}: opted out via sentinel"
            report_entries+=("{\"repo\":\"${repo_full_name}\",\"status\":\"opted-out\"}")
            continue
        fi

        if open_pr_exists "${repo_full_name}"; then
            log_info "${repo_full_name}: open PR already exists on ${BOOTSTRAP_BRANCH_NAME}"
            report_entries+=("{\"repo\":\"${repo_full_name}\",\"status\":\"pr-already-open\"}")
            continue
        fi

        deploy_status=$(deploy_to_repo "${repo_full_name}")
        log_info "${repo_full_name}: ${deploy_status}"
        report_entries+=("{\"repo\":\"${repo_full_name}\",\"status\":\"${deploy_status}\"}")
    done

    printf '[%s]\n' "$(IFS=,; echo "${report_entries[*]}")" > "${REPORT_FILE}"
    log_info "Report written to ${REPORT_FILE}"
}

main "$@"
