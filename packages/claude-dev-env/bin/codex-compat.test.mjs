import test from "node:test";
import assert from "node:assert/strict";
import { buildCommand, createHelpText, main } from "./codex-compat.mjs";

test("help describes both compatibility commands", () => {
    assert.match(createHelpText(), /materialize/);
    assert.match(createHelpText(), /bridge/);
});

test("missing required arguments returns a usage error", async () => {
    const messages = [];
    const originalWrite = process.stderr.write;
    process.stderr.write = (message) => messages.push(message);
    try { assert.equal(await main(["materialize"], { findPython: async () => "python" }), 2); } finally { process.stderr.write = originalWrite; }
    assert.equal(JSON.parse(messages.join("")).error.code, "invalid_command");
    assert.match(messages.join(""), /--source-root/);
});

test("unknown command returns structured error without running a child", async () => {
    const messages = [];
    let wasRun = false;
    const originalWrite = process.stderr.write;
    process.stderr.write = (message) => messages.push(message);
    try {
        const exitCode = await main(["unknown"], {
            findPython: async () => "python",
            runCommand: async () => { wasRun = true; return 0; },
        });
        assert.equal(exitCode, 2);
    } finally { process.stderr.write = originalWrite; }
    assert.equal(JSON.parse(messages.join("")).error.code, "invalid_command");
    assert.equal(wasRun, false);
});

test("commands use safe argv and forward dry-run and apply", () => {
    const dryRun = buildCommand("materialize", ["--source-root", "source root", "--target-root", "target;root"], "python");
    const apply = buildCommand("materialize", ["--source-root", "source", "--target-root", "target", "--apply"], "python");
    assert.equal(dryRun.arguments.at(-1), "target;root");
    assert.equal(apply.arguments.at(-1), "--apply");
});

test("bridge forwarding and child status use injected runners", async () => {
    let receivedCommand;
    const exitCode = await main(["bridge", "--surface", "TaskCreate", "--payload", '{"name":"ship","status":"pending"}'], {
        findPython: async () => "python-test",
        runCommand: async (command) => { receivedCommand = command; return 7; },
    });
    assert.equal(exitCode, 7);
    assert.equal(receivedCommand.executable, "python-test");
    assert.equal(receivedCommand.arguments.at(-1), '{"name":"ship","status":"pending"}');
});
