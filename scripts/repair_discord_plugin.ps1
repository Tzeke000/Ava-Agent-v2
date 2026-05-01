# scripts/repair_discord_plugin.ps1
#
# Patches the cached discord channel plugin's .mcp.json to invoke bun by
# absolute path. Fixes "'bun' is not recognized as an internal or external
# command" when Claude Code's MCP spawn inherits a PATH that lacks bun's
# winget install dir. See docs/DISCORD_SETUP_NOTES.md for background.
#
# Idempotent. Safe to re-run after every plugin upgrade.

$ErrorActionPreference = 'Stop'

$bun = Get-Command bun -ErrorAction SilentlyContinue
if (-not $bun) {
    Write-Error "bun.exe not found on PATH. Install with 'winget install Oven-sh.Bun' first."
    exit 1
}
$bunAbs = $bun.Source
Write-Host "bun: $bunAbs"

$cacheRoot = Join-Path $env:USERPROFILE '.claude\plugins\cache\claude-plugins-official\discord'
if (-not (Test-Path $cacheRoot)) {
    Write-Error "Plugin cache not found: $cacheRoot. Run /plugin install discord@claude-plugins-official inside Claude Code first."
    exit 1
}

$versions = Get-ChildItem -Path $cacheRoot -Directory | Sort-Object Name -Descending
if ($versions.Count -eq 0) {
    Write-Error "No version directories under $cacheRoot."
    exit 1
}
$latest = $versions[0].FullName
$mcpPath = Join-Path $latest '.mcp.json'

if (-not (Test-Path $mcpPath)) {
    Write-Error ".mcp.json not found at $mcpPath."
    exit 1
}

Write-Host "patching: $mcpPath"

$mcpJson = Get-Content -Raw -Path $mcpPath | ConvertFrom-Json
if (-not $mcpJson.mcpServers.discord) {
    Write-Error "Unexpected .mcp.json shape - no mcpServers.discord."
    exit 1
}

$current = $mcpJson.mcpServers.discord.command
if ($current -eq $bunAbs) {
    Write-Host "already patched, no change needed."
    exit 0
}

$mcpJson.mcpServers.discord.command = $bunAbs
$mcpJson | ConvertTo-Json -Depth 10 | Set-Content -Path $mcpPath -Encoding utf8
Write-Host "patched: command = $bunAbs"
Write-Host ""
Write-Host "Test with: claude --channels plugin:discord@claude-plugins-official --dangerously-skip-permissions"
