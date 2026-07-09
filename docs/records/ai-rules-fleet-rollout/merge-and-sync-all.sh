#!/usr/bin/env bash
set -euo pipefail

# Historical one-shot rollout record. Target repo names intentionally omitted
# (see issue #945). Rebuild the target list from installation enumeration at
# run time rather than hardcoding private inventory here.

log_info() { echo "[INFO] $*" >&2; }
log_warn() { echo "[WARN] $*" >&2; }

log_info "This record script no longer ships a hardcoded personal-repo list."
log_info "Use scripts/fan_out_dispatch.py or a local private inventory at run time."
exit 0
