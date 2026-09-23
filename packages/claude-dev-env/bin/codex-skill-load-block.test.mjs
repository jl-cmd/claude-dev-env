import { test } from 'node:test';
import { strict as assert } from 'node:assert';
import { mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import {
    SKILL_LOAD_BLOCK_END,
    SKILL_LOAD_BLOCK_START,
    SKILL_LOAD_INSTRUCTION,
    withSkillLoadBlock,
    writeCodexSkillLoadBlock,
} from './codex-skill-load-block.mjs';

const EXPECTED_BLOCK = `${SKILL_LOAD_BLOCK_START}\n${SKILL_LOAD_INSTRUCTION}\n${SKILL_LOAD_BLOCK_END}\n`;

function makeCodexHome(context) {
    const root = mkdtempSync(join(tmpdir(), 'cde-skill-load-'));
    context.after(() => rmSync(root, { recursive: true, force: true }));
    return join(root, '.codex');
}

test('the instruction names the skill and binds spawned helpers', () => {
    assert.match(SKILL_LOAD_INSTRUCTION, /pstack:poteto-mode/);
    assert.match(SKILL_LOAD_INSTRUCTION, /spawn_agent/);
});

test('a missing Codex guidance file is created holding only the block', (context) => {
    const codexHome = makeCodexHome(context);

    const writtenPath = writeCodexSkillLoadBlock(codexHome);

    assert.equal(writtenPath, join(codexHome, 'AGENTS.md'));
    assert.equal(readFileSync(writtenPath, 'utf8'), EXPECTED_BLOCK);
});

test('existing guidance keeps every line and gains the block first', (context) => {
    const codexHome = makeCodexHome(context);
    mkdirSync(codexHome);
    writeFileSync(join(codexHome, 'AGENTS.md'), '# pstack model configuration\n\nbug-fix: gpt-6-astra\n');

    writeCodexSkillLoadBlock(codexHome);

    assert.equal(
        readFileSync(join(codexHome, 'AGENTS.md'), 'utf8'),
        `${EXPECTED_BLOCK}\n# pstack model configuration\n\nbug-fix: gpt-6-astra\n`,
    );
});

test('a repeat install leaves the file unchanged and reports no write', (context) => {
    const codexHome = makeCodexHome(context);
    mkdirSync(codexHome);
    writeFileSync(join(codexHome, 'AGENTS.md'), 'Custom agents\n');
    writeCodexSkillLoadBlock(codexHome);
    const afterFirstInstall = readFileSync(join(codexHome, 'AGENTS.md'), 'utf8');

    assert.equal(writeCodexSkillLoadBlock(codexHome), null);
    assert.equal(readFileSync(join(codexHome, 'AGENTS.md'), 'utf8'), afterFirstInstall);
});

test('an outdated block is replaced in place and the text around it is kept', () => {
    const outdated = `Intro\n${SKILL_LOAD_BLOCK_START}\nOld wording\n${SKILL_LOAD_BLOCK_END}\nOutro\n`;

    assert.equal(withSkillLoadBlock(outdated), `Intro\n${EXPECTED_BLOCK}Outro\n`);
});

test('a start marker with no end marker gets a fresh block and keeps the stray text', () => {
    const broken = `${SKILL_LOAD_BLOCK_START}\nHalf a block\n`;

    const repaired = withSkillLoadBlock(broken);

    assert.equal(repaired, `${EXPECTED_BLOCK}\n${broken}`);
});
