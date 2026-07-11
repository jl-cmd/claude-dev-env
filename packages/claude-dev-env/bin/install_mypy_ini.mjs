import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

const MYPY_INI_FILENAME = '.mypy.ini';
const MYPY_CONFIG_SECTION_HEADER = '[mypy]';


function normalizeClaudeHooksPathToForwardSlashes(claudeHooksDirectory) {
    return claudeHooksDirectory.replace(/\\/g, '/');
}


function buildExpectedMypyPathLine(claudeHooksDirectory) {
    const claudeHooksAsForwardSlashes = normalizeClaudeHooksPathToForwardSlashes(claudeHooksDirectory);
    return `mypy_path = ${claudeHooksAsForwardSlashes}`;
}


function buildMypyIniContentForClaudeHooks(claudeHooksDirectory) {
    const expectedMypyPathLine = buildExpectedMypyPathLine(claudeHooksDirectory);
    return `${MYPY_CONFIG_SECTION_HEADER}\n${expectedMypyPathLine}\n`;
}


function hasExactMatchingLine(fileContent, expectedLine) {
    const lineBreakPattern = /\r?\n/;
    const allLines = fileContent.split(lineBreakPattern);
    return allLines.some((eachLine) => eachLine.trim() === expectedLine);
}


export function installMypyIniForClaudeHooks({ homeDirectory, claudeHooksDirectory }) {
    const mypyIniDestinationPath = join(homeDirectory, MYPY_INI_FILENAME);
    const expectedMypyPathLine = buildExpectedMypyPathLine(claudeHooksDirectory);

    if (existsSync(mypyIniDestinationPath)) {
        const existingMypyIniContent = readFileSync(mypyIniDestinationPath, 'utf8');
        if (hasExactMatchingLine(existingMypyIniContent, expectedMypyPathLine)) {
            return { action: 'already-configured', path: mypyIniDestinationPath };
        }
        return {
            action: 'skipped-existing',
            path: mypyIniDestinationPath,
            expectedLine: expectedMypyPathLine,
        };
    }

    const mypyIniContent = buildMypyIniContentForClaudeHooks(claudeHooksDirectory);
    writeFileSync(mypyIniDestinationPath, mypyIniContent);
    return { action: 'created', path: mypyIniDestinationPath };
}
