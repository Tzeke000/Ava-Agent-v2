# scripts/repair_discord_plugin.ps1
#
# Patches the cached discord channel plugin's .mcp.json so the bun MCP server
# spawn finds bun.exe even when Claude Code's parent shell PATH lacks bun's
# winget install dir. See docs/DISCORD_SETUP_NOTES.md for background.
#
# Strategy: keep `command: "bun"` (portable), add an `env.PATH` entry that
# prepends bun's directory ahead of the inherited parent PATH (expanded by
# Claude Code at MCP-config parse time via ${PATH}).
#
# Idempotent. Safe to re-run after every plugin upgrade.

$ErrorActionPreference = 'Stop'

$bun = Get-Command bun -ErrorAction SilentlyContinue
if (-not $bun) {
    Write-Error "bun.exe not found on PATH. Install with 'winget install Oven-sh.Bun' first."
    exit 1
}
$bunDir = [IO.Path]::GetFullPath((Split-Path -Parent $bun.Source))
Write-Host "bun dir: $bunDir"

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

$discord = $mcpJson.mcpServers.discord
$wantPath = "$bunDir;`${PATH}"

# Reset command back to plain "bun" (older revisions of this script wrote an
# absolute path; we now prefer the env-PATH approach).
$discord.command = 'bun'

if ($discord.PSObject.Properties.Name -contains 'env') {
    if ($discord.env.PSObject.Properties.Name -contains 'PATH' -and $discord.env.PATH -eq $wantPath) {
        Write-Host "already patched, no change needed."
        exit 0
    }
    $discord.env | Add-Member -NotePropertyName PATH -NotePropertyValue $wantPath -Force
} else {
    $envObj = [PSCustomObject]@{ PATH = $wantPath }
    $discord | Add-Member -NotePropertyName env -NotePropertyValue $envObj -Force
}

$mcpJson | ConvertTo-Json -Depth 10 | Set-Content -Path $mcpPath -Encoding utf8
Write-Host "patched: command=bun, env.PATH prepends $bunDir"
Write-Host ""
Write-Host "Test with: claude --channels plugin:discord@claude-plugins-official --dangerously-skip-permissions"
