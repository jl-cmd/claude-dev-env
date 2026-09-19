# Rerun recipe: windows-scheduled-task skill eval

Subject: `packages/claude-dev-env/.agents/skills/windows-scheduled-task/SKILL.md` at baseline `6274a010c`.
Host: native Windows, Claude Code 2.1.278. The suite grants `Write` only, so it needs no sandbox backend and no WSL2.

Run each step from the repository root in PowerShell.

1. Build the wrapper outside every skills directory.

   ```powershell
   $w = "$env:LOCALAPPDATA\Temp\cde-skill-eval\wst-wrapper"
   New-Item -ItemType Directory -Force "$w\.claude-plugin", "$w\skills\windows-scheduled-task"
   git show 6274a010c:packages/claude-dev-env/.agents/skills/windows-scheduled-task/SKILL.md | Set-Content -Encoding utf8NoBOM "$w\skills\windows-scheduled-task\SKILL.md"
   '{ "name": "wst-eval", "version": "0.0.1", "description": "Eval wrapper for windows-scheduled-task" }' | Set-Content -Encoding utf8NoBOM "$w\.claude-plugin\plugin.json"
   Copy-Item -Recurse tests\audit\skill_evals\windows-scheduled-task\evals "$w\evals"
   ```

   The plugin name must stay `wst-eval`. The slash case invokes `/wst-eval:windows-scheduled-task`.

2. Smoke run.

   ```powershell
   Set-Location $w
   claude plugin eval . --case contrib-repair --runs 1 --ablation none --model claude-sonnet-5 --max-cost-usd 2 --no-publish --trust-plugin --allow-tools Write
   ```

3. Full two-arm run.

   ```powershell
   claude plugin eval . --runs 5 -j 4 --model claude-sonnet-5 --no-publish --trust-plugin --allow-tools Write --keep-temp --json "$w\..\full.json"
   ```

4. Read `permission_denials` in the `result` line of each `out\trace.jsonl` named by `tracePath` in `full.json`. Read the scripts under `home\cwd` in each kept folder.
5. Delete each kept folder with `Remove-Item -Recurse -Force -Confirm:$false -LiteralPath <folder>`.

## Cases

| Case | Shape | Graded outcome |
|---|---|---|
| `slash-invoke` | slash invocation | file written, registers a task, skill idiom as a with-only indicator |
| `plain-trigger` | plain words | `Skill` call indicator, file written, registers a task |
| `no-trigger` | must not trigger | zero `Skill` calls in both arms, agenda present |
| `contrib-register` | contribution | script meets the five stated requirements |
| `contrib-repair` | contribution | repaired script drops both stated faults and keeps the interval |

The `no-maxvalue-duration` expectation rests on the error text the repair prompt quotes. No locked outside source confirms that `[TimeSpan]::MaxValue` fails registration on this Windows build. Confirm it once with an unelevated `Register-ScheduledTask` call before the verdict counts.
