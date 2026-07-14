import { test } from 'node:test';
import { strict as assert } from 'node:assert';
import {
  tryParseJsonObject,
  extractResultText,
  parsePayload,
  isWorkflowToolAbsent,
} from './run-capability-evals.mjs';

const E1_CLAIM_PAYLOAD = {
  can_spawn_subagent_tool: true,
  tool_names: ['spawn_subagent'],
  agents_dir_exists: true,
  skills_dir_exists: true,
};

test('tryParseJsonObject parses a pure JSON object string', () => {
  const parsed = tryParseJsonObject(JSON.stringify(E1_CLAIM_PAYLOAD));
  assert.deepEqual(parsed, E1_CLAIM_PAYLOAD);
});

test('tryParseJsonObject strips leading prose before the first brace', () => {
  const withProse = `Here is the inventory:\n${JSON.stringify(E1_CLAIM_PAYLOAD)}`;
  const parsed = tryParseJsonObject(withProse);
  assert.deepEqual(parsed, E1_CLAIM_PAYLOAD);
});

test('tryParseJsonObject extracts the object when trailing prose carries braces', () => {
  const withTrailingBraces = `${JSON.stringify(E1_CLAIM_PAYLOAD)}\nNote: see {run-directory} for logs.`;
  const parsed = tryParseJsonObject(withTrailingBraces);
  assert.deepEqual(parsed, E1_CLAIM_PAYLOAD);
});

test('tryParseJsonObject ignores a stray brace pair in leading prose', () => {
  const withLeadingBraces = `Here is the result (see {} for details):\n${JSON.stringify(E1_CLAIM_PAYLOAD)}`;
  const parsed = tryParseJsonObject(withLeadingBraces);
  assert.deepEqual(parsed, E1_CLAIM_PAYLOAD);
});

test('tryParseJsonObject returns null for empty input', () => {
  assert.equal(tryParseJsonObject(''), null);
  assert.equal(tryParseJsonObject('   '), null);
});

test('extractResultText reads Grok top-level text field', () => {
  const nestedJson = JSON.stringify(E1_CLAIM_PAYLOAD);
  const envelope = JSON.stringify({ text: nestedJson, model: 'grok' });
  assert.equal(extractResultText(envelope), nestedJson);
});

test('extractResultText prefers Claude result over Grok text', () => {
  const envelope = JSON.stringify({
    result: '{"from":"result"}',
    text: '{"from":"text"}',
  });
  assert.equal(extractResultText(envelope), '{"from":"result"}');
});

test('extractResultText prefers Grok text over a conversational message', () => {
  const envelope = JSON.stringify({
    message: 'working',
    text: '{"from":"text"}',
  });
  assert.equal(extractResultText(envelope), '{"from":"text"}');
});

test('extractResultText reads Claude message field', () => {
  const envelope = JSON.stringify({ message: '{"from":"message"}' });
  assert.equal(extractResultText(envelope), '{"from":"message"}');
});

test('extractResultText reads Claude stream result events', () => {
  const envelope = JSON.stringify([
    { type: 'assistant', content: 'thinking' },
    {
      type: 'result',
      result: JSON.stringify(E1_CLAIM_PAYLOAD),
    },
  ]);
  assert.equal(extractResultText(envelope), JSON.stringify(E1_CLAIM_PAYLOAD));
});

test('extractResultText prefers the last result event in a stream array', () => {
  const intermediateClaim = { can_spawn_subagent_tool: false, tool_names: [] };
  const envelope = JSON.stringify([
    { type: 'assistant', content: 'thinking' },
    { type: 'result', result: JSON.stringify(intermediateClaim) },
    { type: 'assistant', content: 'retry' },
    { type: 'result', result: JSON.stringify(E1_CLAIM_PAYLOAD) },
  ]);
  assert.equal(extractResultText(envelope), JSON.stringify(E1_CLAIM_PAYLOAD));
});

test('parsePayload extracts nested claim JSON from Grok text envelope', () => {
  const envelope = JSON.stringify({
    text: JSON.stringify(E1_CLAIM_PAYLOAD),
  });
  const payload = parsePayload(envelope);
  assert.equal(payload.can_spawn_subagent_tool, true);
  assert.deepEqual(payload.tool_names, ['spawn_subagent']);
});

test('parsePayload extracts nested claim JSON when Grok text has leading prose', () => {
  const envelope = JSON.stringify({
    text: `Capability inventory complete.\n${JSON.stringify(E1_CLAIM_PAYLOAD)}`,
  });
  const payload = parsePayload(envelope);
  assert.equal(payload.can_spawn_subagent_tool, true);
  assert.equal(payload.agents_dir_exists, true);
});

test('parsePayload still reads Claude result envelopes', () => {
  const envelope = JSON.stringify({
    result: JSON.stringify(E1_CLAIM_PAYLOAD),
  });
  const payload = parsePayload(envelope);
  assert.equal(payload.can_spawn_subagent_tool, true);
});

test('parsePayload still reads Claude message envelopes', () => {
  const envelope = JSON.stringify({
    message: JSON.stringify(E1_CLAIM_PAYLOAD),
  });
  const payload = parsePayload(envelope);
  assert.equal(payload.can_spawn_subagent_tool, true);
});

test('parsePayload still reads Claude stream array envelopes', () => {
  const envelope = JSON.stringify([
    { type: 'message', content: 'working' },
    { type: 'result', result: JSON.stringify(E1_CLAIM_PAYLOAD) },
  ]);
  const payload = parsePayload(envelope);
  assert.equal(payload.can_spawn_subagent_tool, true);
  assert.deepEqual(payload.tool_names, ['spawn_subagent']);
});

test('isWorkflowToolAbsent accepts consistent absence', () => {
  assert.equal(
    isWorkflowToolAbsent({ has_workflow_tool: false, result: 'no_tool' }),
    true,
  );
});

test('isWorkflowToolAbsent rejects contradictory true and no_tool', () => {
  assert.equal(
    isWorkflowToolAbsent({ has_workflow_tool: true, result: 'no_tool' }),
    false,
  );
});

test('isWorkflowToolAbsent rejects contradictory false and has_tool', () => {
  assert.equal(
    isWorkflowToolAbsent({ has_workflow_tool: false, result: 'has_tool' }),
    false,
  );
});

test('isWorkflowToolAbsent rejects consistent presence', () => {
  assert.equal(
    isWorkflowToolAbsent({ has_workflow_tool: true, result: 'has_tool' }),
    false,
  );
});

test('isWorkflowToolAbsent rejects partial or missing fields', () => {
  assert.equal(isWorkflowToolAbsent({ has_workflow_tool: false }), false);
  assert.equal(isWorkflowToolAbsent({ result: 'no_tool' }), false);
  assert.equal(isWorkflowToolAbsent(null), false);
  assert.equal(isWorkflowToolAbsent({}), false);
});
