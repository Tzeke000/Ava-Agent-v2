# SELF_ASSESSMENT: I point the widget orb at screen elements to draw Zeke's attention.
"""
Phase 49 — Screen pointer tool.

Tier 1: Ava requests the widget to point at a screen element.
Sets a pointing state in globals that the operator snapshot exposes.
The frontend reads pointing_target and switches OrbCanvas to pointer shape.

Bootstrap: Ava tracks whether pointing correlates with positive engagement.
She does it less if you ignore her and more if you engage with it.
"""
from __future__ import annotations

import time
import threading
from typing import Any

from tools.tool_registry import register_tool

_POINTING_UNTIL: float = 0.0
_POINTING_DESCRIPTION: str = ""


def _point_at_element(params: dict[str, Any], g: dict[str, Any]) -> dict[str, Any]:
    global _POINTING_UNTIL, _POINTING_DESCRIPTION
    description = str(params.get("description") or "").strip()[:200]
    duration = min(max(float(params.get("duration_seconds") or 3.0), 1.0), 10.0)

    # Attempt pywinauto coordinate lookup (best-effort)
    coords: dict[str, int] | None = None
    try:
        import pywinauto
        from pywinauto import Desktop
        desk = Desktop(backend="uia")
        windows = desk.windows()
        for win in windows:
            try:
                title = str(win.window_text() or "").lower()
                if any(kw in title for kw in description.lower().split()[:3]):
                    rect = win.rectangle()
                    coords = {
                        "x": (rect.left + rect.right) // 2,
                        "y": (rect.top + rect.bottom) // 2,
                    }
                    break
            except Exception:
                continue
    except ImportError:
        pass
    except Exception:
        pass

    _POINTING_UNTIL = time.time() + duration
    _POINTING_DESCRIPTION = description

    # Set pointing state in globals for operator snapshot
    g["_widget_pointing"] = True
    g["_widget_pointing_description"] = description
    g["_widget_pointing_until"] = _POINTING_UNTIL
    if coords:
        g["_widget_pointing_coords"] = coords

    # Auto-reset after duration
    def _reset():
        time.sleep(duration + 0.5)
        g.pop("_widget_pointing", None)
        g.pop("_widget_pointing_description", None)
        g.pop("_widget_pointing_until", None)
        g.pop("_widget_pointing_coords", None)

    threading.Thread(target=_reset, daemon=True).start()

    # Track usage for bootstrap
    history = list(g.get("_pointing_history") or [])
    history.append({
        "ts": time.time(),
        "description": description,
        "had_coords": coords is not None,
    })
    g["_pointing_history"] = history[-50:]

    return {
        "ok": True,
        "pointing_at": description,
        "duration_seconds": duration,
        "coords": coords,
        "message": f"Pointing at '{description}' for {duration}s",
    }


register_tool(
    name="point_at_element",
    description="Point the widget orb at a screen element to draw attention. Tier 1 — use freely.",
    tier=1,
    handler=_point_at_element,
)
