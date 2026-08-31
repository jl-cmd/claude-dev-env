"use strict";

const { spawnSync } = require("node:child_process");

function getPythonCommandCandidates() {
  if (process.platform === "win32") {
    return [["py", "-3"], ["python"]];
  }
  return [["python3"], ["python"]];
}

function runPythonScript() {
  const scriptPath = process.argv[2];
  if (!scriptPath) {
    process.exitCode = 2;
    return;
  }

  const scriptArguments = process.argv.slice(3);
  for (const candidate of getPythonCommandCandidates()) {
    const [pythonCommand, ...pythonArguments] = candidate;
    const childProcess = spawnSync(
      pythonCommand,
      [...pythonArguments, scriptPath, ...scriptArguments],
      { shell: false, stdio: "inherit" },
    );
    if (childProcess.error?.code === "ENOENT") {
      continue;
    }
    if (childProcess.error) {
      process.exitCode = 1;
      return;
    }
    process.exitCode = childProcess.status ?? 1;
    return;
  }

  process.exitCode = 1;
}

runPythonScript();
