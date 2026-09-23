import { lstatSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

export const SKILL_LOAD_BLOCK_START = '<!-- claude-dev-env skill load: start -->';
export const SKILL_LOAD_BLOCK_END = '<!-- claude-dev-env skill load: end -->';
export const SKILL_LOAD_INSTRUCTION = 'Load the pstack:poteto-mode skill before your first tool call or reply: '
    + 'open its SKILL.md from your skills list and follow it. This binds every Codex agent, '
    + 'including a helper started with spawn_agent, whatever its task message says.';

const SKILL_LOAD_BLOCK = `${SKILL_LOAD_BLOCK_START}\n${SKILL_LOAD_INSTRUCTION}\n${SKILL_LOAD_BLOCK_END}\n`;

/**
 * Return the Codex guidance text with the package's skill-load block in it.
 *
 * Codex starts a spawn_agent helper without running any hook, so the global
 * AGENTS.md is the one channel that reaches every helper. A block already in
 * the text is replaced where it stands; otherwise the block goes first.
 */
export function withSkillLoadBlock(guidanceText) {
    const startIndex = guidanceText.indexOf(SKILL_LOAD_BLOCK_START);
    const endIndex = startIndex === -1 ? -1 : guidanceText.indexOf(SKILL_LOAD_BLOCK_END, startIndex);
    if (endIndex === -1) {
        return guidanceText ? `${SKILL_LOAD_BLOCK}\n${guidanceText}` : SKILL_LOAD_BLOCK;
    }
    let afterBlockIndex = endIndex + SKILL_LOAD_BLOCK_END.length;
    if (guidanceText[afterBlockIndex] === '\n') afterBlockIndex += 1;
    return guidanceText.slice(0, startIndex) + SKILL_LOAD_BLOCK + guidanceText.slice(afterBlockIndex);
}

/**
 * Write the skill-load block into CODEX_HOME/AGENTS.md.
 *
 * Returns the file path when the file changed, and null when it already held
 * the current block.
 */
export function writeCodexSkillLoadBlock(codexHome) {
    const agentsPath = join(codexHome, 'AGENTS.md');
    const hasGuidance = lstatSync(agentsPath, { throwIfNoEntry: false }) !== undefined;
    const currentText = hasGuidance ? readFileSync(agentsPath, 'utf8') : '';
    const updatedText = withSkillLoadBlock(currentText);
    if (updatedText === currentText) return null;
    mkdirSync(codexHome, { recursive: true });
    writeFileSync(agentsPath, updatedText, 'utf8');
    return agentsPath;
}
