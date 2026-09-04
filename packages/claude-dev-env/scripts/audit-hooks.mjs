import { spawnSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { homedir } from "node:os";
import path from "node:path";

const expectedCounts = Object.freeze({ direct: 32, dispatchers: 5, hosted: 43 });
const dispatcherSpecs = Object.freeze([
  ["script:blocking/pre_tool_use_dispatcher.py", "hooks_constants/pre_tool_use_dispatcher_constants.py", "ALL_HOSTED_HOOK_ENTRIES"],
  ["script:blocking/bash_pre_tool_use_dispatcher.py", "hooks_constants/bash_pre_tool_use_dispatcher_constants.py", "ALL_BASH_HOSTED_HOOK_ENTRIES"],
  ["script:blocking/stop_dispatcher.py", "hooks_constants/stop_dispatcher_constants.py", "ALL_STOP_HOSTED_HOOK_PATHS"],
  ["script:validation/post_tool_use_dispatcher.py", "hooks_constants/post_tool_use_dispatcher_constants.py", "ALL_POST_HOSTED_HOOK_ENTRIES"],
  ["script:blocking/bash_post_call_dispatcher.py", "hooks_constants/bash_post_call_dispatcher_constants.py", "ALL_BASH_POST_TOOL_USE_HOSTED_HOOK_ENTRIES"],
]);
const lifecycleNames = new Set([
  "delete",
  "keep_boundary_check",
  "keep_nonblocking_automation",
  "move_to_ci",
  "move_to_explicit_command",
  "move_to_linter",
]);

function normalizeMatcher(rawMatcher) {
  return typeof rawMatcher === "string" && rawMatcher
    ? rawMatcher.split("|").sort().join("|")
    : "*";
}

function targetFromCommand(command, scope, event, ordinal) {
  const normalized = command.replaceAll("\\", "/");
  const hookMarker = "/hooks/";
  if (normalized.includes(hookMarker)) {
    const relative = normalized.split(hookMarker).at(-1).split(/[\s"']/u, 1)[0];
    if (relative.endsWith(".py")) return `script:${relative}`;
  }
  const importMatch = /\bfrom\s+([A-Za-z_][\w.]*)\s+import\s+main\b/u.exec(command);
  if (importMatch) return `script:${importMatch[1].replaceAll(".", "/")}.py`;
  const scriptMatches = [...normalized.matchAll(/(?:^|\s)["']?([^"'/\s]+\.(?:exe|js|mjs|ps1|py))\b/gu)];
  if (scriptMatches.length) return `external:${scriptMatches.at(-1)[1]}`;
  return `external:${scope}:${event}:${ordinal}`;
}

function readDirect(configPath, scope) {
  const parsed = JSON.parse(readFileSync(configPath, "utf8"));
  const records = [];
  for (const [event, groups] of Object.entries(parsed.hooks ?? {})) {
    for (const group of Array.isArray(groups) ? groups : []) {
      appendGroupRecords(records, scope, event, group);
    }
  }
  return records;
}

function appendGroupRecords(records, scope, event, group) {
  const matcher = normalizeMatcher(group.matcher);
  for (const hook of Array.isArray(group.hooks) ? group.hooks : []) {
    if (hook?.type !== "command" || typeof hook.command !== "string") continue;
    const ordinal = records.length;
    const target = targetFromCommand(hook.command, scope, event, ordinal);
    const isDispatcher = dispatcherSpecs.some(([knownTarget]) => knownTarget === target);
    records.push({
      event,
      matcher,
      ordinal,
      role: isDispatcher ? "dispatcher" : "hook",
      scope,
      target,
      timeoutSeconds: Number.isInteger(hook.timeout) ? hook.timeout : null,
    });
  }
}

function assignmentBody(source, rosterName) {
  const rosterOffset = source.lastIndexOf(rosterName);
  if (rosterOffset < 0) throw new Error(`missing roster ${rosterName}`);
  const equalsOffset = source.indexOf("=", rosterOffset);
  const openOffset = source.indexOf("(", equalsOffset);
  if (equalsOffset < 0 || openOffset < 0) throw new Error(`invalid roster ${rosterName}`);
  const closeOffset = matchingParenthesis(source, openOffset);
  return source.slice(openOffset + 1, closeOffset);
}

function matchingParenthesis(source, openOffset) {
  let depth = 0;
  let quote = "";
  for (let offset = openOffset; offset < source.length; offset += 1) {
    const character = source[offset];
    const previous = source[offset - 1];
    if (quote && character === quote && previous !== "\\") quote = "";
    else if (!quote && (character === '"' || character === "'")) quote = character;
    else if (!quote && character === "(") depth += 1;
    else if (!quote && character === ")") depth -= 1;
    if (depth === 0) return offset;
  }
  throw new Error("unclosed roster");
}

function topLevelEntries(source) {
  const entries = [];
  let depth = 0;
  let quote = "";
  let start = 0;
  for (let offset = 0; offset < source.length; offset += 1) {
    const character = source[offset];
    const previous = source[offset - 1];
    if (quote && character === quote && previous !== "\\") quote = "";
    else if (!quote && (character === '"' || character === "'")) quote = character;
    else if (!quote && /[([{]/u.test(character)) depth += 1;
    else if (!quote && /[\])}]/u.test(character)) depth -= 1;
    else if (!quote && character === "," && depth === 0) {
      entries.push(source.slice(start, offset));
      start = offset + 1;
    }
  }
  entries.push(source.slice(start));
  return entries.filter((entry) => entry.trim());
}

function toolMatchers(source) {
  const matchers = new Map();
  for (const match of source.matchAll(/\b([A-Z][A-Z0-9_]*_TOOL_NAME)\s*=\s*["']([^"']+)["']/gu)) {
    matchers.set(match[1], new Set([match[2]]));
  }
  const collections = [...source.matchAll(/\b([A-Z][A-Z0-9_]*_TOOL_NAMES)\s*(?::[^=]+)?=\s*frozenset\s*\(/gu)];
  for (const collection of collections) {
    const openOffset = source.indexOf("(", collection.index + collection[0].indexOf("frozenset"));
    const body = source.slice(openOffset + 1, matchingParenthesis(source, openOffset));
    const names = new Set();
    for (const token of body.match(/\b[A-Z][A-Z0-9_]+\b/gu) ?? []) {
      for (const toolName of matchers.get(token) ?? []) names.add(toolName);
    }
    matchers.set(collection[1], names);
  }
  return matchers;
}

function rosterEntries(hooksRoot, constantsPath, rosterName) {
  const source = readFileSync(path.join(hooksRoot, constantsPath), "utf8");
  const body = assignmentBody(source, rosterName);
  const matchers = toolMatchers(source);
  return topLevelEntries(body).map((expression) => {
    const targetMatch = /["']([^"']+\.py)["']/u.exec(expression);
    if (!targetMatch) throw new Error(`invalid roster entry ${rosterName}`);
    const names = new Set();
    for (const token of expression.match(/\b[A-Z][A-Z0-9_]+\b/gu) ?? []) {
      for (const toolName of matchers.get(token) ?? []) names.add(toolName);
    }
    return {
      matcher: names.size ? [...names].sort().join("|") : null,
      target: `script:${targetMatch[1].replaceAll("\\", "/")}`,
    };
  });
}

function expandHosted(directRecords, hooksRoot) {
  const parents = new Map(
    directRecords.filter(({ role }) => role === "dispatcher").map((record) => [record.target, record]),
  );
  const hosted = [];
  for (const [dispatcherTarget, constantsPath, rosterName] of dispatcherSpecs) {
    const parent = parents.get(dispatcherTarget);
    if (!parent) continue;
    const entries = rosterEntries(hooksRoot, constantsPath, rosterName);
    for (const entry of entries) {
      hosted.push({
        event: parent.event,
        matcher: entry.matcher ?? parent.matcher,
        ordinal: hosted.length,
        parentTarget: parent.target,
        role: "hosted",
        scope: parent.scope,
        target: entry.target,
        timeoutSeconds: parent.timeoutSeconds,
      });
    }
  }
  return hosted;
}

function logicalRecords(directRecords, hostedRecords) {
  return [...directRecords.filter(({ role }) => role !== "dispatcher"), ...hostedRecords].sort(recordSort);
}

function recordSort(left, right) {
  const leftKey = [left.scope, left.event, left.matcher, left.target, left.role, left.ordinal].join("\0");
  const rightKey = [right.scope, right.event, right.matcher, right.target, right.role, right.ordinal].join("\0");
  return leftKey.localeCompare(rightKey);
}

function duplicateFindings(records, scope) {
  const counts = new Map();
  for (const record of records) {
    const key = [record.event, record.matcher, record.target].join("\0");
    counts.set(key, (counts.get(key) ?? 0) + 1);
  }
  return [...counts.entries()]
    .filter(([, count]) => count > 1)
    .map(([key, count]) => ({
      code: "DUPLICATE_EFFECTIVE_EXECUTION",
      message: `The same event, matcher, and target run ${count} times.`,
      scope,
      severity: "error",
      target: key.split("\0").at(-1),
    }));
}

function missingTargetFindings(records, hooksRoot, scope) {
  return records
    .filter(({ target }) => target.startsWith("script:"))
    .filter(({ target }) => !existsSync(path.join(hooksRoot, target.slice("script:".length))))
    .map(({ target }) => ({
      code: "MISSING_HOOK_TARGET",
      message: "The registered script is missing from the installed hook tree.",
      scope,
      severity: "error",
      target,
    }));
}

function missingManagedFindings(expectedRecords, installedRecords, scope) {
  const installedIdentities = new Set(installedRecords.map(recordIdentity));
  return expectedRecords
    .filter((record) => !installedIdentities.has(recordIdentity(record)))
    .map(({ target }) => ({
      code: "MISSING_MANAGED_REGISTRATION",
      message: "The installed configuration is missing a canonical registration.",
      scope,
      severity: "error",
      target,
    }));
}

function recordIdentity({ event, matcher, target }) {
  return [event, matcher, target].join("\0");
}

function readLifecycle(catalogPath) {
  if (!catalogPath) return [];
  const parsed = JSON.parse(readFileSync(catalogPath, "utf8"));
  return Object.entries(parsed.hooks ?? {}).map(([target, decision]) => {
    const safeTarget = /^(?:external:[A-Za-z0-9_.:-]+|git:(?:post-commit|pre-commit|pre-push)|script:[A-Za-z0-9_./-]+)$/u;
    if (!safeTarget.test(target) || !lifecycleNames.has(decision?.lifecycle) || !decision.reason) {
      throw new Error("invalid lifecycle entry");
    }
    return { lifecycle: decision.lifecycle, target };
  });
}

function lifecycleFindings(records, lifecycle) {
  const targets = new Set(records.map(({ target }) => target));
  const classified = new Set(lifecycle.map(({ target }) => target));
  const missing = [...targets].filter((target) => !classified.has(target));
  const stale = [...classified].filter((target) => !targets.has(target));
  return [
    ...missing.map((target) => ({
      code: "UNCLASSIFIED_HOOK",
      message: "The effective hook has no lifecycle decision.",
      scope: "catalog",
      severity: "error",
      target,
    })),
    ...stale.map((target) => ({
      code: "STALE_LIFECYCLE_ENTRY",
      message: "The lifecycle target is absent from the canonical graph.",
      scope: "catalog",
      severity: "warning",
      target,
    })),
  ];
}

function readInstalled(configPath, hooksRoot, scope) {
  if (!existsSync(configPath)) return { findings: [], logical: [], records: [] };
  const records = readDirect(configPath, scope);
  const hosted = expandHosted(records, hooksRoot);
  const logical = logicalRecords(records, hosted);
  return {
    findings: [
      ...duplicateFindings(logical, scope),
      ...missingTargetFindings([...records, ...hosted], hooksRoot, scope),
    ],
    logical,
    records,
  };
}

function activeGitHooks(repositoryRoot) {
  const gitQuery = spawnSync("git", ["rev-parse", "--git-path", "hooks"], {
    cwd: repositoryRoot,
    encoding: "utf8",
    shell: false,
    timeout: 10_000,
  });
  if (gitQuery.status !== 0) return [];
  const hooksPath = gitQuery.stdout?.trim();
  if (!hooksPath) return [];
  const hooksRoot = path.isAbsolute(hooksPath) ? hooksPath : path.resolve(repositoryRoot, hooksPath);
  return ["pre-commit", "pre-push", "post-commit"]
    .filter((name) => existsSync(path.join(hooksRoot, name)))
    .map((name, ordinal) => ({
      event: name,
      matcher: "*",
      ordinal,
      role: "native",
      scope: "git",
      target: `git:${name}`,
      timeoutSeconds: null,
    }));
}

function countFindings(directCount, dispatcherCount, hostedCount) {
  const actual = { direct: directCount, dispatchers: dispatcherCount, hosted: hostedCount };
  return Object.entries(expectedCounts)
    .filter(([name, expected]) => actual[name] !== expected)
    .map(([name, expected]) => ({
      code: `${name.toUpperCase()}_COUNT_DRIFT`,
      message: `Expected ${expected} entries and found ${actual[name]}.`,
      scope: "canonical",
      severity: "error",
      target: null,
    }));
}

export function auditHooks(options) {
  const repositoryRoot = path.resolve(options.repositoryRoot);
  const hooksRoot = path.join(repositoryRoot, "packages", "claude-dev-env", "hooks");
  const direct = readDirect(path.join(hooksRoot, "hooks.json"), "canonical");
  const hosted = expandHosted(direct, hooksRoot);
  const logical = logicalRecords(direct, hosted);
  const lifecycle = readLifecycle(options.catalogPath);
  const dispatcherCount = direct.filter(({ role }) => role === "dispatcher").length;
  const installed = options.includeInstalled
    ? installedAudit(options.homeDirectory ?? homedir(), repositoryRoot, logical)
    : { claudeCount: 0, codexCount: 0, findings: [], git: [], logical: [], records: [] };
  const allLogical = [...logical, ...installed.logical, ...installed.git];
  const findings = [
    ...countFindings(direct.length, dispatcherCount, hosted.length),
    ...duplicateFindings(logical, "canonical"),
    ...(options.catalogPath ? lifecycleFindings(allLogical, lifecycle) : []),
    ...installed.findings,
  ].sort((left, right) => JSON.stringify(left).localeCompare(JSON.stringify(right)));
  const targets = new Set(allLogical.map(({ target }) => target));
  const classified = new Set(lifecycle.map(({ target }) => target));
  return {
    directRegistrations: direct.sort(recordSort),
    findings,
    hostedRegistrations: hosted.sort(recordSort),
    installedRegistrations: installed.records.sort(recordSort),
    installedLogicalRegistrations: installed.logical.sort(recordSort),
    gitRegistrations: installed.git,
    lifecycle,
    logicalRegistrations: logical,
    schemaVersion: 1,
    summary: {
      claudeDirectCount: installed.claudeCount,
      codexDirectCount: installed.codexCount,
      directCount: direct.length,
      dispatcherCount,
      effectiveCount: hosted.length,
      findingCount: findings.length,
      gitHookCount: installed.git.length,
      lifecycleCount: lifecycle.length,
      logicalAssociationCount: logical.length,
      unclassifiedCount: options.catalogPath
        ? [...targets].filter((target) => !classified.has(target)).length
        : 0,
      uniqueTargetCount: targets.size,
    },
  };
}

function installedAudit(homeDirectory, repositoryRoot, canonicalLogical) {
  const claude = readInstalled(
    path.join(homeDirectory, ".claude", "settings.json"),
    path.join(homeDirectory, ".claude", "hooks"),
    "claude",
  );
  const codex = readInstalled(
    path.join(homeDirectory, ".codex", "hooks.json"),
    path.join(homeDirectory, ".codex", "hooks"),
    "codex",
  );
  const git = activeGitHooks(repositoryRoot);
  return {
    claudeCount: claude.records.length,
    codexCount: codex.records.length,
    findings: [
      ...claude.findings,
      ...codex.findings,
      ...missingManagedFindings(canonicalLogical, claude.logical, "claude"),
      ...missingManagedFindings(canonicalLogical, codex.logical, "codex"),
    ],
    git,
    logical: [...claude.logical, ...codex.logical],
    records: [...claude.records, ...codex.records],
  };
}
