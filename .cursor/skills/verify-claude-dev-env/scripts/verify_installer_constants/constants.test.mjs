import test from 'node:test';
import assert from 'node:assert/strict';

import {
    DRIVER_FILE_NAME,
    SCRIPTS_DIRECTORY_NAME,
    SKILL_HOME_DIRECTORY_NAME,
    SKILLS_DIRECTORY_NAME,
    VERIFY_SKILL_NAME,
} from './constants.mjs';

test('the driver path segments should compose the location the skill owns', () => {
    const composedPath = [
        SKILL_HOME_DIRECTORY_NAME,
        SKILLS_DIRECTORY_NAME,
        VERIFY_SKILL_NAME,
        SCRIPTS_DIRECTORY_NAME,
        DRIVER_FILE_NAME,
    ].join('/');

    assert.equal(composedPath, '.cursor/skills/verify-claude-dev-env/scripts/driver.mjs');
});
