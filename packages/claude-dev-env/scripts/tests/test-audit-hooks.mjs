import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { existsSync, mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { auditHooks } from "../audit-hooks.mjs";

const repositoryRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../../..");

function writeJson(filePath, document) {
  writeFileSync(filePath, JSON.stringify(document), "utf8");
}

function createAuditFixture({ canonicalHooks = {}, claudeHooks = { hooks: {} }, codexHooks = { hooks: {} } } = {}) {
  const fixtureRoot = mkdtempSync(path.join(tmpdir(), "hook-audit-"));
  const canonicalHooksRoot = path.join(fixtureRoot, "packages", "claude-dev-env", "hooks");
  const homeDirectory = path.join(fixtureRoot, "home");
  mkdirSync(canonicalHooksRoot, { recursive: true });
  mkdirSync(path.join(homeDirectory, ".claude", "hooks"), { recursive: true });
  mkdirSync(path.join(homeDirectory, ".codex", "hooks"), { recursive: true });
  writeJson(path.join(canonicalHooksRoot, "hooks.json"), { hooks: canonicalHooks });
  writeJson(path.join(homeDirectory, ".claude", "settings.json"), claudeHooks);
  writeJson(path.join(homeDirectory, ".codex", "hooks.json"), codexHooks);
  return { fixtureRoot, homeDirectory, canonicalHooksRoot };
}

function writeHookFile(hooksRoot, relativePath) {
  const hookPath = path.join(hooksRoot, relativePath);
  mkdirSync(path.dirname(hookPath), { recursive: true });
  writeFileSync(hookPath, "", "utf8");
}

function runGit(repositoryRoot, argumentsList, environment) {
  const command = spawnSync("git", argumentsList, {
    cwd: repositoryRoot,
    encoding: "utf8",
    env: environment,
    shell: false,
  });
  assert.equal(command.status, 0, command.stderr);
  return command;
}

test("reports the canonical execution graph", () => {
  const fixture = createAuditFixture({
    canonicalHooks: {
      PreToolUse: [{
        matcher: "Write",
        hooks: [{ type: "command", command: "python3 ${CLAUDE_PLUGIN_ROOT}/hooks/blocking/write_existing_file_blocker.py" }],
      }],
    },
  });
  try {
    const report = auditHooks({ repositoryRoot: fixture.fixtureRoot });
    assert.equal(report.summary.directCount, 1);
    assert.equal(report.summary.dispatcherCount, 0);
    assert.equal(report.summary.effectiveCount, 0);
    assert.equal(report.summary.logicalAssociationCount, 1);
  } finally {
    rmSync(fixture.fixtureRoot, { force: true, recursive: true });
  }
});

test("renders deterministic private JSON", () => {
  const report = auditHooks({ repositoryRoot });
  const first = JSON.stringify(report);
  const second = JSON.stringify(report);
  assert.equal(first, second);
  assert.equal(first.includes(repositoryRoot), false);
  assert.equal(first.includes("python3 ${CLAUDE_PLUGIN_ROOT}"), false);
});

test("does not compare the live graph with retired baseline counts", () => {
  const report = auditHooks({ repositoryRoot });
  assert.equal(report.summary.directCount, report.directRegistrations.length);
  assert.equal(report.summary.effectiveCount, report.hostedRegistrations.length);
  assert.equal(report.summary.logicalAssociationCount, report.logicalRegistrations.length);
  assert.ok(report.summary.directCount > 0);
  assert.ok(report.summary.effectiveCount > 0);
  assert.ok(report.summary.logicalAssociationCount > report.summary.directCount);
  assert.equal(report.findings.some(({ code }) => code === "DIRECT_COUNT_DRIFT"), false);
  assert.equal(report.findings.some(({ code }) => code === "HOSTED_COUNT_DRIFT"), false);
});

test("does not execute registered commands", () => {
  const fixture = createAuditFixture({
    canonicalHooks: {
      PreToolUse: [{
        hooks: [{
          command: "node -e \"require('node:fs').writeFileSync('audit-executed', 'yes')\"",
          type: "command",
        }],
      }],
    },
  });
  try {
    auditHooks({ repositoryRoot: fixture.fixtureRoot });
    assert.equal(existsSync(path.join(fixture.fixtureRoot, "audit-executed")), false);
  } finally {
    rmSync(fixture.fixtureRoot, { force: true, recursive: true });
  }
});

test("reports every unclassified target", () => {
  const temporaryRoot = mkdtempSync(path.join(tmpdir(), "hook-audit-"));
  const catalogPath = path.join(temporaryRoot, "lifecycle.json");
  writeFileSync(catalogPath, '{"schema_version":1,"hooks":{}}', "utf8");
  try {
    const report = auditHooks({ catalogPath, repositoryRoot });
    assert.equal(report.summary.unclassifiedCount, report.summary.uniqueTargetCount);
    assert.equal(report.findings.some(({ code }) => code === "UNCLASSIFIED_HOOK"), true);
  } finally {
    rmSync(temporaryRoot, { force: true, recursive: true });
  }
});

test("reports canonical native Git hooks from the installer registry", () => {
  const report = auditHooks({ repositoryRoot });
  assert.deepEqual(
    report.knownGitRegistrations.map(({ target }) => target),
    ["git:pre-commit", "git:pre-push", "git:post-commit"],
  );
  assert.equal(report.summary.knownGitHookCount, 3);
});

test("keeps each hosted matcher as narrow as its roster", () => {
  const fixture = createAuditFixture({
    canonicalHooks: {
      PreToolUse: [{
        matcher: "Bash|Write",
        hooks: [{ type: "command", command: "python3 ${CLAUDE_PLUGIN_ROOT}/hooks/blocking/pre_tool_use_dispatcher.py" }],
      }],
    },
  });
  const constantsRoot = path.join(fixture.canonicalHooksRoot, "hooks_constants");
  writeHookFile(fixture.canonicalHooksRoot, "blocking/pre_tool_use_dispatcher.py");
  mkdirSync(constantsRoot, { recursive: true });
  writeFileSync(
    path.join(constantsRoot, "pre_tool_use_dispatcher_constants.py"),
    [
      'BASH_TOOL_NAME = "Bash"',
      "ALL_BASH_TOOL_NAMES = frozenset({BASH_TOOL_NAME})",
      "ALL_HOSTED_HOOK_ENTRIES = (",
      'HostedHookEntry(script_relative_path="blocking/shell_substitution_blocker.py", applicable_tool_names=ALL_BASH_TOOL_NAMES),',
      ")",
    ].join("\n"),
    "utf8",
  );
  try {
    const report = auditHooks({ repositoryRoot: fixture.fixtureRoot });
    const shellGate = report.hostedRegistrations.find(({ target }) =>
      target.endsWith("shell_substitution_blocker.py"),
    );
    assert.equal(shellGate.matcher, "Bash");
  } finally {
    rmSync(fixture.fixtureRoot, { force: true, recursive: true });
  }
});

test("omits untrusted lifecycle prose from output", () => {
  const temporaryRoot = mkdtempSync(path.join(tmpdir(), "hook-audit-"));
  const catalogPath = path.join(temporaryRoot, "lifecycle.json");
  const privateText = "PRIVATE_TOKEN python3 C:/Users/example/private.py";
  const catalog = {
    hooks: {
      "script:blocking/code_rules_enforcer.py": {
        lifecycle: "move_to_linter",
        reason: privateText,
        replacement: privateText,
      },
    },
  };
  writeFileSync(catalogPath, JSON.stringify(catalog), "utf8");
  try {
    const rendered = JSON.stringify(auditHooks({ catalogPath, repositoryRoot }));
    assert.equal(rendered.includes(privateText), false);
  } finally {
    rmSync(temporaryRoot, { force: true, recursive: true });
  }
});

test("classifies installed-only targets", () => {
  const fixture = createAuditFixture();
  const temporaryRoot = fixture.fixtureRoot;
  const claudeRoot = path.join(fixture.homeDirectory, ".claude");
  const codexRoot = path.join(fixture.homeDirectory, ".codex");
  const installedOnly = {
    hooks: {
      SessionStart: [{ hooks: [{ command: "node cleanup.mjs", type: "command" }], matcher: "" }],
    },
  };
  writeJson(path.join(claudeRoot, "settings.json"), installedOnly);
  writeJson(path.join(codexRoot, "hooks.json"), { hooks: {} });
  const catalogPath = path.join(temporaryRoot, "lifecycle.json");
  writeFileSync(catalogPath, '{"hooks":{}}', "utf8");
  try {
    const report = auditHooks({
      catalogPath,
      homeDirectory: fixture.homeDirectory,
      includeInstalled: true,
      requireNonblocking: true,
      repositoryRoot: temporaryRoot,
    });
    const missingTargets = new Set(
      report.findings.filter(({ code }) => code === "UNCLASSIFIED_HOOK").map(({ target }) => target),
    );
    assert.equal(missingTargets.has("external:cleanup.mjs"), true);
  } finally {
    rmSync(temporaryRoot, { force: true, recursive: true });
  }
});

test("reads dispatcher children from the installed hook tree", () => {
  const fixture = createAuditFixture();
  const temporaryRoot = fixture.fixtureRoot;
  const claudeRoot = path.join(fixture.homeDirectory, ".claude");
  const installedHooks = path.join(claudeRoot, "hooks");
  const constantsRoot = path.join(installedHooks, "hooks_constants");
  const blockingRoot = path.join(installedHooks, "blocking");
  mkdirSync(constantsRoot, { recursive: true });
  mkdirSync(blockingRoot, { recursive: true });
  const config = {
    hooks: {
      PreToolUse: [{
        hooks: [{
          command: "python3 ${CLAUDE_PLUGIN_ROOT}/hooks/blocking/pre_tool_use_dispatcher.py",
          type: "command",
        }],
        matcher: "Write",
      }],
    },
  };
  const roster = [
    'WRITE_TOOL_NAME = "Write"',
    "ALL_WRITE_TOOL_NAMES = frozenset({WRITE_TOOL_NAME})",
    "ALL_HOSTED_HOOK_ENTRIES = (",
    'HostedHookEntry(script_relative_path="blocking/installed_only.py", applicable_tool_names=ALL_WRITE_TOOL_NAMES),',
    ")",
  ].join("\n");
  writeJson(path.join(claudeRoot, "settings.json"), config);
  writeFileSync(path.join(constantsRoot, "pre_tool_use_dispatcher_constants.py"), roster, "utf8");
  writeFileSync(path.join(blockingRoot, "pre_tool_use_dispatcher.py"), "", "utf8");
  writeJson(path.join(fixture.homeDirectory, ".codex", "hooks.json"), { hooks: {} });
  try {
    const report = auditHooks({
      homeDirectory: fixture.homeDirectory,
      includeInstalled: true,
      repositoryRoot: temporaryRoot,
    });
    assert.equal(
      report.installedLogicalRegistrations.some(({ target }) => target.endsWith("installed_only.py")),
      true,
    );
    assert.equal(
      report.findings.some(({ code, target }) =>
        code === "MISSING_HOOK_TARGET" && target === "script:blocking/installed_only.py",
      ),
      true,
    );
  } finally {
    rmSync(temporaryRoot, { force: true, recursive: true });
  }
});

test("reports missing installed dispatcher targets", () => {
  const fixture = createAuditFixture({
    claudeHooks: {
      hooks: {
        PreToolUse: [{
          matcher: "Write",
          hooks: [{
            type: "command",
            command: "python3 ${CLAUDE_PLUGIN_ROOT}/hooks/blocking/pre_tool_use_dispatcher.py",
          }],
        }],
      },
    },
  });
  const constantsPath = path.join(
    fixture.homeDirectory,
    ".claude",
    "hooks",
    "hooks_constants",
    "pre_tool_use_dispatcher_constants.py",
  );
  mkdirSync(path.dirname(constantsPath), { recursive: true });
  writeFileSync(constantsPath, "ALL_HOSTED_HOOK_ENTRIES = ()\n", "utf8");
  try {
    const report = auditHooks({
      homeDirectory: fixture.homeDirectory,
      includeInstalled: true,
      repositoryRoot: fixture.fixtureRoot,
    });
    assert.equal(
      report.findings.some(({ code, scope, target }) =>
        code === "MISSING_HOOK_TARGET" &&
        scope === "claude" &&
        target === "script:blocking/pre_tool_use_dispatcher.py",
      ),
      true,
    );
  } finally {
    rmSync(fixture.fixtureRoot, { force: true, recursive: true });
  }
});

test("rejects an installed-only registration without nonblocking lifecycle", () => {
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
    const report = auditHooks({
      catalogPath,
      homeDirectory: fixture.homeDirectory,
      includeInstalled: true,
      requireNonblocking: true,
      repositoryRoot: fixture.fixtureRoot,
    });
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

test("checks canonical managed parity for Codex registrations", () => {
  const fixture = createAuditFixture({
    canonicalHooks: {
      PreToolUse: [{
        matcher: "Write",
        hooks: [{ type: "command", command: "python3 ${CLAUDE_PLUGIN_ROOT}/hooks/blocking/write_existing_file_blocker.py" }],
      }],
    },
  });
  try {
    const report = auditHooks({
      homeDirectory: fixture.homeDirectory,
      includeInstalled: true,
      repositoryRoot: fixture.fixtureRoot,
    });
    assert.equal(
      report.findings.some(({ code, scope, target }) =>
        code === "MISSING_MANAGED_REGISTRATION" &&
        scope === "codex" &&
        target === "script:blocking/write_existing_file_blocker.py",
      ),
      true,
    );
  } finally {
    rmSync(fixture.fixtureRoot, { force: true, recursive: true });
  }
});

test("compares managed registrations by event, matcher, and target", () => {
  const command = "python3 ${CLAUDE_PLUGIN_ROOT}/hooks/blocking/write_existing_file_blocker.py";
  const fixture = createAuditFixture({
    canonicalHooks: {
      PreToolUse: [{ matcher: "Write", hooks: [{ type: "command", command }] }],
    },
    claudeHooks: {
      hooks: {
        PostToolUse: [{ matcher: "Read", hooks: [{ type: "command", command }] }],
      },
    },
    codexHooks: {
      hooks: {
        PreToolUse: [{ matcher: "Write", hooks: [{ type: "command", command }] }],
      },
    },
  });
  writeHookFile(path.join(fixture.homeDirectory, ".claude", "hooks"), "blocking/write_existing_file_blocker.py");
  writeHookFile(path.join(fixture.homeDirectory, ".codex", "hooks"), "blocking/write_existing_file_blocker.py");
  try {
    const report = auditHooks({
      homeDirectory: fixture.homeDirectory,
      includeInstalled: true,
      repositoryRoot: fixture.fixtureRoot,
    });
    assert.equal(
      report.findings.some(({ code, scope, target }) =>
        code === "MISSING_MANAGED_REGISTRATION" &&
        scope === "claude" &&
        target === "script:blocking/write_existing_file_blocker.py",
      ),
      true,
    );
    assert.equal(
      report.findings.some(({ code, scope }) =>
        code === "MISSING_MANAGED_REGISTRATION" && scope === "codex",
      ),
      false,
    );
  } finally {
    rmSync(fixture.fixtureRoot, { force: true, recursive: true });
  }
});

test("finds default Git hooks from a worktree", () => {
  const sourceRoot = mkdtempSync(path.join(tmpdir(), "hook-audit-git-"));
  const worktreeRoot = path.join(sourceRoot, "worktree");
  const globalConfigPath = path.join(sourceRoot, "global-gitconfig");
  writeFileSync(globalConfigPath, "", "utf8");
  const environment = { ...process.env, GIT_CONFIG_GLOBAL: globalConfigPath, GIT_CONFIG_NOSYSTEM: "1" };
  const previousGlobalConfig = process.env.GIT_CONFIG_GLOBAL;
  const previousNoSystem = process.env.GIT_CONFIG_NOSYSTEM;
  process.env.GIT_CONFIG_GLOBAL = globalConfigPath;
  process.env.GIT_CONFIG_NOSYSTEM = "1";
  try {
    runGit(sourceRoot, ["init", "--quiet"], environment);
    runGit(sourceRoot, ["config", "user.email", "hook-audit@example.invalid"], environment);
    runGit(sourceRoot, ["config", "user.name", "Hook Audit"], environment);
    runGit(sourceRoot, ["commit", "--quiet", "--allow-empty", "-m", "fixture"], environment);
    runGit(sourceRoot, ["worktree", "add", "--quiet", worktreeRoot, "HEAD"], environment);
    writeHookFile(path.join(sourceRoot, ".git", "hooks"), "pre-commit");
    writeHookFile(path.join(sourceRoot, ".git", "hooks"), "post-commit");
    const canonicalHooksRoot = path.join(worktreeRoot, "packages", "claude-dev-env", "hooks");
    const homeDirectory = path.join(sourceRoot, "home");
    mkdirSync(canonicalHooksRoot, { recursive: true });
    mkdirSync(path.join(homeDirectory, ".claude", "hooks"), { recursive: true });
    mkdirSync(path.join(homeDirectory, ".codex", "hooks"), { recursive: true });
    writeJson(path.join(canonicalHooksRoot, "hooks.json"), { hooks: {} });
    writeJson(path.join(homeDirectory, ".claude", "settings.json"), { hooks: {} });
    writeJson(path.join(homeDirectory, ".codex", "hooks.json"), { hooks: {} });
    const report = auditHooks({
      homeDirectory,
      includeInstalled: true,
      requireNonblocking: true,
      repositoryRoot: worktreeRoot,
    });
    assert.deepEqual(report.gitRegistrations.map(({ target }) => target), [
      "git:pre-commit",
      "git:post-commit",
    ]);
    assert.equal(
      report.findings.some(({ code, target }) =>
        code === "NATIVE_GIT_BLOCKING_HOOK" && target === "git:pre-commit",
      ),
      true,
    );
  } finally {
    if (previousGlobalConfig === undefined) delete process.env.GIT_CONFIG_GLOBAL;
    else process.env.GIT_CONFIG_GLOBAL = previousGlobalConfig;
    if (previousNoSystem === undefined) delete process.env.GIT_CONFIG_NOSYSTEM;
    else process.env.GIT_CONFIG_NOSYSTEM = previousNoSystem;
    rmSync(sourceRoot, { force: true, recursive: true });
  }
});
