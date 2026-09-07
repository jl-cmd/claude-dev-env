#!/usr/bin/env node
import { spawn, spawnSync } from "node:child_process";
import { constants as osConstants } from "node:os";
import { fileURLToPath } from "node:url";
import path from "node:path";

const packageRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const lintScriptPath = path.join(packageRoot, "scripts", "cde_lint.py");
const verificationScriptPath = path.join(packageRoot, "scripts", "local_verification", "cli.py");
const posixSignalStatusOffset = 128;
const lintCommandName = "lint";
const verifyCommandName = "verify";
const pythonOptionName = "--python";
const pythonEnvironmentName = "CDE_PYTHON";


export function createHelpText() {
    return [
        "Usage: cde <lint|verify> [options]",
        "",
        "Run the policy linter with cde lint. Source modes are mutually exclusive:",
        "  --files PATH [PATH ...]  Current worktree files",
        "  --staged                 Staged index content",
        "  --base REVISION          Changes from a base revision",
        "  --repository             Tracked worktree files",
        "  --text-as PATH           One editor buffer from standard input",
        "",
        "Report formats: --format text|json|editor",
        "",
        "Launcher options:",
        "  --python <command>       Python interpreter override",
        "  Exit 0 clean, 1 diagnostics, 2 invalid input or start failure, 3 failed rule",
        "",
        "Run the required-check manifest with cde verify:",
        "  --manifest PATH           JSON required-check manifest",
        "  --repo PATH               Candidate repository root",
        "  --base SHA                Trusted base revision",
        "  --output PATH             JSON verification report",
        "",
        "Python may also be selected with CDE_PYTHON.",
    ].join("\n");
}


export function pythonInterpreterNames(platformName = process.platform) {
    if (platformName === "win32") return ["py", "python"];
    return ["python3", "python"];
}


export function findPython(
    commandNames = pythonInterpreterNames(),
    canRun = (commandName) => spawnSync(commandName, ["--version"], { stdio: "ignore", shell: false }).status === 0,
) {
    for (const eachCommand of commandNames) {
        if (canRun(eachCommand)) return eachCommand;
    }
    return undefined;
}


export function buildLintCommand(interpreter, forwardedArguments) {
    return {
        executable: interpreter,
        arguments: [lintScriptPath, ...forwardedArguments],
    };
}


export function buildVerifyCommand(interpreter, forwardedArguments) {
    return {
        executable: interpreter,
        arguments: [verificationScriptPath, ...forwardedArguments],
    };
}


function takePythonOverride(allArguments) {
    const remainingArguments = [];
    let interpreterOverride;
    for (let index = 0; index < allArguments.length; index += 1) {
        if (allArguments[index] === pythonOptionName) {
            const nextArgument = allArguments[index + 1];
            if (nextArgument === undefined || nextArgument.startsWith("--")) {
                return { error: "--python requires an interpreter command" };
            }
            interpreterOverride = nextArgument;
            index += 1;
            continue;
        }
        remainingArguments.push(allArguments[index]);
    }
    return { interpreterOverride, remainingArguments, error: undefined };
}


function attachSignalForwarding(childProcess, processEmitter) {
    const allSignals = ["SIGINT", "SIGTERM"];
    if (process.platform !== "win32") {
        allSignals.push("SIGHUP");
    }
    const listenerBySignal = [];
    for (const eachSignal of allSignals) {
        const listener = () => {
            try {
                childProcess.kill(eachSignal);
            } catch {
                return;
            }
        };
        processEmitter.on(eachSignal, listener);
        listenerBySignal.push([eachSignal, listener]);
    }
    return () => {
        for (const [eachSignal, listener] of listenerBySignal) {
            processEmitter.off(eachSignal, listener);
        }
    };
}


function statusCodeForSignal(signalName) {
    const signalNumber = osConstants.signals?.[signalName];
    if (signalNumber === undefined) return 1;
    return posixSignalStatusOffset + signalNumber;
}


function runChildCommand(command, failureMessage, dependencies = {}) {
    const runChild = dependencies.runChild ?? spawn;
    const processEmitter = dependencies.processEmitter ?? process;
    return new Promise((resolve) => {
        let childProcess;
        try {
            childProcess = runChild(command.executable, command.arguments, {
                stdio: "inherit",
                shell: false,
                windowsHide: true,
            });
        } catch {
            processEmitter.stderr.write(`${failureMessage}\n`);
            resolve(2);
            return;
        }
        const detachSignals = attachSignalForwarding(childProcess, processEmitter);
        childProcess.on("error", () => {
            detachSignals();
            processEmitter.stderr.write(`${failureMessage}\n`);
            resolve(2);
        });
        childProcess.on("close", (exitCode, signalName) => {
            detachSignals();
            if (exitCode !== null) {
                resolve(exitCode);
                return;
            }
            resolve(statusCodeForSignal(signalName));
        });
    });
}


export function runLintCommand(command, dependencies = {}) {
    return runChildCommand(command, "Unable to start the policy linter.", dependencies);
}


export function runVerifyCommand(command, dependencies = {}) {
    return runChildCommand(command, "Unable to start verification.", dependencies);
}


export async function main(argumentsList = process.argv.slice(2), dependencies = {}) {
    if (argumentsList.length === 0 || argumentsList.includes("--help") || argumentsList.includes("-h")) {
        process.stdout.write(`${createHelpText()}\n`);
        return 0;
    }
    if (![lintCommandName, verifyCommandName].includes(argumentsList[0])) {
        process.stderr.write(`${createHelpText()}\n`);
        return 2;
    }
    const { interpreterOverride, remainingArguments, error } = takePythonOverride(argumentsList.slice(1));
    if (error) {
        process.stderr.write(`${error}\n`);
        return 2;
    }
    const resolvePython = dependencies.findPython ?? findPython;
    const interpreter = interpreterOverride ?? process.env[pythonEnvironmentName] ?? await resolvePython();
    if (!interpreter) {
        process.stderr.write("No usable Python interpreter found. Use --python or CDE_PYTHON.\n");
        return 2;
    }
    const buildCommand = argumentsList[0] === lintCommandName ? buildLintCommand : buildVerifyCommand;
    const command = buildCommand(interpreter, remainingArguments);
    const runCommand = dependencies.runCommand
        ?? (argumentsList[0] === lintCommandName ? runLintCommand : runVerifyCommand);
    return await runCommand(command, dependencies);
}


const isLaunchedDirectly = process.argv[1] !== undefined
    && fileURLToPath(import.meta.url) === path.resolve(process.argv[1]);
if (isLaunchedDirectly) process.exitCode = await main();
