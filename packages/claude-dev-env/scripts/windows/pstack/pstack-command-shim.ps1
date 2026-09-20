$command = $args[0]
$commandArguments = @($args | Select-Object -Skip 1)

if (@("watch-pr", "ship-pr") -notcontains $command) {
  Write-Error "The command must be watch-pr or ship-pr"
  exit 1
}

$codexHome = if ([string]::IsNullOrWhiteSpace($env:CODEX_HOME)) {
  Join-Path $env:USERPROFILE ".codex"
} else {
  $env:CODEX_HOME
}
$cacheRoot = Join-Path $codexHome "plugins\cache\pstack-claude\pstack"
$pluginRoot = Get-ChildItem -LiteralPath $cacheRoot -Directory -ErrorAction SilentlyContinue |
  Where-Object { $_.Name -match "^\d+\.\d+\.\d+$" } |
  Sort-Object { [version]$_.Name } -Descending |
  Select-Object -First 1

if ($null -eq $pluginRoot) {
  Write-Error "No installed pstack-claude version was found under $cacheRoot"
  exit 1
}

$entrypoint = Join-Path $pluginRoot.FullName "skills\poteto-mode\scripts\watch-pr\$command"
if (-not (Test-Path -LiteralPath $entrypoint -PathType Leaf)) {
  Write-Error "The pstack entrypoint was not found: $entrypoint"
  exit 1
}

$scriptsRoot = Split-Path -Parent (Split-Path -Parent $entrypoint)
$exitCode = 1
Push-Location $scriptsRoot
try {
  & bun -e 'import { ensureDependenciesInstalled } from "./bootstrap.ts"; ensureDependenciesInstalled();'
  $bootstrapExitCode = $LASTEXITCODE
  if ($bootstrapExitCode -ne 0) {
    Write-Error "The pstack dependencies could not be installed"
    $exitCode = $bootstrapExitCode
  } else {
    & bun $entrypoint @commandArguments
    $exitCode = $LASTEXITCODE
  }
}
finally {
  Pop-Location
}
exit $exitCode
