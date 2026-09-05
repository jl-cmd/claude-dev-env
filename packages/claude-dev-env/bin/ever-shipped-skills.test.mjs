import { strict as assert } from 'node:assert';
import { test } from 'node:test';
import { existsSync, readdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { EVER_SHIPPED_SKILL_NAMES } from './ever-shipped-skills.mjs';
import {
    MANAGED_SKILLS_DIRECTORY_NAME,
    PACKAGE_AGENTS_HOME_DIRECTORY_NAME,
} from './install-constants.mjs';

const THIS_DIRECTORY = dirname(fileURLToPath(import.meta.url));
const PACKAGE_DIRECTORY = dirname(THIS_DIRECTORY);

test('EVER_SHIPPED_SKILL_NAMES includes every current shipped skill', () => {
    const sourceSkillsDirectory = join(
        PACKAGE_DIRECTORY,
        PACKAGE_AGENTS_HOME_DIRECTORY_NAME,
        MANAGED_SKILLS_DIRECTORY_NAME,
    );
    const allCurrentSkillNames = readdirSync(sourceSkillsDirectory, { withFileTypes: true })
        .filter(eachEntry => eachEntry.isDirectory())
        .filter(eachEntry => existsSync(join(sourceSkillsDirectory, eachEntry.name, 'SKILL.md')))
        .map(eachEntry => eachEntry.name);
    const allUncoveredSkillNames = allCurrentSkillNames.filter(
        eachSkillName => !EVER_SHIPPED_SKILL_NAMES.has(eachSkillName),
    );

    assert.deepEqual(allUncoveredSkillNames, [], 'every current skill must enter the fallback set');
});

test('EVER_SHIPPED_SKILL_NAMES retains the explicit test runner', () => {
    assert.ok(EVER_SHIPPED_SKILL_NAMES.has('test-runner'));
});
