#!/usr/bin/env bash
# Cloud Agent bootstrap for the claude-dev-env monorepo.
#
# Prepares a clean base image to build, test, lint, and run the
# claude-dev-env npm installer. Safe to run repeatedly: every step is
# idempotent, so a rerun over cached or snapshot state converges without
# duplicating work.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

echo "==> System packages (python launcher, pip, libpq for psycopg)"
sudo apt-get update -qq
sudo apt-get install -y -qq python-is-python3 python3-pip libpq5

echo "==> PowerShell (runs the check.ps1 quality gate)"
if ! command -v pwsh >/dev/null 2>&1; then
  powershell_deb="$(mktemp --suffix=.deb)"
  curl -fsSL -o "$powershell_deb" \
    https://github.com/PowerShell/PowerShell/releases/download/v7.4.6/powershell_7.4.6-1.deb_amd64.deb
  sudo dpkg -i "$powershell_deb" || sudo apt-get install -f -y -qq
  rm -f "$powershell_deb"
fi

echo "==> Node workspace dependencies"
npm install

echo "==> Python test and lint tooling plus the editable constants packages"
pip install --break-system-packages -e "packages/claude-dev-env[dev]" ruff mypy pytest psycopg

echo "==> Expose user-site console scripts to name-based callers (check.ps1 runs ruff and mypy)"
for console_script in ruff mypy pytest; do
  if [ -x "$HOME/.local/bin/$console_script" ]; then
    sudo ln -sf "$HOME/.local/bin/$console_script" "/usr/local/bin/$console_script"
  fi
done

echo "==> Install the claude-dev-env config from local source (the npx claude-dev-env workflow)"
node packages/claude-dev-env/bin/install.mjs --update

echo "==> Bootstrap complete"
