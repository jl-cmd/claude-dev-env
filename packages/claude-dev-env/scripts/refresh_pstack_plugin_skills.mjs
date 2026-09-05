/**
 * Keep a pstack skills-directory plugin manifest listing every skill folder.
 *
 * Claude Code loads a folder under `~/.claude/skills` as a plugin when the
 * folder holds `.claude-plugin/plugin.json`, and it namespaces that plugin's
 * skills as `pstack:how`. It does not scan a plugin root for skill folders, so
 * the manifest names each sub-skill path:
 *
 *     plugin root holds: how/SKILL.md, why/SKILL.md, docs/, .claude-plugin/
 *     manifest before:   "skills": ["./how"]
 *     manifest after:    "skills": ["./how", "./why"]   <- why/ picked up
 *     second run:        no write                        <- the list matches
 *     docs/, .claude-plugin/                             <- skipped, no SKILL.md
 *
 * The installer calls `refreshPstackPluginManifest` for a pstack folder the
 * user installed. Running this file directly refreshes the same manifest after
 * a pstack update.
 */

import {
    existsSync,
    mkdirSync,
    readdirSync,
    readFileSync,
    realpathSync,
    writeFileSync,
} from 'node:fs';
import { homedir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

export const PSTACK_PLUGIN_DIRECTORY_NAME = 'pstack';
export const PSTACK_PLUGIN_MANIFEST_RELATIVE_PATH = join('.claude-plugin', 'plugin.json');
export const SKILL_MANIFEST_FILE_NAME = 'SKILL.md';
export const SKILL_PATH_PREFIX = './';

const CLAUDE_HOME_DIRECTORY_NAME = '.claude';
const MANIFEST_SKILLS_KEY = 'skills';
const MANIFEST_INDENT_SPACES = 2;
const FILE_ENCODING = 'utf8';
const HIDDEN_NAME_PREFIX = '.';

/**
 * The manifest fields a first write seeds, taken from the published pstack
 * plugin. A manifest the user already has keeps its own values: the refresher
 * owns the skills list alone.
 */
const SEEDED_MANIFEST_FIELDS = Object.freeze({
    $schema: 'https://anthropic.com/claude-code/plugin.schema.json',
    name: PSTACK_PLUGIN_DIRECTORY_NAME,
    version: '0.14.8',
    description:
        'if you want to go fast, go deep first. pstack helps you write less, but higher '
        + 'quality code. rigorous agent workflows you can parallelize with confidence.',
    author: Object.freeze({ name: 'Lauren Tan' }),
    homepage: 'https://github.com/cursor/plugins/tree/main/pstack',
    repository: 'https://github.com/cursor/plugins',
    license: 'MIT',
});

/**
 * Name every sub-folder of a plugin root that Claude Code loads as a skill.
 *
 * @param {string} pluginRoot Plugin folder holding one sub-folder per skill.
 * @returns {string[]} The sorted names of each visible sub-folder holding a
 *   skill manifest. A hidden folder and a folder without `SKILL.md` are left out.
 */
export function findPstackSkillDirectoryNames(pluginRoot) {
    return readdirSync(pluginRoot, { withFileTypes: true })
        .filter((eachEntry) => eachEntry.isDirectory())
        .map((eachEntry) => eachEntry.name)
        .filter((eachName) => !eachName.startsWith(HIDDEN_NAME_PREFIX))
        .filter((eachName) => existsSync(join(pluginRoot, eachName, SKILL_MANIFEST_FILE_NAME)))
        .sort();
}

function readManifestSkillPaths(manifestPath) {
    if (!existsSync(manifestPath)) return { manifest: null, previousSkillPaths: [] };
    const manifest = JSON.parse(readFileSync(manifestPath, FILE_ENCODING));
    const listedSkillPaths = manifest[MANIFEST_SKILLS_KEY];
    if (typeof listedSkillPaths === 'string') {
        return { manifest, previousSkillPaths: [listedSkillPaths] };
    }
    if (Array.isArray(listedSkillPaths)) {
        return { manifest, previousSkillPaths: listedSkillPaths };
    }
    return { manifest, previousSkillPaths: [] };
}

/**
 * Rewrite a pstack plugin manifest's skills list to match its folder.
 *
 * The manifest is written only when the list changes, so a second call on an
 * unchanged folder leaves the file byte for byte as it was. A manifest that is
 * already present keeps every field but the skills list.
 *
 * @param {string} pluginRoot Plugin folder holding the skill sub-folders.
 * @returns {{didWrite: boolean, reason: string, previousSkillPaths: string[],
 *   currentSkillPaths: string[]}} What the call found and whether it wrote.
 *   `reason` names why a call declined to write, and is empty otherwise.
 */
export function refreshPstackPluginManifest(pluginRoot) {
    const declined = { didWrite: false, previousSkillPaths: [], currentSkillPaths: [] };
    if (!existsSync(pluginRoot)) {
        return { ...declined, reason: 'plugin root is absent' };
    }
    if (existsSync(join(pluginRoot, SKILL_MANIFEST_FILE_NAME))) {
        return { ...declined, reason: 'plugin root is itself a skill' };
    }
    const allSkillNames = findPstackSkillDirectoryNames(pluginRoot);
    if (allSkillNames.length === 0) {
        return { ...declined, reason: 'plugin root holds no skills' };
    }
    const manifestPath = join(pluginRoot, PSTACK_PLUGIN_MANIFEST_RELATIVE_PATH);
    const { manifest, previousSkillPaths } = readManifestSkillPaths(manifestPath);
    const currentSkillPaths = allSkillNames.map((eachName) => SKILL_PATH_PREFIX + eachName);
    const outcome = { reason: '', previousSkillPaths, currentSkillPaths };
    const isUnchanged = manifest !== null
        && previousSkillPaths.length === currentSkillPaths.length
        && previousSkillPaths.every((eachPath, eachIndex) => eachPath === currentSkillPaths[eachIndex]);
    if (isUnchanged) {
        return { ...outcome, didWrite: false };
    }
    const refreshedManifest = {
        ...(manifest === null ? SEEDED_MANIFEST_FIELDS : manifest),
        [MANIFEST_SKILLS_KEY]: currentSkillPaths,
    };
    mkdirSync(join(pluginRoot, '.claude-plugin'), { recursive: true });
    writeFileSync(
        manifestPath,
        JSON.stringify(refreshedManifest, null, MANIFEST_INDENT_SPACES) + '\n',
        FILE_ENCODING,
    );
    return { ...outcome, didWrite: true };
}

/**
 * Resolve the pstack plugin folder a Claude home publishes.
 *
 * @param {string} claudeHome The Claude home directory holding `skills`.
 * @returns {string} The pstack plugin folder path, present or not.
 */
export function pstackPluginRootFor(claudeHome) {
    return join(claudeHome, 'skills', PSTACK_PLUGIN_DIRECTORY_NAME);
}

/**
 * Resolve the Claude home this run reads when no folder argument is given.
 *
 * A named profile sets `CLAUDE_CONFIG_DIR`, and the installer writes into that
 * root, so the command-line form reads the same variable.
 *
 * @param {Record<string, string|undefined>} environment The process environment.
 * @returns {string} The Claude home directory holding `skills`.
 */
export function claudeHomeFrom(environment) {
    return environment.CLAUDE_CONFIG_DIR || join(homedir(), CLAUDE_HOME_DIRECTORY_NAME);
}

function main() {
    const explicitRoot = process.argv[2];
    const pluginRoot = explicitRoot || pstackPluginRootFor(claudeHomeFrom(process.env));
    const outcome = refreshPstackPluginManifest(pluginRoot);
    if (!outcome.didWrite && outcome.reason) {
        console.log(`No manifest written: ${outcome.reason}.`);
        return;
    }
    if (!outcome.didWrite) {
        console.log(`No change. ${outcome.currentSkillPaths.length} skills listed.`);
        return;
    }
    console.log(`Updated. ${outcome.currentSkillPaths.length} skills listed.`);
    for (const eachPath of outcome.currentSkillPaths) {
        if (!outcome.previousSkillPaths.includes(eachPath)) console.log(`  added   ${eachPath}`);
    }
    for (const eachPath of outcome.previousSkillPaths) {
        if (!outcome.currentSkillPaths.includes(eachPath)) console.log(`  removed ${eachPath}`);
    }
}

/**
 * Report whether this module is the file node was asked to run.
 *
 * A home that reaches the script through a directory link gives node an
 * invoked path that differs from this module's own path, so both sides resolve
 * to their real location before the comparison.
 *
 * @param {string|undefined} invokedPath The path node reports as `argv[1]`.
 * @returns {boolean} True when node ran this module as its entry point.
 */
function isEntryPoint(invokedPath) {
    if (!invokedPath) return false;
    try {
        return realpathSync(fileURLToPath(import.meta.url)) === realpathSync(invokedPath);
    } catch {
        return fileURLToPath(import.meta.url) === invokedPath;
    }
}

if (isEntryPoint(process.argv[1])) main();
