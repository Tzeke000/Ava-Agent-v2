from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

ToolResult = dict[str, Any]
ToolHandler = Callable[[dict[str, Any], dict[str, Any]], ToolResult]


@dataclass
class ToolDef:
    name: str
    description: str
    tier: int
    handler: ToolHandler


_REGISTRY: dict[str, ToolDef] = {}


def register_tool(name: str, description: str, tier: int, handler: ToolHandler) -> None:
    _REGISTRY[name] = ToolDef(name=name, description=description, tier=int(tier), handler=handler)


def load_builtin_tools() -> None:
    from tools.system import file_manager as _file_manager  # noqa: F401
    from tools.system import process_manager as _process_manager  # noqa: F401
    from tools.web import web_fetch as _web_fetch  # noqa: F401
    from tools.web import web_search as _web_search  # noqa: F401
    from tools.ava import memory_tool as _memory_tool  # noqa: F401
    from tools.ava import note_tool as _note_tool  # noqa: F401


class ToolRegistry:
    def __init__(self) -> None:
        load_builtin_tools()

    def list_tools(self) -> list[dict[str, Any]]:
        out = []
        for d in sorted(_REGISTRY.values(), key=lambda x: x.name):
            out.append({"name": d.name, "description": d.description, "tier": d.tier})
        return out

    def get_tool(self, name: str) -> ToolDef | None:
        return _REGISTRY.get(str(name or "").strip())

    def execute_tool(self, name: str, params: dict[str, Any] | None, g: dict[str, Any]) -> ToolResult:
        tool = self.get_tool(name)
        if tool is None:
            return {"ok": False, "error": f"unknown tool: {name}"}
        try:
            result = tool.handler(params or {}, g)
            if not isinstance(result, dict):
                result = {"ok": True, "result": result}
        except Exception as e:
            result = {"ok": False, "error": str(e)}
        g["_desktop_last_tool_used"] = tool.name
        g["_desktop_last_tool_result"] = str(result)[:300]
        g["_desktop_tool_execution_count"] = int(g.get("_desktop_tool_execution_count", 0) or 0) + 1
        return result

