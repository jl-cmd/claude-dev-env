import { EventEmitter } from "node:events";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import assert from "node:assert/strict";
import path from "node:path";
import test from "node:test";

import {
    buildLintCommand,
    createHelpText,
    findPython,
    main,
    pythonInterpreterNames,
    runLintCommand,
} from "./cde.mjs";

const packageRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const lintScriptPath = path.join(packageRoot, "scripts", "cde_lint.py");
const packageManifest = JSON.parse(
    readFileSync(new URL("../package.json", import.meta.url), "utf8"),
);


function createFakeChild() {
    const childProcess = new EventEmitter();
    childProcess.kill = (signalName) => {
        childProcess.lastSignalName = signalName;
    };
    return childProcess;
}


test("package exposes cde through its bin map", () => {
    assert.equal(packageManifest.bin.cde, "bin/cde.mjs");
});


test("help describes lint source modes", () => {
    const helpText = createHelpText();
    assert.match(helpText, /cde lint/);
    assert.match(helpText, /--files/);
    assert.match(helpText, /--staged/);
    assert.match(helpText, /--base/);
    assert.match(helpText, /--repository/);
    assert.match(helpText, /--text-as/);
});


test("prefers py then python on Windows and python3 then python on POSIX", () => {
    assert.deepEqual(pythonInterpreterNames("win32"), ["py", "python"]);
    assert.deepEqual(pythonInterpreterNames("linux"), ["python3", "python"]);
    assert.deepEqual(pythonInterpreterNames("darwin"), ["python3", "python"]);
});


test("falls back to the next interpreter when the first cannot run", () => {
    const selectedName = findPython(["py", "python"], (commandName) => commandName === "python");
    assert.equal(selectedName, "python");
});


test("forwards lint arguments to the python command without a shell", () => {
    const command = buildLintCommand("python-test", ["--files", "a.py", "--format", "json"]);
    assert.equal(command.executable, "python-test");
    assert.equal(command.arguments[0], lintScriptPath);
    assert.deepEqual(command.arguments.slice(1), ["--files", "a.py", "--format", "json"]);
});


test("strips the launcher python override from forwarded arguments", async () => {
    let receivedCommand;
    const exitCode = await main(["lint", "--python", "python-test", "--staged"], {
        findPython: async () => "unused-python",
        runCommand: async (command) => {
            receivedCommand = command;
            return 0;
        },
    });
    assert.equal(exitCode, 0);
    assert.equal(receivedCommand.executable, "python-test");
    assert.deepEqual(receivedCommand.arguments, [lintScriptPath, "--staged"]);
});


test("unknown command returns invalid input without spawning", async () => {
    let wasRun = false;
    const messages = [];
    const originalWrite = process.stderr.write;
    process.stderr.write = (message) => messages.push(message);
    try {
        const exitCode = await main(["not-lint"], {
            findPython: async () => "python",
            runCommand: async () => {
                wasRun = true;
                return 0;
            },
        });
        assert.equal(exitCode, 2);
    } finally {
        process.stderr.write = originalWrite;
    }
    assert.equal(wasRun, false);
    assert.match(messages.join(""), /lint/);
});


test("missing python override value returns invalid input without spawning", async () => {
    let wasRun = false;
    const exitCode = await main(["lint", "--python"], {
        findPython: async () => "python",
        runCommand: async () => {
            wasRun = true;
            return 0;
        },
    });
    assert.equal(exitCode, 2);
    assert.equal(wasRun, false);
});


test("missing interpreter returns invalid input without spawning", async () => {
    let wasRun = false;
    const originalWrite = process.stderr.write;
    process.stderr.write = () => true;
    try {
        const exitCode = await main(["lint", "--staged"], {
            findPython: async () => undefined,
            runCommand: async () => {
                wasRun = true;
                return 0;
            },
        });
        assert.equal(exitCode, 2);
    } finally {
        process.stderr.write = originalWrite;
    }
    assert.equal(wasRun, false);
});


test("forwards child exit status", async () => {
    const childProcess = createFakeChild();
    const exitPromise = runLintCommand(
        { executable: "python", arguments: [lintScriptPath] },
        {
            runChild: () => childProcess,
        },
    );
    childProcess.emit("close", 3, null);
    assert.equal(await exitPromise, 3);
});


test("forwards SIGINT to the child and never enables a shell", async () => {
    const childProcess = createFakeChild();
    const processEmitter = new EventEmitter();
    let spawnOptions;
    const exitPromise = runLintCommand(
        { executable: "python", arguments: [lintScriptPath, "--staged"] },
        {
            processEmitter,
            runChild: (_executable, _allArguments, options) => {
                spawnOptions = options;
                return childProcess;
            },
        },
    );
    processEmitter.emit("SIGINT");
    childProcess.emit("close", 0, null);
    assert.equal(await exitPromise, 0);
    assert.equal(childProcess.lastSignalName, "SIGINT");
    assert.equal(spawnOptions.shell, false);
});


test("tolerates forwarding a signal to a dead child", async () => {
    const childProcess = createFakeChild();
    childProcess.kill = () => {
        throw new Error("child already exited");
    };
    const processEmitter = new EventEmitter();
    const exitPromise = runLintCommand(
        { executable: "python", arguments: [lintScriptPath] },
        { processEmitter, runChild: () => childProcess },
    );
    processEmitter.emit("SIGTERM");
    childProcess.emit("close", 0, null);
    assert.equal(await exitPromise, 0);
});


test("reports a child start failure as invalid input", async () => {
    const childProcess = createFakeChild();
    const processEmitter = new EventEmitter();
    const messages = [];
    processEmitter.stderr = { write: (message) => messages.push(message) };
    const exitPromise = runLintCommand(
        { executable: "missing-python", arguments: [lintScriptPath] },
        { processEmitter, runChild: () => childProcess },
    );
    childProcess.emit("error", new Error("not found"));
    assert.equal(await exitPromise, 2);
    assert.deepEqual(messages, ["Unable to start the policy linter.\n"]);
});


test("reports a synchronous child start failure as invalid input", async () => {
    const processEmitter = new EventEmitter();
    const messages = [];
    processEmitter.stderr = { write: (message) => messages.push(message) };
    const exitCode = await runLintCommand(
        { executable: "missing-python", arguments: [lintScriptPath] },
        {
            processEmitter,
            runChild: () => {
                throw new Error("not found");
            },
        },
    );
    assert.equal(exitCode, 2);
    assert.deepEqual(messages, ["Unable to start the policy linter.\n"]);
});
