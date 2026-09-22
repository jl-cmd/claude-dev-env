import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

const CI_DIRECTORY = dirname(fileURLToPath(import.meta.url));
const SHIM_PATH = join(CI_DIRECTORY, '..', 'windows', 'pstack', 'pstack-command-shim.ps1');
const shimSource = readFileSync(SHIM_PATH, 'utf8');

test('the shim hands every argument after the command to the entrypoint', () => {
    assert.match(shimSource, /\$commandArguments = @\(\$args \| Select-Object -Skip 1\)/);
    assert.match(shimSource, /& bun \$entrypoint @commandArguments/);
});

test('the shim validates the command without a parameter binder', () => {
    assert.match(shimSource, /-notcontains \$command/);
    assert.doesNotMatch(shimSource, /ValidateSet/);
    assert.doesNotMatch(shimSource, /ValueFromRemainingArguments/);
});

test('the shim bootstraps dependencies before it launches the entrypoint', () => {
    const bootstrapIndex = shimSource.indexOf('ensureDependenciesInstalled');
    const launchIndex = shimSource.indexOf('& bun $entrypoint');
    assert.ok(bootstrapIndex > -1, 'the bootstrap call is absent');
    assert.ok(launchIndex > -1, 'the entrypoint launch is absent');
    assert.ok(bootstrapIndex < launchIndex, 'the bootstrap call runs after the launch');
});

test('the shim exits with the code the entrypoint returned', () => {
    assert.match(shimSource, /\$exitCode = \$LASTEXITCODE/);
    assert.match(shimSource, /exit \$exitCode/);
});
