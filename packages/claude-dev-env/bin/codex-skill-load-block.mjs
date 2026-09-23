import { lstatSync, mkdirSync, readFileSync, readlinkSync, unlinkSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';

export const SKILL_LOAD_BLOCK_START = '<!-- claude-dev-env skill load: start -->';
export const SKILL_LOAD_BLOCK_END = '<!-- claude-dev-env skill load: end -->';
export const SKILL_LOAD_INSTRUCTION = 'Load the pstack:poteto-mode skill before your first tool call or reply: '
    + 'open its SKILL.md from your skills list and follow it. This binds every Codex agent, '
    + 'including a helper started with spawn_agent, whatever its task message says.';
export const PACKAGE_GUIDANCE_BLOCK_START = '<!-- claude-dev-env package guidance: start -->';
export const PACKAGE_GUIDANCE_BLOCK_END = '<!-- claude-dev-env package guidance: end -->';

const WINDOWS_LONG_PATH_PREFIX = '\\\\?\\';

function managedBlock(blockStart, blockBody, blockEnd) {
    const terminatedBody = blockBody.endsWith('\n') ? blockBody : `${blockBody}\n`;
    return `${blockStart}\n${terminatedBody}${blockEnd}\n`;
}

function withBlockReplaced(guidanceText, blockStart, blockEnd, block) {
    const startIndex = guidanceText.indexOf(blockStart);
    const endIndex = startIndex === -1 ? -1 : guidanceText.indexOf(blockEnd, startIndex);
    if (endIndex === -1) return null;
    let afterBlockIndex = endIndex + blockEnd.length;
    if (guidanceText[afterBlockIndex] === '\n') afterBlockIndex += 1;
    return guidanceText.slice(0, startIndex) + block + guidanceText.slice(afterBlockIndex);
}

/**
 * Return the Codex guidance text with the package's skill-load block in it.
 *
 * Codex starts a spawn_agent helper without running any hook, so the global
 * AGENTS.md is the one channel that reaches every helper. A block already in
 * the text is replaced where it stands; otherwise the block goes first.
 */
export function withSkillLoadBlock(guidanceText) {
    const block = managedBlock(SKILL_LOAD_BLOCK_START, SKILL_LOAD_INSTRUCTION, SKILL_LOAD_BLOCK_END);
    const replacedText = withBlockReplaced(guidanceText, SKILL_LOAD_BLOCK_START, SKILL_LOAD_BLOCK_END, block);
    if (replacedText !== null) return replacedText;
    return guidanceText ? `${block}\n${guidanceText}` : block;
}

function withPackageGuidanceBlock(guidanceText, packageGuidanceText) {
    const block = managedBlock(PACKAGE_GUIDANCE_BLOCK_START, packageGuidanceText, PACKAGE_GUIDANCE_BLOCK_END);
    const replacedText = withBlockReplaced(
        guidanceText,
        PACKAGE_GUIDANCE_BLOCK_START,
        PACKAGE_GUIDANCE_BLOCK_END,
        block,
    );
    return replacedText ?? `${guidanceText}\n${block}`;
}

function comparablePath(filePath) {
    const withoutPrefix = filePath.startsWith(WINDOWS_LONG_PATH_PREFIX)
        ? filePath.slice(WINDOWS_LONG_PATH_PREFIX.length)
        : filePath;
    const resolvedPath = resolve(withoutPrefix);
    return process.platform === 'win32' ? resolvedPath.toLowerCase() : resolvedPath;
}

function linksToPackageGuidance(agentsPath, allPackageGuidancePaths) {
    const linkTarget = comparablePath(resolve(dirname(agentsPath), readlinkSync(agentsPath)));
    return allPackageGuidancePaths.some(eachPath => comparablePath(eachPath) === linkTarget);
}

/**
 * Keep CODEX_HOME/AGENTS.md carrying the skill-load block.
 *
 * A symbolic link that points at the package guidance (the shared agents-home
 * copy, or the retired copy under the Claude home) is replaced by a regular
 * file holding the skill-load block and a package-guidance block, so Codex
 * keeps both after the package moves its guidance. A file that already holds
 * the package-guidance block gets the current guidance text. A link to any
 * other file is left alone.
 *
 * Returns the file path when the file changed, and null otherwise.
 */
export function writeCodexAgentsGuidance(codexHome, packageGuidanceText, allPackageGuidancePaths) {
    const agentsPath = join(codexHome, 'AGENTS.md');
    const agentsEntry = lstatSync(agentsPath, { throwIfNoEntry: false });
    const isPackageGuidanceLink = agentsEntry?.isSymbolicLink() ?? false;
    if (isPackageGuidanceLink && !linksToPackageGuidance(agentsPath, allPackageGuidancePaths)) return null;
    const currentText = agentsEntry && !isPackageGuidanceLink ? readFileSync(agentsPath, 'utf8') : '';
    let updatedText = withSkillLoadBlock(currentText);
    if (isPackageGuidanceLink || updatedText.includes(PACKAGE_GUIDANCE_BLOCK_START)) {
        updatedText = withPackageGuidanceBlock(updatedText, packageGuidanceText);
    }
    if (!isPackageGuidanceLink && updatedText === currentText) return null;
    mkdirSync(codexHome, { recursive: true });
    if (isPackageGuidanceLink) unlinkSync(agentsPath);
    writeFileSync(agentsPath, updatedText, 'utf8');
    return agentsPath;
}
