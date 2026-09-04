import { writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { auditHooks } from "./audit-hooks.mjs";

function parseArguments(argv) {
  const options = {
    catalogPath: null,
    format: "text",
    homeDirectory: null,
    includeInstalled: false,
    outputPath: null,
    repositoryRoot: path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../.."),
  };
  for (let offset = 0; offset < argv.length; offset += 1) {
    const argument = argv[offset];
    if (argument === "--installed") options.includeInstalled = true;
    else if (argument === "--catalog") options.catalogPath = argv[++offset];
    else if (argument === "--format") options.format = argv[++offset];
    else if (argument === "--home") options.homeDirectory = argv[++offset];
    else if (argument === "--output") options.outputPath = argv[++offset];
    else if (argument === "--repository-root") options.repositoryRoot = argv[++offset];
    else throw new Error(`unknown argument ${argument}`);
  }
  return options;
}

function renderText(report) {
  const summary = report.summary;
  return [
    `canonical direct: ${summary.directCount}`,
    `dispatchers: ${summary.dispatcherCount}`,
    `hosted entries: ${summary.effectiveCount}`,
    `logical associations: ${summary.logicalAssociationCount}`,
    `unclassified targets: ${summary.unclassifiedCount}`,
    `installed Claude direct: ${summary.claudeDirectCount}`,
    `installed Codex direct: ${summary.codexDirectCount}`,
    `active native Git hooks: ${summary.gitHookCount}`,
    `findings: ${summary.findingCount}`,
  ].join("\n");
}

function main() {
  const options = parseArguments(process.argv.slice(2));
  const report = auditHooks(options);
  const rendered =
    options.format === "json" ? `${JSON.stringify(report, null, 2)}\n` : `${renderText(report)}\n`;
  if (options.outputPath) writeFileSync(options.outputPath, rendered, "utf8");
  else process.stdout.write(rendered);
  process.exitCode = report.findings.some(({ severity }) => severity === "error") ? 1 : 0;
}

main();
