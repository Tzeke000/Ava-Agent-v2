# SELF_ASSESSMENT: I manage my own visual style — emotion-to-shape mappings, orb personality. I own my own face.
"""
Phase 56 — Ava's style management tool.

Ava can propose new emotion→shape mappings via ava_style.json.
These are her choices, not ours.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from tools.tool_registry import register_tool

VALID_SHAPES = {
    "sphere", "teardrop", "compressed", "elongated", "contracted", "scattered",
    "double", "spiral", "pointer", "cube", "prism", "cylinder", "infinity",
    "double_helix", "burst", "contracted_tremor", "rising",
}


def _load_style(base: Path) -> dict:
    p = base / "state" / "ava_style.json"
    if not p.is_file():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_style(base: Path, data: dict) -> None:
    p = base / "state" / "ava_style.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    data["last_updated"] = time.time()
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _propose_expression(params: dict[str, Any], g: dict[str, Any]) -> dict[str, Any]:
    emotion = str(params.get("emotion") or "").strip().lower()
    shape = str(params.get("shape") or "").strip().lower()
    reason = str(params.get("reason") or "").strip()[:300]

    if not emotion:
        return {"ok": False, "error": "emotion required"}
    if shape and shape not in VALID_SHAPES:
        return {"ok": False, "error": f"unknown shape '{shape}'. Valid: {sorted(VALID_SHAPES)}"}

    base = Path(g.get("BASE_DIR") or ".")
    style = _load_style(base)
    mappings = style.setdefault("emotion_shape_mappings", {})
    mappings[emotion] = {"shape": shape, "reason": reason, "ts": time.time()}
    _save_style(base, style)

    return {"ok": True, "emotion": emotion, "shape": shape, "note": "Mapping saved to ava_style.json — will be used by the orb."}


def _get_style(params: dict[str, Any], g: dict[str, Any]) -> dict[str, Any]:
    base = Path(g.get("BASE_DIR") or ".")
    return {"ok": True, "style": _load_style(base)}


register_tool("propose_expression", "Propose a new emotion→shape mapping for my orb. I own my own face.", 1, _propose_expression)
register_tool("get_style", "Read my current visual style configuration.", 1, _get_style)
