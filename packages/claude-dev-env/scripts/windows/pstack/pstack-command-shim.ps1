param(
  [Parameter(Mandatory = $true, Position = 0)]
  [ValidateSet("watch-pr", "ship-pr")]
  [string]$Command,
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$CommandArguments
)

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

$entrypoint = Join-Path $pluginRoot.FullName "skills\poteto-mode\scripts\watch-pr\$Command"
if (-not (Test-Path -LiteralPath $entrypoint -PathType Leaf)) {
  Write-Error "The pstack entrypoint was not found: $entrypoint"
  exit 1
}

$scriptsRoot = Split-Path -Parent (Split-Path -Parent $entrypoint)
$exitCode = 1
Push-Location $scriptsRoot
try {
  & bun $entrypoint @CommandArguments
  $exitCode = $LASTEXITCODE
}
finally {
  Pop-Location
}
exit $exitCode
