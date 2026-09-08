#!/usr/bin/env bash
set -euo pipefail
repo="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
exec node "$repo/packages/claude-dev-env/bin/pstack.mjs" install --host "${1:?Use claude, codex or cursor}" --root "${2:-$PWD}" --force-check
