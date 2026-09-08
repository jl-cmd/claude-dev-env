#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname -- "${BASH_SOURCE[0]}")/pstack-cloud-setup.sh" "${1:-codex}" "${2:-$PWD}"
