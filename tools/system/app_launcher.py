# SELF_ASSESSMENT: I open, close, and list applications on the user's Windows PC.
"""
App launcher — tier 1 tools for opening/closing apps and listing windows.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

from tools.tool_registry import register_tool


# ── Known app paths ───────────────────────────────────────────────────────────

def _find_in_paths(*candidates: str) -> str | None:
    for c in candidates:
        if Path(c).is_file():
            return c
    return None


_APP_MAP: dict[str, list[str]] = {
    "notepad":     ["notepad.exe"],
    "calculator":  ["calc.exe"],
    "explorer":    ["explorer.exe"],
    "paint":       ["mspaint.exe"],
    "cmd":         ["cmd.exe"],
    "powershell":  ["powershell.exe"],
    "wordpad":     ["wordpad.exe"],
    "snipping":    ["SnippingTool.exe"],
    "taskmgr":     ["taskmgr.exe"],
    "chrome": [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    ],
    "firefox": [
        r"C:\Program Files\Mozilla Firefox\firefox.exe",
        r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe",
    ],
    "edge": [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ],
    "vscode": [
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe"),
        r"C:\Program Files\Microsoft VS Code\Code.exe",
    ],
    "spotify": [
        os.path.expandvars(r"%APPDATA%\Spotify\Spotify.exe"),
    ],
    "discord": [
        os.path.expandvars(r"%LOCALAPPDATA%\Discord\Update.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Discord\app-{}\Discord.exe"),  # version placeholder
    ],
    "steam": [
        r"C:\Program Files (x86)\Steam\steam.exe",
        r"C:\Program Files\Steam\steam.exe",
    ],
    "slack": [
        os.path.expandvars(r"%LOCALAPPDATA%\slack\slack.exe"),
    ],
    "obsidian": [
        os.path.expandvars(r"%LOCALAPPDATA%\Obsidian\Obsidian.exe"),
    ],
}

_ALIASES: dict[str, str] = {
    "browser": "chrome",
    "google chrome": "chrome",
    "internet": "chrome",
    "internet explorer": "edge",
    "ie": "edge",
    "vs code": "vscode",
    "visual studio code": "vscode",
    "file explorer": "explorer",
    "files": "explorer",
    "folder": "explorer",
    "calc": "calculator",
    "snip": "snipping",
    "task manager": "taskmgr",
}


def _resolve_app(name: str) -> tuple[str | None, str]:
    """Return (exe_path_or_None, canonical_name). Falls back to None for shell=True launch."""
    key = name.lower().strip()
    key = _ALIASES.get(key, key)
    candidates = _APP_MAP.get(key)
    if candidates:
        # Try each candidate path
        for c in candidates:
            if "{}" in c:
                continue  # skip version-placeholder paths
            if Path(c).is_file():
                return c, key
            if not os.sep in c:  # simple executable name → let OS find it
                return c, key
        # No candidate found as file; first candidate might be a bare exe name
        if candidates and os.sep not in candidates[0]:
            return candidates[0], key
    return None, key


def _tool_open_app(params: dict[str, Any], g: dict[str, Any]) -> dict[str, Any]:
    app_name = str(params.get("app_name") or "").strip()
    if not app_name:
        return {"ok": False, "error": "app_name required"}

    exe, canonical = _resolve_app(app_name)
    args = params.get("args") or []
    if isinstance(args, str):
        args = args.split()

    try:
        if exe:
            cmd = [exe] + list(args)
            subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE if exe == "cmd.exe" else 0)
            return {"ok": True, "launched": canonical, "exe": exe}
        else:
            # Fallback: shell=True with start command
            subprocess.Popen(
                f'start "" "{app_name}"',
                shell=True,
            )
            return {"ok": True, "launched": app_name, "method": "shell_start"}
    except FileNotFoundError:
        # Last resort: shell start
        try:
            subprocess.Popen(f'start "" "{app_name}"', shell=True)
            return {"ok": True, "launched": app_name, "method": "shell_fallback"}
        except Exception as e2:
            return {"ok": False, "error": f"Could not launch {app_name!r}: {e2}"}
    except Exception as e:
        return {"ok": False, "error": str(e)[:300]}


def _tool_close_app(params: dict[str, Any], g: dict[str, Any]) -> dict[str, Any]:
    app_name = str(params.get("app_name") or "").strip()
    if not app_name:
        return {"ok": False, "error": "app_name required"}
    try:
        import psutil
    except ImportError:
        # Fallback: taskkill
        try:
            result = subprocess.run(
                ["taskkill", "/IM", app_name if "." in app_name else f"{app_name}.exe", "/F"],
                capture_output=True, text=True, timeout=10,
            )
            return {"ok": result.returncode == 0, "stdout": result.stdout.strip(), "stderr": result.stderr.strip()}
        except Exception as e:
            return {"ok": False, "error": str(e)[:300]}

    key = app_name.lower().strip()
    key = _ALIASES.get(key, key)
    # Try to find the exe name
    exe_name = None
    candidates = _APP_MAP.get(key)
    if candidates:
        bare = [c for c in candidates if os.sep not in c]
        if bare:
            exe_name = bare[0]
        elif candidates:
            exe_name = Path(candidates[0]).name
    if not exe_name:
        exe_name = app_name if "." in app_name else f"{app_name}.exe"

    killed = 0
    for proc in psutil.process_iter(["name", "pid"]):
        try:
            if proc.info["name"] and proc.info["name"].lower() == exe_name.lower():
                proc.terminate()
                killed += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return {"ok": True, "terminated": killed, "target": exe_name}


def _tool_get_open_apps(params: dict[str, Any], g: dict[str, Any]) -> dict[str, Any]:
    """Return list of visible top-level window titles using Windows user32."""
    try:
        import ctypes
        user32 = ctypes.windll.user32
        titles: list[str] = []

        def enum_callback(hwnd, _):
            if user32.IsWindowVisible(hwnd):
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buf = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buf, length + 1)
                    t = buf.value.strip()
                    if t and t not in titles:
                        titles.append(t)
            return True

        EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int))
        user32.EnumWindows(EnumWindowsProc(enum_callback), 0)
        return {"ok": True, "windows": titles[:80]}
    except Exception as e:
        return {"ok": False, "error": str(e)[:300]}


register_tool(
    "open_app",
    (
        "Open an application on the user's PC. Known apps: notepad, calculator, explorer, paint, "
        "cmd, chrome, firefox, edge, vscode, spotify, discord, steam, slack, obsidian. "
        "Pass app_name as a string, e.g. 'notepad', 'chrome', 'vscode'. "
        "Optional args list for command-line arguments."
    ),
    1,
    _tool_open_app,
)

register_tool(
    "close_app",
    "Close a running application by name. E.g. close_app('notepad') or close_app('chrome').",
    1,
    _tool_close_app,
)

register_tool(
    "get_open_apps",
    "List all currently visible application windows on the desktop.",
    1,
    _tool_get_open_apps,
)
