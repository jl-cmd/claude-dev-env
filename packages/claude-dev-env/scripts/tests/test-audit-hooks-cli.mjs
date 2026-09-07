import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import {
  mkdirSync,
  mkdtempSync,
  readFileSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const packageRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const auditCliPath = path.join(packageRoot, "audit-hooks-cli.mjs");

function writeJson(filePath, jsonDocument) {
  writeFileSync(filePath, JSON.stringify(jsonDocument), "utf8");
}

function createAuditFixture({
  canonicalHooks = {},
  claudeHooks = { hooks: {} },
  codexHooks = { hooks: {} },
} = {}) {
  const fixtureRoot = mkdtempSync(path.join(tmpdir(), "hook-audit-cli-"));
  const canonicalHooksRoot = path.join(fixtureRoot, "packages", "claude-dev-env", "hooks");
  const homeDirectory = path.join(fixtureRoot, "home");
  mkdirSync(canonicalHooksRoot, { recursive: true });
  mkdirSync(path.join(homeDirectory, ".claude", "hooks"), { recursive: true });
  mkdirSync(path.join(homeDirectory, ".codex", "hooks"), { recursive: true });
  writeJson(path.join(canonicalHooksRoot, "hooks.json"), { hooks: canonicalHooks });
  writeJson(path.join(homeDirectory, ".claude", "settings.json"), claudeHooks);
  writeJson(path.join(homeDirectory, ".codex", "hooks.json"), codexHooks);
  return { fixtureRoot, homeDirectory };
}

function runAuditCli(allArguments) {
  const childProcess = spawnSync(process.execPath, [auditCliPath, ...allArguments], {
    cwd: packageRoot,
    encoding: "utf8",
    env: { ...process.env, HOME: path.join(tmpdir(), "unused-audit-cli-home") },
    shell: false,
  });
  assert.equal(childProcess.error, undefined);
  return childProcess;
}

test("writes a JSON audit report to stdout through the CLI", () => {
  const fixture = createAuditFixture({
    canonicalHooks: {
      PreToolUse: [{
        matcher: "Write",
        hooks: [{
          type: "command",
          command: "python3 " + "$" + "{CLAUDE_PLUGIN_ROOT}/hooks/blocking/write_existing_file_blocker.py",
        }],
      }],
    },
  });
  try {
    const childProcess = runAuditCli([
      "--format",
      "json",
      "--repository-root",
      fixture.fixtureRoot,
    ]);

    assert.equal(childProcess.status, 0);
    assert.equal(childProcess.stderr, "");
    const report = JSON.parse(childProcess.stdout);
    assert.equal(report.summary.directCount, 1);
    assert.equal(report.registrationEligibility.status, "not_checked");
  } finally {
    rmSync(fixture.fixtureRoot, { force: true, recursive: true });
  }
});

test("writes the JSON audit report to the requested file through the CLI", () => {
  const fixture = createAuditFixture();
  const reportPath = path.join(fixture.fixtureRoot, "audit-report.json");
  try {
    const childProcess = runAuditCli([
      "--format",
      "json",
      "--output",
      reportPath,
      "--repository-root",
      fixture.fixtureRoot,
    ]);

    assert.equal(childProcess.status, 0);
    assert.equal(childProcess.stdout, "");
    const report = JSON.parse(readFileSync(reportPath, "utf8"));
    assert.equal(report.summary.directCount, 0);
    assert.equal(report.summary.findingCount, 0);
  } finally {
    rmSync(fixture.fixtureRoot, { force: true, recursive: true });
  }
});

test("returns a strict nonblocking failure through the CLI", () => {
  const fixture = createAuditFixture({
    claudeHooks: {
      hooks: {
        SessionStart: [{
          hooks: [{ command: "node cleanup.mjs", type: "command" }],
        }],
      },
    },
  });
  const catalogPath = path.join(fixture.fixtureRoot, "lifecycle.json");
  writeJson(catalogPath, {
    hooks: {
      "external:cleanup.mjs": {
        lifecycle: "delete",
        reason: "The installed entry is retired.",
        replacement: null,
      },
    },
  });
  try {
    const childProcess = runAuditCli([
      "--format",
      "json",
      "--catalog",
      catalogPath,
      "--home",
      fixture.homeDirectory,
      "--installed",
      "--require-nonblocking",
      "--repository-root",
      fixture.fixtureRoot,
    ]);

    assert.equal(childProcess.status, 1);
    assert.equal(childProcess.stderr, "");
    const report = JSON.parse(childProcess.stdout);
    assert.equal(report.registrationEligibility.status, "ineligible");
    assert.equal(
      report.findings.some(({ code, target }) =>
        code === "NONBLOCKING_LIFECYCLE_MISMATCH" && target === "external:cleanup.mjs",
      ),
      true,
    );
  } finally {
    rmSync(fixture.fixtureRoot, { force: true, recursive: true });
  }
});
