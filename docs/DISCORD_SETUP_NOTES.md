# Discord channel — Windows setup notes

The `claude-plugins-official/discord` plugin works on Windows, but its default
MCP spawn config (`"command": "bun"`) relies on `bun` being on the PATH that
Claude Code's MCP loader inherits. On Windows that is unreliable:

- `winget install Oven-sh.Bun` puts bun on the **User** `PATH` only, not the
  Machine `PATH`.
- A Claude Code instance launched from a shell opened **before** bun was
  installed (or from a non-shell context like a scheduled task) will not see
  the new PATH entry.
- Claude Code spawns MCP servers via `cmd.exe`. If the parent's PATH lacks
  bun's directory, the spawn dies with:

  ```
  'bun' is not recognized as an internal or external command
  ```

  manifesting in `/mcp` as `plugin:discord:discord — Status: failed`.

## The fix

Patch the plugin's `.mcp.json` so the MCP spawn doesn't depend on PATH at
all for the initial process, AND prepends bun's install directory ahead of
the inherited PATH so inner `bun install && bun server.ts` invocations
(from the package start script) also resolve `bun`.

### What goes wrong with PowerShell-written patches

PowerShell 5.1's `Set-Content -Encoding utf8` writes a UTF-8 BOM
(`EF BB BF`). Node's `JSON.parse` rejects BOM-prefixed JSON. When the
plugin loader reads a BOM-prefixed `.mcp.json` it silently drops the entry
— `/mcp` reports "no MCP servers configured" and the plugin appears
to disappear entirely (vs. registering as `failed`).

We use Python (which writes BOM-free UTF-8 by default) to avoid this trap.

### What goes wrong with cache-only patches

The plugin loader copies
```
%USERPROFILE%\.claude\plugins\marketplaces\claude-plugins-official\external_plugins\discord\.mcp.json
```
over the cached
```
%USERPROFILE%\.claude\plugins\cache\claude-plugins-official\discord\<ver>\.mcp.json
```
on every startup. The relevant debug-log line:

```
[DEBUG] Copied plugin discord to versioned cache:
        C:\Users\...\plugins\cache\claude-plugins-official\discord\0.0.4
```

A patch applied only to the cache gets clobbered on the next launch. The
repair script patches BOTH the marketplace source (durable across launches)
and the cache (defensive in case the marketplace is refreshed).

### Patched `.mcp.json` shape

```json
{
  "mcpServers": {
    "discord": {
      "command": "C:\\Users\\<you>\\AppData\\Local\\Microsoft\\WinGet\\Packages\\Oven-sh.Bun_Microsoft.Winget.Source_8wekyb3d8bbwe\\bun-windows-x64\\bun.exe",
      "args": ["run", "--cwd", "${CLAUDE_PLUGIN_ROOT}", "--shell=bun", "--silent", "start"],
      "env": {
        "PATH": "C:\\Users\\<you>\\AppData\\Local\\Microsoft\\WinGet\\Packages\\Oven-sh.Bun_Microsoft.Winget.Source_8wekyb3d8bbwe\\bun-windows-x64;${PATH}"
      }
    }
  }
}
```

Two layers of defence:
1. `command` is the absolute path to `bun.exe` (canonicalised — no `\.\`
   artefacts from winget's PATH entry). The initial spawn doesn't need
   `bun` on PATH at all.
2. `env.PATH` prepends bun's directory ahead of `${PATH}` (Claude Code
   expands `${PATH}` from the parent process at MCP-config parse time),
   so inner `bun install` and `bun server.ts` invocations from the
   package's start script also find bun.

## Repair script

```powershell
py -3.11 scripts\repair_discord_plugin.py
```

The script is idempotent. It:
- Locates `bun.exe` via `shutil.which` then resolves to drop `\.\` segments
- Patches the marketplace source `.mcp.json`
- Patches every versioned cache `.mcp.json` under the plugin cache
- Writes UTF-8 without BOM

Re-run any time the plugin is reinstalled or the marketplace is refreshed.

## Smoke test

```powershell
py -3.11 scripts\smoketest_discord_mcp.py
```

Spawns the patched MCP command exactly as Claude Code's loader would and
runs the JSON-RPC `initialize` handshake. Exits 0 with
`OK: server responded. name='discord' version='1.0.0'` on success. Use
this to confirm the patch works before launching a real `claude` session.

## Acceptance test

```powershell
claude mcp list
```

Should print:
```
plugin:discord:discord: ...\bun.exe run --cwd ... --shell=bun --silent start - ✓ Connected
```

Then launch interactively:
```powershell
claude --channels plugin:discord@claude-plugins-official --dangerously-skip-permissions
```

Confirm:
1. The startup banner shows `Listening for channel messages from:
   plugin:discord@claude-plugins-official`.
2. Bot status goes online in Discord within ~30 seconds.
3. DM the bot from your phone — message arrives as a
   `<channel source="discord" ...>` notification and a Claude reply
   lands back in the DM.

## What was tried first (and why it failed)

| Attempt                                                       | Outcome              | Cause                                                                                                       |
|---------------------------------------------------------------|----------------------|-------------------------------------------------------------------------------------------------------------|
| `command = "<bun-source-from-Get-Command>"`                   | Plugin disappeared   | `\.\` segment in winget PATH; `Set-Content -Encoding utf8` added a BOM that broke JSON parsing             |
| `command = "bun"` + `env.PATH = "<bun-dir>;${PATH}"`          | Plugin disappeared   | Same BOM problem; ALSO patch was on cache only and got overwritten by the marketplace source on next start |
| Python rewrite, BOM-free, marketplace + cache, absolute bun   | ✓ Connected          | —                                                                                                           |

## Why not just add bun to system PATH?

Works too, but requires admin and mutates global Windows state. The
file-based patch is per-user, no-admin, and survives Claude Code reinstalls.

## Manual fallback

If anything in the auto-spawn path goes sideways, the original
"open a second shell and run `bun run --silent start` in the plugin
cache dir" workflow still works.
