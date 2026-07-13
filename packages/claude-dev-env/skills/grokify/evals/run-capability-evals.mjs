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
const SPAWN_MARKER = 'SPAWN_OK';
const GROK_SPAWN_TIMEOUT_MS = 600000;
const SPAWN_MAX_BUFFER_BYTES = 20 * 1024 * 1024;
const WORKFLOW_RESULT_NO_TOOL = 'no_tool';
const SPAWN_TIMEOUT_ERROR_CODE = 'ETIMEDOUT';

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
2. Instruct the child to print exactly ${SPAWN_MARKER} on its first line, then list basenames from the agents directory under the user's Claude config (for example ~/.claude/agents).
3. Wait for the child to finish.

Reply with ONLY one JSON object and nothing else:
{
  "spawn_succeeded": <true if the child ran and returned ${SPAWN_MARKER}>,
  "child_excerpt": "<excerpt of child output that includes its first line>"
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

function mintLeaderSocketPath(runDirectory, evalName) {
  return join(runDirectory, `leader-${evalName}.sock`);
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
    maxBuffer: SPAWN_MAX_BUFFER_BYTES,
    timeout: GROK_SPAWN_TIMEOUT_MS,
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
  if (firstBrace === -1) {
    return null;
  }
  for (
    let closingBrace = trimmed.lastIndexOf('}');
    closingBrace > firstBrace;
    closingBrace = trimmed.lastIndexOf('}', closingBrace - 1)
  ) {
    try {
      const parsed = JSON.parse(trimmed.slice(firstBrace, closingBrace + 1));
      if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
        return parsed;
      }
    } catch {
      // try the next-shorter closing-brace candidate
    }
  }
  return null;
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
      const resultEvent = parsed.findLast(
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
        const eventText =
          typeof eachEvent.result === 'string'
            ? eachEvent.result
            : typeof eachEvent.text === 'string'
              ? eachEvent.text
              : typeof eachEvent.content === 'string'
                ? eachEvent.content
                : null;
        if (eventText !== null) {
          textChunks.push(eventText);
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
      const maybeText = extractStringField(parsed, 'text');
      if (maybeText !== null) {
        return maybeText;
      }
      const maybeMessage = extractStringField(parsed, 'message');
      if (maybeMessage !== null) {
        return maybeMessage;
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

function describeLaunchFailure(label, processResult) {
  const launchError = processResult.error;
  if (
    launchError &&
    typeof launchError === 'object' &&
    launchError.code === SPAWN_TIMEOUT_ERROR_CODE
  ) {
    return `${label}: grok timed out after ${GROK_SPAWN_TIMEOUT_MS}ms`;
  }
  if (launchError !== null) {
    return `${label}: failed to launch grok: ${launchError}`;
  }
  return `${label}: grok exit ${processResult.exitCode}\n${processResult.stderr}\n${processResult.stdout}`;
}

function launchEval(runDirectory, { evalName, promptText, maxTurns, agentName }) {
  const label = evalName.toUpperCase();
  const promptPath = writePromptFile(runDirectory, evalName, promptText);
  const processResult = runGrok({
    promptPath,
    workingDirectory: runDirectory,
    leaderSocketPath: mintLeaderSocketPath(runDirectory, evalName),
    maxTurns,
    agentName,
  });
  assertCondition(
    processResult.error === null && processResult.exitCode === 0,
    describeLaunchFailure(label, processResult),
  );
  const payload = parsePayload(processResult.stdout);
  assertCondition(
    payload !== null,
    `${label}: could not parse JSON payload from grok output`,
  );
  return payload;
}

function runEvalOne(runDirectory) {
  const payload = launchEval(runDirectory, {
    evalName: 'e1',
    promptText: E1_PROMPT,
    maxTurns: DEFAULT_MAX_TURNS,
  });
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
  const payload = launchEval(runDirectory, {
    evalName: 'e2',
    promptText: E2_PROMPT,
    maxTurns: SPAWN_MAX_TURNS,
  });
  assertCondition(
    payload.spawn_succeeded === true,
    `E2: expected spawn_succeeded === true, got ${JSON.stringify(payload.spawn_succeeded)}`,
  );
  const childExcerpt =
    typeof payload.child_excerpt === 'string' ? payload.child_excerpt : '';
  assertCondition(
    childExcerpt.includes(SPAWN_MARKER),
    `E2: expected child_excerpt to include ${SPAWN_MARKER}, got ${JSON.stringify(payload.child_excerpt)}`,
  );
  return payload;
}

function runEvalThree(runDirectory) {
  const payload = launchEval(runDirectory, {
    evalName: 'e3',
    promptText: E3_PROMPT,
    maxTurns: SKILL_MAX_TURNS,
    agentName: resolveDefaultAgentName(),
  });
  assertCondition(
    payload.skill_read_ok === true,
    `E3: expected skill_read_ok === true, got ${JSON.stringify(payload.skill_read_ok)}`,
  );
  return payload;
}

function runEvalFour(runDirectory) {
  const payload = launchEval(runDirectory, {
    evalName: 'e4',
    promptText: E4_PROMPT,
    maxTurns: WRITE_MAX_TURNS,
  });
  const probePath = join(runDirectory, PROBE_FILE_NAME);
  const isProbePresent = existsSync(probePath);
  assertCondition(
    isProbePresent,
    `E4: probe file missing under the eval cwd (write_succeeded claim: ${JSON.stringify(payload.write_succeeded)})`,
  );
  const probeContents = readFileSync(probePath, 'utf8');
  assertCondition(
    probeContents.includes(PROBE_FILE_CONTENTS),
    `E4: probe file contents mismatch: ${JSON.stringify(probeContents)}`,
  );
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

export function isWorkflowToolAbsent(payload) {
  if (!payload || typeof payload !== 'object') {
    return false;
  }
  return (
    payload.has_workflow_tool === false &&
    payload.result === WORKFLOW_RESULT_NO_TOOL
  );
}

function runEvalFive(runDirectory) {
  const payload = launchEval(runDirectory, {
    evalName: 'e5',
    promptText: E5_PROMPT,
    maxTurns: WORKFLOW_MAX_TURNS,
  });
  assertCondition(
    isWorkflowToolAbsent(payload),
    `E5: expected has_workflow_tool === false and result === "no_tool", got ${JSON.stringify(payload)}`,
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
