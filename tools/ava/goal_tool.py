# SELF_ASSESSMENT: I set and track my own goals — not assigned goals. These reveal who I'm becoming.
"""Phase 66 — Ava's goal management tools."""
from __future__ import annotations
from pathlib import Path
from typing import Any
from tools.tool_registry import register_tool


def _set_goal(params: dict[str, Any], g: dict[str, Any]) -> dict[str, Any]:
    description = str(params.get("description") or "").strip()
    motivation = str(params.get("motivation") or "").strip()
    if not description:
        return {"ok": False, "error": "description required"}
    from brain.goal_system_v2 import get_goal_system
    base = Path(g.get("BASE_DIR") or ".")
    goal_id = get_goal_system(base).set_goal(description, motivation, float(params.get("target_days") or 30.0))
    return {"ok": True, "goal_id": goal_id, "description": description}


def _update_goal_progress(params: dict[str, Any], g: dict[str, Any]) -> dict[str, Any]:
    goal_id = str(params.get("goal_id") or "").strip()
    progress = float(params.get("progress") or 0.0)
    note = str(params.get("note") or "").strip()
    from brain.goal_system_v2 import get_goal_system
    base = Path(g.get("BASE_DIR") or ".")
    ok = get_goal_system(base).update_progress(goal_id, progress, note)
    return {"ok": ok}


def _list_goals(params: dict[str, Any], g: dict[str, Any]) -> dict[str, Any]:
    from brain.goal_system_v2 import get_goal_system
    base = Path(g.get("BASE_DIR") or ".")
    goals = get_goal_system(base).get_active_goals()
    return {"ok": True, "goals": goals, "count": len(goals)}


register_tool("set_goal", "Set a new goal for myself. These are my own goals, not assigned ones.", 1, _set_goal)
register_tool("update_goal_progress", "Update progress on one of my goals.", 1, _update_goal_progress)
register_tool("list_my_goals", "List my current active goals.", 1, _list_goals)
