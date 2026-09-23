import { test } from 'node:test';
import { strict as assert } from 'node:assert';
import { lstatSync, mkdtempSync, mkdirSync, readFileSync, rmSync, symlinkSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import {
    PACKAGE_GUIDANCE_BLOCK_END,
    PACKAGE_GUIDANCE_BLOCK_START,
    SKILL_LOAD_BLOCK_END,
    SKILL_LOAD_BLOCK_START,
    SKILL_LOAD_INSTRUCTION,
    withSkillLoadBlock,
    writeCodexAgentsGuidance,
} from './codex-skill-load-block.mjs';

const EXPECTED_BLOCK = `${SKILL_LOAD_BLOCK_START}\n${SKILL_LOAD_INSTRUCTION}\n${SKILL_LOAD_BLOCK_END}\n`;
const PACKAGE_GUIDANCE = 'Status\n\nChanged / proof / blocked.\n';

function guidanceBlock(guidanceText) {
    return `${PACKAGE_GUIDANCE_BLOCK_START}\n${guidanceText}${PACKAGE_GUIDANCE_BLOCK_END}\n`;
}

function makeHomes(context) {
    const root = mkdtempSync(join(tmpdir(), 'cde-skill-load-'));
    context.after(() => rmSync(root, { recursive: true, force: true }));
    const codexHome = join(root, '.codex');
    const retiredGuidancePath = join(root, '.claude', 'AGENTS.md');
    const sharedGuidancePath = join(root, '.agents', 'AGENTS.md');
    return {
        root,
        codexHome,
        agentsPath: join(codexHome, 'AGENTS.md'),
        retiredGuidancePath,
        sharedGuidancePath,
        allPackageGuidancePaths: [retiredGuidancePath, sharedGuidancePath],
    };
}

function writeGuidance(homes) {
    return writeCodexAgentsGuidance(homes.codexHome, PACKAGE_GUIDANCE, homes.allPackageGuidancePaths);
}

test('the instruction names the skill and binds spawned helpers', () => {
    assert.match(SKILL_LOAD_INSTRUCTION, /pstack:poteto-mode/);
    assert.match(SKILL_LOAD_INSTRUCTION, /spawn_agent/);
});

test('a missing Codex guidance file is created holding only the skill-load block', (context) => {
    const homes = makeHomes(context);

    const writtenPath = writeGuidance(homes);

    assert.equal(writtenPath, homes.agentsPath);
    assert.equal(readFileSync(homes.agentsPath, 'utf8'), EXPECTED_BLOCK);
});

test('existing guidance keeps every line and gains the skill-load block first', (context) => {
    const homes = makeHomes(context);
    mkdirSync(homes.codexHome);
    writeFileSync(homes.agentsPath, '# pstack model configuration\n\nbug-fix: gpt-6-astra\n');

    writeGuidance(homes);

    assert.equal(
        readFileSync(homes.agentsPath, 'utf8'),
        `${EXPECTED_BLOCK}\n# pstack model configuration\n\nbug-fix: gpt-6-astra\n`,
    );
});

test('a repeat install leaves the file unchanged and reports no write', (context) => {
    const homes = makeHomes(context);
    mkdirSync(homes.codexHome);
    writeFileSync(homes.agentsPath, 'Custom agents\n');
    writeGuidance(homes);
    const afterFirstInstall = readFileSync(homes.agentsPath, 'utf8');

    assert.equal(writeGuidance(homes), null);
    assert.equal(readFileSync(homes.agentsPath, 'utf8'), afterFirstInstall);
});

test('an outdated block is replaced in place and the text around it is kept', () => {
    const outdated = `Intro\n${SKILL_LOAD_BLOCK_START}\nOld wording\n${SKILL_LOAD_BLOCK_END}\nOutro\n`;

    assert.equal(withSkillLoadBlock(outdated), `Intro\n${EXPECTED_BLOCK}Outro\n`);
});

test('a start marker with no end marker gets a fresh block and keeps the stray text', () => {
    const broken = `${SKILL_LOAD_BLOCK_START}\nHalf a block\n`;

    assert.equal(withSkillLoadBlock(broken), `${EXPECTED_BLOCK}\n${broken}`);
});

for (const linkName of ['retiredGuidancePath', 'sharedGuidancePath']) {
    test(`a link to package guidance at ${linkName} becomes a file with both blocks`, (context) => {
        const homes = makeHomes(context);
        mkdirSync(homes.codexHome);
        symlinkSync(homes[linkName], homes.agentsPath);

        const writtenPath = writeGuidance(homes);

        assert.equal(writtenPath, homes.agentsPath);
        assert.equal(lstatSync(homes.agentsPath).isSymbolicLink(), false);
        assert.equal(
            readFileSync(homes.agentsPath, 'utf8'),
            `${EXPECTED_BLOCK}\n${guidanceBlock(PACKAGE_GUIDANCE)}`,
        );
    });
}

test('a converted file takes the new package guidance on the next install', (context) => {
    const homes = makeHomes(context);
    mkdirSync(homes.codexHome);
    writeFileSync(homes.agentsPath, `${EXPECTED_BLOCK}\n${guidanceBlock('Old guidance\n')}`);

    writeGuidance(homes);

    assert.equal(
        readFileSync(homes.agentsPath, 'utf8'),
        `${EXPECTED_BLOCK}\n${guidanceBlock(PACKAGE_GUIDANCE)}`,
    );
});

test('a link to a file the package does not own is left alone', (context) => {
    const homes = makeHomes(context);
    mkdirSync(homes.codexHome);
    const ownGuidancePath = join(homes.root, 'notes', 'codex.md');
    mkdirSync(join(homes.root, 'notes'));
    writeFileSync(ownGuidancePath, 'My own Codex notes\n');
    symlinkSync(ownGuidancePath, homes.agentsPath);

    assert.equal(writeGuidance(homes), null);
    assert.equal(lstatSync(homes.agentsPath).isSymbolicLink(), true);
    assert.equal(readFileSync(ownGuidancePath, 'utf8'), 'My own Codex notes\n');
});
