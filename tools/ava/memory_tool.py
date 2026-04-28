from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tools.tool_registry import register_tool

BASE = Path("D:/AvaAgentv2").resolve()


def query_memory(query: str, limit: int = 8) -> list[dict[str, Any]]:
    q = str(query or "").lower().strip()
    if not q:
        return []
    path = BASE / "memory" / "self reflection" / "reflection_log.jsonl"
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        if not isinstance(row, dict):
            continue
        text = f"{row.get('summary','')} {row.get('user_input','')} {row.get('ai_reply','')}".lower()
        if q in text:
            rows.append(
                {
                    "timestamp": row.get("timestamp"),
                    "summary": str(row.get("summary") or "")[:260],
                    "importance": row.get("importance"),
                }
            )
    return rows[-max(1, int(limit or 8)) :]


def _tool_memory(params: dict[str, Any], g: dict[str, Any]) -> dict[str, Any]:
    try:
        query = str(params.get("query") or "")
        limit = int(params.get("limit") or 8)
        return {"ok": True, "matches": query_memory(query, limit=limit)}
    except Exception as e:
        return {"ok": False, "error": str(e), "matches": []}


register_tool("memory_query", "Query Ava reflection memory summaries.", 1, _tool_memory)

