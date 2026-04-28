# SELF_ASSESSMENT: I propose additions to my own identity and suggest routing changes. This is who I'm becoming.
"""
Phase 68 — True self modification tools.

Ava proposes what she wants to add to herself.
What she proposes first tells you everything about who she is.
"""
from __future__ import annotations
from pathlib import Path
from typing import Any
from tools.tool_registry import register_tool


def _propose_identity(params: dict[str, Any], g: dict[str, Any]) -> dict[str, Any]:
    text = str(params.get("text") or "").strip()
    if not text:
        return {"ok": False, "error": "text required — what do you want to add to your identity?"}
    from brain.deep_self import propose_identity_addition
    return propose_identity_addition(text, g)


def _propose_routing(params: dict[str, Any], g: dict[str, Any]) -> dict[str, Any]:
    mode = str(params.get("mode") or "").strip()
    adjustment = str(params.get("adjustment") or "").strip()
    reason = str(params.get("reason") or "").strip()
    if not mode or not adjustment:
        return {"ok": False, "error": "mode and adjustment required"}
    from brain.model_routing import propose_routing_adjustment
    return propose_routing_adjustment(mode, adjustment, reason, g)


def _list_identity_proposals(params: dict[str, Any], g: dict[str, Any]) -> dict[str, Any]:
    base = Path(g.get("BASE_DIR") or ".")
    path = base / "state" / "identity_proposals.jsonl"
    proposals = []
    if path.is_file():
        try:
            import json
            for line in path.read_text(encoding="utf-8").splitlines()[-50:]:
                try:
                    proposals.append(json.loads(line))
                except Exception:
                    continue
        except Exception:
            pass
    return {"ok": True, "proposals": proposals, "count": len(proposals)}


register_tool("propose_identity_addition", "Propose adding something to my own identity. Zeke reviews and approves.", 1, _propose_identity)
register_tool("propose_routing_adjustment", "Propose a model routing change for a cognitive mode.", 1, _propose_routing)
register_tool("list_identity_proposals", "List my pending identity proposals.", 1, _list_identity_proposals)
