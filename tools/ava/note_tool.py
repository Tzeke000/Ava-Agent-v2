from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from tools.tool_registry import register_tool

BASE = Path("D:/AvaAgentv2").resolve()


def write_note(text: str) -> dict[str, Any]:
    note = str(text or "").strip()
    if not note:
        return {"ok": False, "error": "empty_note"}
    path = BASE / "state" / "pickup_note.json"
    payload = {"timestamp": time.time(), "note": note}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"ok": True, "path": str(path), "note_preview": note[:120]}


def _tool_note(params: dict[str, Any], g: dict[str, Any]) -> dict[str, Any]:
    try:
        return write_note(str(params.get("text") or ""))
    except Exception as e:
        return {"ok": False, "error": str(e)}


register_tool("note_self", "Write a note for Ava's next startup.", 1, _tool_note)

