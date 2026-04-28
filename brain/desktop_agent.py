from __future__ import annotations

import glob
import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import requests
from fury import create_tool


SAFE_ROOTS = [
    Path("D:/AvaAgentv2").resolve(),
    Path.home().resolve(),
]


def _in_safe_zone(path: Path) -> bool:
    rp = path.resolve()
    for root in SAFE_ROOTS:
        try:
            rp.relative_to(root)
            return True
        except Exception:
            continue
    return False


def _safe_path(path: str) -> Path:
    p = Path(path).expanduser()
    if not p.is_absolute():
        p = (Path("D:/AvaAgentv2") / p).resolve()
    if not _in_safe_zone(p):
        raise ValueError(f"path outside safe zones: {p}")
    return p


def _ps(cmd: str, timeout: int = 10) -> dict[str, Any]:
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-Command", cmd],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return {"stdout": proc.stdout[:8000], "stderr": proc.stderr[:4000], "code": proc.returncode}


def _is_safe_ps_command(cmd: str) -> bool:
    c = " ".join((cmd or "").strip().split())
    if not c:
        return False
    blocked = [
        " set-",
        " remove-",
        " delete",
        " format",
        " rm ",
        " del ",
        " stop-process",
        " new-item",
        " copy-item",
        " move-item",
    ]
    low = f" {c.lower()} "
    if any(x in low for x in blocked):
        return False
    allowed_starts = ("get-", "dir", "ls", "echo", "whoami", "hostname", "systeminfo")
    return low.strip().startswith(allowed_starts)


@dataclass
class ToolEntry:
    tier: int
    handler: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]
    fury_tool: Any


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolEntry] = {}
        self._register_tools()

    def _register(self, name: str, tier: int, description: str, input_schema: dict[str, Any], handler: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]) -> None:
        tool = create_tool(
            id=name,
            description=description,
            execute=lambda **kwargs: handler(kwargs, {}),
            input_schema=input_schema,
            output_schema={"type": "object"},
        )
        self._tools[name] = ToolEntry(tier=tier, handler=handler, fury_tool=tool)

    def _register_tools(self) -> None:
        self._register(
            "read_file",
            1,
            "Read a text file within safe zones.",
            {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
            self._t_read_file,
        )
        self._register(
            "list_directory",
            1,
            "List files in a directory.",
            {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
            self._t_list_directory,
        )
        self._register(
            "search_files",
            1,
            "Search file paths by glob pattern.",
            {
                "type": "object",
                "properties": {"path": {"type": "string"}, "pattern": {"type": "string"}},
                "required": ["path", "pattern"],
            },
            self._t_search_files,
        )
        self._register(
            "run_powershell_safe",
            1,
            "Run read-only PowerShell diagnostics.",
            {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]},
            self._t_run_powershell_safe,
        )
        self._register(
            "web_fetch",
            1,
            "Fetch URL text content.",
            {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]},
            self._t_web_fetch,
        )
        self._register(
            "get_screen_info",
            1,
            "List open windows/processes.",
            {"type": "object", "properties": {}},
            self._t_get_screen_info,
        )
        self._register(
            "write_file",
            2,
            "Write file content (proposal only).",
            {
                "type": "object",
                "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
                "required": ["path", "content"],
            },
            self._t_write_file,
        )
        self._register(
            "run_powershell_write",
            2,
            "Run modifying PowerShell command (proposal only).",
            {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]},
            self._t_run_powershell_write,
        )
        self._register(
            "open_application",
            2,
            "Open app or URL (proposal only).",
            {"type": "object", "properties": {"target": {"type": "string"}}, "required": ["target"]},
            self._t_open_application,
        )
        self._register(
            "run_powershell_admin",
            3,
            "Run elevated PowerShell command (explicit approval required).",
            {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]},
            self._t_run_powershell_admin,
        )

    def _record(self, g: dict[str, Any], name: str, result: dict[str, Any]) -> None:
        g["_desktop_last_tool_used"] = name
        g["_desktop_last_tool_result"] = json.dumps(result, ensure_ascii=False)[:200]
        g["_desktop_tool_execution_count"] = int(g.get("_desktop_tool_execution_count", 0) or 0) + 1

    def _proposal(self, g: dict[str, Any], name: str, params: dict[str, Any], risk: str) -> dict[str, Any]:
        rows = list(g.get("_desktop_tier2_pending") or [])
        proposal = {
            "id": f"{name}:{len(rows)+1}",
            "tool": name,
            "params": params,
            "risk": risk,
        }
        rows.append(proposal)
        g["_desktop_tier2_pending"] = rows[-100:]
        return {"ok": True, "message": "proposal created, awaiting approval", "proposal": proposal}

    def execute(self, tool_name: str, params: dict[str, Any], g: dict[str, Any]) -> dict[str, Any]:
        entry = self._tools.get(tool_name)
        if entry is None:
            out = {"ok": False, "error": f"unknown tool: {tool_name}"}
            self._record(g, tool_name, out)
            return out
        if entry.tier == 1:
            res = entry.handler(params, g)
            self._record(g, tool_name, res)
            return res
        if entry.tier == 2:
            res = self._proposal(g, tool_name, params, risk="medium")
            self._record(g, tool_name, res)
            return res
        res = {
            "ok": False,
            "error": "explicit confirmation required",
            "message": "Tier 3 tool blocked until explicit user approval.",
        }
        self._record(g, tool_name, res)
        return res

    def pending_tier2_count(self, g: dict[str, Any]) -> int:
        return len(list(g.get("_desktop_tier2_pending") or []))

    # ---------- handlers ----------
    def _t_read_file(self, params: dict[str, Any], g: dict[str, Any]) -> dict[str, Any]:
        try:
            p = _safe_path(str(params.get("path") or ""))
            text = p.read_text(encoding="utf-8", errors="replace")
            return {"ok": True, "path": str(p), "content": text[:20000]}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _t_list_directory(self, params: dict[str, Any], g: dict[str, Any]) -> dict[str, Any]:
        try:
            p = _safe_path(str(params.get("path") or ""))
            if not p.is_dir():
                return {"ok": False, "error": f"not a directory: {p}"}
            rows = []
            for child in p.iterdir():
                try:
                    rows.append({"name": child.name, "size": child.stat().st_size, "dir": child.is_dir()})
                except Exception:
                    rows.append({"name": child.name, "size": None, "dir": child.is_dir()})
            return {"ok": True, "path": str(p), "items": rows[:500]}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _t_search_files(self, params: dict[str, Any], g: dict[str, Any]) -> dict[str, Any]:
        try:
            p = _safe_path(str(params.get("path") or ""))
            pat = str(params.get("pattern") or "*")
            hits = glob.glob(str(p / "**" / pat), recursive=True)
            hits = [h for h in hits if _in_safe_zone(Path(h))]
            return {"ok": True, "path": str(p), "pattern": pat, "matches": hits[:1000]}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _t_run_powershell_safe(self, params: dict[str, Any], g: dict[str, Any]) -> dict[str, Any]:
        cmd = str(params.get("command") or "")
        if not _is_safe_ps_command(cmd):
            return {"ok": False, "error": "blocked non-read-only command"}
        try:
            out = _ps(cmd, timeout=10)
            return {"ok": True, **out}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _t_web_fetch(self, params: dict[str, Any], g: dict[str, Any]) -> dict[str, Any]:
        url = str(params.get("url") or "")
        if not re.match(r"^https?://", url):
            return {"ok": False, "error": "invalid_url"}
        try:
            r = requests.get(url, timeout=15)
            return {"ok": True, "status_code": r.status_code, "content": r.text[:5000]}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _t_get_screen_info(self, params: dict[str, Any], g: dict[str, Any]) -> dict[str, Any]:
        try:
            out = _ps("tasklist", timeout=10)
            lines = [ln for ln in out.get("stdout", "").splitlines() if ln.strip()]
            return {"ok": True, "active_app": os.environ.get("PROCESSOR_IDENTIFIER", ""), "open_windows": lines[:120]}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _t_write_file(self, params: dict[str, Any], g: dict[str, Any]) -> dict[str, Any]:
        return self._proposal(
            g,
            "write_file",
            {
                "path": str(params.get("path") or ""),
                "content_preview": str(params.get("content") or "")[:300],
            },
            risk="medium",
        )

    def _t_run_powershell_write(self, params: dict[str, Any], g: dict[str, Any]) -> dict[str, Any]:
        return self._proposal(
            g,
            "run_powershell_write",
            {"command": str(params.get("command") or "")[:500]},
            risk="high",
        )

    def _t_open_application(self, params: dict[str, Any], g: dict[str, Any]) -> dict[str, Any]:
        return self._proposal(
            g,
            "open_application",
            {"target": str(params.get("target") or "")[:400]},
            risk="medium",
        )

    def _t_run_powershell_admin(self, params: dict[str, Any], g: dict[str, Any]) -> dict[str, Any]:
        return {
            "ok": False,
            "error": "tier3_requires_explicit_approval",
            "command": str(params.get("command") or "")[:500],
        }
