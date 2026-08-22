import { test } from 'node:test';
import { strict as assert } from 'node:assert';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const skillDirectory = dirname(fileURLToPath(import.meta.url));
const skillSource = readFileSync(join(skillDirectory, 'SKILL.md'), 'utf8');
const handoffSource = readFileSync(
  join(skillDirectory, 'templates', 'handoff-template.md'),
  'utf8',
);

test('SKILL.md does not claim Grok cannot spawn Claude subagents', () => {
  assert.equal(
    skillSource.includes('cannot spawn Claude subagents'),
    false,
    'SKILL.md must not contain the false substring "cannot spawn Claude subagents"',
  );
});

test('SKILL.md documents the out-of-process claude -p advisor path', () => {
  assert.match(skillSource, /claude -p/);
});

test('handoff template keeps the claude -p advisor bind path', () => {
  assert.match(handoffSource, /claude -p/);
});
