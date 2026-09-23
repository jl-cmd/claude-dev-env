import { copyFileSync, lstatSync, mkdirSync, readFileSync, unlinkSync, writeFileSync, constants as filesystemConstants } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const CODEX_PRESET_PATH = fileURLToPath(new URL('../pstack-codex-models.md', import.meta.url));

function pathExists(path) {
    return lstatSync(path, { throwIfNoEntry: false }) !== undefined;
}

export function seedCodexPstackModels(codexHome, writeAgentGuidance = writeFileSync) {
    const sheetPath = join(codexHome, 'pstack-models.md');
    const agentsPath = join(codexHome, 'AGENTS.md');
    if (pathExists(sheetPath) || pathExists(agentsPath)) return null;

    const preset = readFileSync(CODEX_PRESET_PATH, 'utf8');
    const agentGuidance = preset.replace(/^session hook: on\n?$/m, '');
    mkdirSync(codexHome, { recursive: true });
    copyFileSync(CODEX_PRESET_PATH, sheetPath, filesystemConstants.COPYFILE_EXCL);
    try {
        writeAgentGuidance(agentsPath, agentGuidance, { encoding: 'utf8', flag: 'wx' });
    } catch (writeError) {
        unlinkSync(sheetPath);
        throw writeError;
    }
    return [sheetPath, agentsPath];
}
