#!/usr/bin/env node
import { spawn, spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import path from "node:path";

const packageRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const materializerPath = path.join(packageRoot, "scripts", "codex_compat_materializer.py");
const bridgePath = path.join(packageRoot, "scripts", "codex_capability_bridge.py");
const pythonNames = process.platform === "win32" ? ["py", "python"] : ["python3", "python"];

export function createHelpText() {
    return [
        "Usage: codex-compat <command> [options]",
        "",
        "Commands:",
        "  materialize  Plan or apply Claude agents into an explicit Codex root",
        "  bridge       Translate a Claude capability request to a declarative record",
        "",
        "Materialize options:",
        "  --source-root <path>  Claude source root (required)",
        "  --target-root <path>  Codex target root (required)",
        "  --apply               Write changes; default is dry-run",
        "  --python <command>    Python interpreter override",
        "",
        "Bridge options:",
        "  --surface <name>      Capability surface (required)",
        "  --payload <json>      JSON object payload (required)",
        "  --python <command>    Python interpreter override",
        "",
        "Python may also be selected with CODEX_COMPAT_PYTHON. Roots are never inferred or written automatically.",
    ].join("\n");
}

function readOption(argumentsList, optionName) {
    const optionIndex = argumentsList.indexOf(optionName);
    if (optionIndex < 0) return undefined;
    return argumentsList[optionIndex + 1];
}

function requireOption(argumentsList, optionName) {
    const optionValue = readOption(argumentsList, optionName);
    if (!optionValue || optionValue.startsWith("--")) throw new Error(`Missing required option: ${optionName}`);
    return optionValue;
}

function writeErrorRecord(errorCode, errorMessage) {
    process.stderr.write(`${JSON.stringify({ error: { code: errorCode, message: errorMessage } })}\n`);
}

export function buildCommand(commandName, argumentsList, interpreter) {
    if (commandName === "materialize") {
        const sourceRoot = requireOption(argumentsList, "--source-root");
        const targetRoot = requireOption(argumentsList, "--target-root");
        const materializerArguments = [materializerPath, sourceRoot, targetRoot];
        if (argumentsList.includes("--apply")) materializerArguments.push("--apply");
        return { executable: interpreter, arguments: materializerArguments };
    }
    if (commandName === "bridge") {
        const surface = requireOption(argumentsList, "--surface");
        const payload = requireOption(argumentsList, "--payload");
        return { executable: interpreter, arguments: [bridgePath, surface, payload] };
    }
    throw new Error(`Unknown command: ${commandName}`);
}

export function findPython(commandNames = pythonNames, canRun = (command) => spawnSync(command, ["--version"], { stdio: "ignore" }).status === 0) {
    for (const eachCommand of commandNames) {
        if (canRun(eachCommand)) return eachCommand;
    }
    return undefined;
}

export function runCommand(command, runChild = spawn) {
    return new Promise((resolve) => {
        const childProcess = runChild(command.executable, command.arguments, { stdio: "inherit" });
        childProcess.on("close", (exitCode, signal) => resolve(exitCode ?? 1 + (signal ? 1 : 0)));
        childProcess.on("error", () => resolve(1));
    });
}

export async function main(argumentsList = process.argv.slice(2), dependencies = {}) {
    if (argumentsList.length === 0 || argumentsList.includes("--help") || argumentsList.includes("-h")) {
        process.stdout.write(`${createHelpText()}\n`);
        return 0;
    }
    const [commandName, ...commandArguments] = argumentsList;
    try {
        const interpreter = readOption(commandArguments, "--python") ?? process.env.CODEX_COMPAT_PYTHON ?? await (dependencies.findPython ?? findPython)();
        if (!interpreter) {
            writeErrorRecord("python_unavailable", "No usable Python interpreter found. Use --python or CODEX_COMPAT_PYTHON.");
            return 1;
        }
        const command = buildCommand(commandName, commandArguments, interpreter);
        return await (dependencies.runCommand ?? runCommand)(command, dependencies.runChild);
    } catch (error) {
        const errorMessage = error instanceof Error ? error.message : "Unknown compatibility command error";
        writeErrorRecord("invalid_command", errorMessage);
        return 2;
    }
}

if (fileURLToPath(import.meta.url) === path.resolve(process.argv[1])) process.exitCode = await main();
