#!/usr/bin/env node
/**
 * Opt-in live Grok capability evals (E1–E5).
 *
 * Never wired into package.json `test`. Requires GROK_CAPABILITY_EVALS=1 or --run.
 */
import { spawnSync } from 'node:child_process';
import {
  existsSync,
  mkdtempSync,
  readFileSync,
  rmSync,
  writeFileSync,
} from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { randomUUID } from 'node:crypto';
import { fileURLToPath } from 'node:url';

const OPT_IN_ENV = 'GROK_CAPABILITY_EVALS';
const OPT_IN_VALUE = '1';
const RUN_FLAG = '--run';
const GROK_BINARY = process.env.GROK_BIN || 'grok';
const DEFAULT_MAX_TURNS = 12;
const SPAWN_MAX_TURNS = 20;
const SKILL_MAX_TURNS = 16;
const WRITE_MAX_TURNS = 12;
const WORKFLOW_MAX_TURNS = 8;
const PROBE_FILE_NAME = 'capability-probe-write.txt';
const PROBE_FILE_CONTENTS = 'capability-probe-ok';
const HOOKS_LOG_NAME = 'hooks.log';

const E1_PROMPT = `You are running a capability inventory. Do not edit files.

1. Inspect your available tools.
2. Check whether agents and skills directories exist under the user's Claude config (typical locations: ~/.claude/agents, ~/.claude/skills).

Reply with ONLY one JSON object and nothing else:
{
  "can_spawn_subagent_tool": <true if a spawn_subagent tool is available>,
  "tool_names": [<string tool names>],
  "agents_dir_exists": <bool>,
  "skills_dir_exists": <bool>
}`;

const E2_PROMPT = `You are measuring spawn_subagent.

1. Use spawn_subagent (or the equivalent agent-spawn tool) once.
2. Instruct the child to print exactly SPAWN_OK on its first line, then list basenames from the agents directory under the user's Claude config (for example ~/.claude/agents).
3. Wait for the child to finish.

Reply with ONLY one JSON object and nothing else:
{
  "spawn_succeeded": <true if the child ran and returned SPAWN_OK>,
  "child_excerpt": "<short excerpt of child output>"
}`;

const E3_PROMPT = `You are measuring skill readability under an agent definition.

1. Read any one skill entrypoint under the user's Claude skills path (for example ~/.claude/skills/*/SKILL.md). Prefer a short file if several exist.
2. Confirm you loaded an agent definition for this run (this process was started with --agent).

Reply with ONLY one JSON object and nothing else:
{
  "skill_read_ok": <true if you read a skill file's contents>,
  "skill_path": "<path you read or empty string>",
  "agent_definition_loaded": <true if an agent definition is active>
}`;

const E4_PROMPT = `You are measuring write capability in the current working directory.

1. Write a file named ${PROBE_FILE_NAME} in the current working directory with exact contents: ${PROBE_FILE_CONTENTS}
2. Do not write anything else.

Reply with ONLY one JSON object and nothing else:
{
  "write_succeeded": <true if the write completed>,
  "written_path": "<absolute or relative path written>"
}`;

const E5_PROMPT = `You are measuring whether a Claude/GSD Workflow tool is available.

Inspect your tool list. Do not invent a Workflow tool.

Reply with ONLY one JSON object and nothing else:
{
  "has_workflow_tool": <true only if a Workflow tool is present>,
  "result": <"has_tool" or "no_tool">
}`;

function isOptedIn(allArguments) {
  if (allArguments.includes(RUN_FLAG)) {
    return true;
  }
  return process.env[OPT_IN_ENV] === OPT_IN_VALUE;
}

function printOptInHelp() {
  console.log(
    [
      'Grok capability evals are opt-in only (not part of npm test / CI).',
      '',
      'Run with either:',
      `  ${OPT_IN_ENV}=${OPT_IN_VALUE} node skills/grokify/evals/run-capability-evals.mjs`,
      '  node skills/grokify/evals/run-capability-evals.mjs --run',
      '',
      'See skills/grokify/evals/README.md.',
    ].join('\n'),
  );
}

function mintLeaderSocketPath(runDirectory) {
  return join(runDirectory, `leader-${randomUUID()}.sock`);
}

function writePromptFile(runDirectory, evalName, promptText) {
  const promptPath = join(runDirectory, `${evalName}-prompt.md`);
  writeFileSync(promptPath, promptText, 'utf8');
  return promptPath;
}

function buildGrokArguments({
  promptPath,
  workingDirectory,
  leaderSocketPath,
  maxTurns,
  agentName,
}) {
  const allArguments = [
    '--prompt-file',
    promptPath,
    '--cwd',
    workingDirectory,
    '--output-format',
    'json',
    '--always-approve',
    '--max-turns',
    String(maxTurns),
    '--permission-mode',
    'bypassPermissions',
    '--leader-socket',
    leaderSocketPath,
  ];
  if (agentName) {
    allArguments.push('--agent', agentName);
  }
  return allArguments;
}

function runGrok({
  promptPath,
  workingDirectory,
  leaderSocketPath,
  maxTurns,
  agentName,
}) {
  const allArguments = buildGrokArguments({
    promptPath,
    workingDirectory,
    leaderSocketPath,
    maxTurns,
    agentName,
  });
  const processResult = spawnSync(GROK_BINARY, allArguments, {
    encoding: 'utf8',
    cwd: workingDirectory,
    maxBuffer: 20 * 1024 * 1024,
    windowsHide: true,
  });
  return {
    exitCode: processResult.status,
    stdout: processResult.stdout || '',
    stderr: processResult.stderr || '',
    error: processResult.error || null,
  };
}

export function tryParseJsonObject(text) {
  const trimmed = text.trim();
  if (!trimmed) {
    return null;
  }
  try {
    const parsed = JSON.parse(trimmed);
    if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
      return parsed;
    }
  } catch {
    // fall through to extraction
  }
  const firstBrace = trimmed.indexOf('{');
  const lastBrace = trimmed.lastIndexOf('}');
  if (firstBrace === -1 || lastBrace <= firstBrace) {
    return null;
  }
  try {
    return JSON.parse(trimmed.slice(firstBrace, lastBrace + 1));
  } catch {
    return null;
  }
}

function extractStringField(parsedEnvelope, fieldName) {
  if (!parsedEnvelope || typeof parsedEnvelope !== 'object') {
    return null;
  }
  const fieldValue = parsedEnvelope[fieldName];
  if (typeof fieldValue === 'string') {
    return fieldValue;
  }
  return null;
}

export function extractResultText(stdout) {
  const trimmed = stdout.trim();
  if (!trimmed) {
    return '';
  }
  try {
    const parsed = JSON.parse(trimmed);
    if (Array.isArray(parsed)) {
      const resultEvent = parsed.find(
        (eachEvent) =>
          eachEvent &&
          typeof eachEvent === 'object' &&
          eachEvent.type === 'result' &&
          typeof eachEvent.result === 'string',
      );
      if (resultEvent) {
        return resultEvent.result;
      }
      const textChunks = [];
      for (const eachEvent of parsed) {
        if (!eachEvent || typeof eachEvent !== 'object') {
          continue;
        }
        if (typeof eachEvent.result === 'string') {
          textChunks.push(eachEvent.result);
        }
        if (typeof eachEvent.text === 'string') {
          textChunks.push(eachEvent.text);
        }
        if (typeof eachEvent.content === 'string') {
          textChunks.push(eachEvent.content);
        }
      }
      if (textChunks.length > 0) {
        return textChunks.join('\n');
      }
    }
    if (parsed && typeof parsed === 'object') {
      const maybeResult = extractStringField(parsed, 'result');
      if (maybeResult !== null) {
        return maybeResult;
      }
      const maybeMessage = extractStringField(parsed, 'message');
      if (maybeMessage !== null) {
        return maybeMessage;
      }
      const maybeText = extractStringField(parsed, 'text');
      if (maybeText !== null) {
        return maybeText;
      }
    }
  } catch {
    // stdout is plain text
  }
  return trimmed;
}

export function parsePayload(stdout) {
  const resultText = extractResultText(stdout);
  return tryParseJsonObject(resultText) || tryParseJsonObject(stdout);
}

function assertCondition(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

function resolveDefaultAgentName() {
  return process.env.GROK_CAPABILITY_EVAL_AGENT || 'Explore';
}

function runEvalOne(runDirectory) {
  const promptPath = writePromptFile(runDirectory, 'e1', E1_PROMPT);
  const processResult = runGrok({
    promptPath,
    workingDirectory: runDirectory,
    leaderSocketPath: mintLeaderSocketPath(runDirectory),
    maxTurns: DEFAULT_MAX_TURNS,
  });
  assertCondition(
    processResult.error === null,
    `E1: failed to launch grok: ${processResult.error}`,
  );
  assertCondition(
    processResult.exitCode === 0,
    `E1: grok exit ${processResult.exitCode}\n${processResult.stderr}\n${processResult.stdout}`,
  );
  const payload = parsePayload(processResult.stdout);
  assertCondition(payload !== null, `E1: could not parse JSON payload from grok output`);
  assertCondition(
    payload.can_spawn_subagent_tool === true,
    `E1: expected can_spawn_subagent_tool === true, got ${JSON.stringify(payload.can_spawn_subagent_tool)}`,
  );
  const allToolNames = Array.isArray(payload.tool_names)
    ? payload.tool_names.map(String)
    : [];
  assertCondition(
    allToolNames.includes('spawn_subagent'),
    `E1: expected tool_names to include spawn_subagent, got ${JSON.stringify(allToolNames)}`,
  );
  return payload;
}

function runEvalTwo(runDirectory) {
  const promptPath = writePromptFile(runDirectory, 'e2', E2_PROMPT);
  const processResult = runGrok({
    promptPath,
    workingDirectory: runDirectory,
    leaderSocketPath: mintLeaderSocketPath(runDirectory),
    maxTurns: SPAWN_MAX_TURNS,
  });
  assertCondition(
    processResult.error === null,
    `E2: failed to launch grok: ${processResult.error}`,
  );
  assertCondition(
    processResult.exitCode === 0,
    `E2: grok exit ${processResult.exitCode}\n${processResult.stderr}\n${processResult.stdout}`,
  );
  const payload = parsePayload(processResult.stdout);
  assertCondition(payload !== null, `E2: could not parse JSON payload from grok output`);
  assertCondition(
    payload.spawn_succeeded === true,
    `E2: expected spawn_succeeded === true, got ${JSON.stringify(payload.spawn_succeeded)}`,
  );
  return payload;
}

function runEvalThree(runDirectory) {
  const promptPath = writePromptFile(runDirectory, 'e3', E3_PROMPT);
  const processResult = runGrok({
    promptPath,
    workingDirectory: runDirectory,
    leaderSocketPath: mintLeaderSocketPath(runDirectory),
    maxTurns: SKILL_MAX_TURNS,
    agentName: resolveDefaultAgentName(),
  });
  assertCondition(
    processResult.error === null,
    `E3: failed to launch grok: ${processResult.error}`,
  );
  assertCondition(
    processResult.exitCode === 0,
    `E3: grok exit ${processResult.exitCode}\n${processResult.stderr}\n${processResult.stdout}`,
  );
  const payload = parsePayload(processResult.stdout);
  assertCondition(payload !== null, `E3: could not parse JSON payload from grok output`);
  assertCondition(
    payload.skill_read_ok === true,
    `E3: expected skill_read_ok === true, got ${JSON.stringify(payload.skill_read_ok)}`,
  );
  return payload;
}

function runEvalFour(runDirectory) {
  const promptPath = writePromptFile(runDirectory, 'e4', E4_PROMPT);
  const processResult = runGrok({
    promptPath,
    workingDirectory: runDirectory,
    leaderSocketPath: mintLeaderSocketPath(runDirectory),
    maxTurns: WRITE_MAX_TURNS,
  });
  assertCondition(
    processResult.error === null,
    `E4: failed to launch grok: ${processResult.error}`,
  );
  assertCondition(
    processResult.exitCode === 0,
    `E4: grok exit ${processResult.exitCode}\n${processResult.stderr}\n${processResult.stdout}`,
  );
  const payload = parsePayload(processResult.stdout);
  assertCondition(payload !== null, `E4: could not parse JSON payload from grok output`);
  const probePath = join(runDirectory, PROBE_FILE_NAME);
  const isProbePresent = existsSync(probePath);
  assertCondition(
    isProbePresent || payload.write_succeeded === true,
    `E4: probe write did not succeed (file missing and write_succeeded not true)`,
  );
  if (isProbePresent) {
    const probeContents = readFileSync(probePath, 'utf8');
    assertCondition(
      probeContents.includes(PROBE_FILE_CONTENTS),
      `E4: probe file contents mismatch: ${JSON.stringify(probeContents)}`,
    );
  }
  const hooksLogPath = join(runDirectory, HOOKS_LOG_NAME);
  let hooksNote = 'hooks.log not present (soft check skipped)';
  if (existsSync(hooksLogPath)) {
    const hooksLogText = readFileSync(hooksLogPath, 'utf8');
    const hasGlobalSettings = hooksLogText.includes('global/settings');
    const hasPreToolUse = hooksLogText.toLowerCase().includes('pre_tool_use');
    hooksNote =
      hasGlobalSettings && hasPreToolUse
        ? 'hooks.log contains global/settings and pre_tool_use'
        : 'hooks.log present but missing expected markers (soft)';
  }
  return { payload, hooksNote, isProbePresent };
}

function runEvalFive(runDirectory) {
  const promptPath = writePromptFile(runDirectory, 'e5', E5_PROMPT);
  const processResult = runGrok({
    promptPath,
    workingDirectory: runDirectory,
    leaderSocketPath: mintLeaderSocketPath(runDirectory),
    maxTurns: WORKFLOW_MAX_TURNS,
  });
  assertCondition(
    processResult.error === null,
    `E5: failed to launch grok: ${processResult.error}`,
  );
  assertCondition(
    processResult.exitCode === 0,
    `E5: grok exit ${processResult.exitCode}\n${processResult.stderr}\n${processResult.stdout}`,
  );
  const payload = parsePayload(processResult.stdout);
  assertCondition(payload !== null, `E5: could not parse JSON payload from grok output`);
  const isWorkflowAbsent =
    payload.has_workflow_tool === false || payload.result === 'no_tool';
  assertCondition(
    isWorkflowAbsent,
    `E5: expected has_workflow_tool === false or result === "no_tool", got ${JSON.stringify(payload)}`,
  );
  return payload;
}

function main() {
  if (!isOptedIn(process.argv.slice(2))) {
    printOptInHelp();
    process.exit(0);
  }

  const runDirectory = mkdtempSync(join(tmpdir(), 'grok-capability-evals-'));
  console.log(`run directory: ${runDirectory}`);

  try {
    console.log('E1 tool inventory...');
    const e1Payload = runEvalOne(runDirectory);
    console.log('E1 ok', JSON.stringify(e1Payload));

    console.log('E2 spawn_subagent...');
    const e2Payload = runEvalTwo(runDirectory);
    console.log('E2 ok', JSON.stringify(e2Payload));

    console.log('E3 --agent + skill read...');
    const e3Payload = runEvalThree(runDirectory);
    console.log('E3 ok', JSON.stringify(e3Payload));

    console.log('E4 probe write...');
    const e4Outcome = runEvalFour(runDirectory);
    console.log(
      'E4 ok',
      JSON.stringify({
        payload: e4Outcome.payload,
        isProbePresent: e4Outcome.isProbePresent,
        hooksNote: e4Outcome.hooksNote,
      }),
    );

    console.log('E5 workflow tool absence...');
    const e5Payload = runEvalFive(runDirectory);
    console.log('E5 ok', JSON.stringify(e5Payload));

    console.log('ALL CAPABILITY EVALS PASSED');
  } catch (failure) {
    console.error(String(failure && failure.stack ? failure.stack : failure));
    process.exitCode = 1;
  } finally {
    try {
      rmSync(runDirectory, { recursive: true, force: true });
    } catch {
      // best-effort cleanup
    }
  }
}

function isDirectExecution() {
  const entryArgument = process.argv[1];
  if (!entryArgument) {
    return false;
  }
  return resolve(fileURLToPath(import.meta.url)) === resolve(entryArgument);
}

if (isDirectExecution()) {
  main();
}
