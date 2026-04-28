"""
Local operator HTTP API for the Ava Control desktop app (Phase 1).

Binds to 127.0.0.1 only. Started from avaagent when AVA_OPERATOR_HTTP != 0.
Does not replace Gradio; complements it with JSON/chat for the Tauri UI.
"""
from __future__ import annotations

from dataclasses import asdict
import json
import os
import threading
import traceback
from pathlib import Path
from typing import Any, Callable, Optional

_HOST: dict[str, Any] | None = None
_CHAT_FN: Optional[Callable[..., dict[str, Any]]] = None
_CHAT_CALL_LOCK = threading.Lock()


def configure_operator_runtime(host: dict[str, Any], chat_fn: Callable[..., dict[str, Any]]) -> None:
    global _HOST, _CHAT_FN
    _HOST = host
    _CHAT_FN = chat_fn


def _g() -> dict[str, Any]:
    if _HOST is None:
        return {}
    return _HOST


def _memory_refinement_summary(perception: Any) -> str:
    """Single-line operator summary from Phase 24 refined memory fields."""
    if perception is None:
        return ""
    parts = [
        str(getattr(perception, "refined_memory_class", "") or ""),
        "worthy" if bool(getattr(perception, "refined_memory_worthy", False)) else "not_worthy",
        f"retrieval_pri={float(getattr(perception, 'refined_memory_retrieval_priority', 0.0) or 0.0):.2f}",
    ]
    meta = getattr(perception, "refined_memory_meta", None)
    if isinstance(meta, dict) and meta.get("summary_line"):
        parts.append(str(meta.get("summary_line"))[:120])
    return " · ".join(parts)[:400]


def _perception_dict(p: Any) -> dict[str, Any]:
    if p is None:
        return {}
    keys = [
        "vision_status",
        "visual_truth_trusted",
        "face_status",
        "recognized_text",
        "scene_compact_summary",
        "scene_overall_state",
        "identity_state",
        "resolved_face_identity",
        "stable_face_identity",
        "quality_label",
        "blur_label",
        "acquisition_freshness",
        "interpretation_primary_event",
        "interpretation_confidence",
        "routing_selected_model",
        "cognitive_mode",
        "routing_fallback_model",
        "routing_reason",
        "routing_confidence",
        "heartbeat_mode",
        "heartbeat_summary",
        "heartbeat_last_reason",
        "voice_turn_state",
        "nuance_tone",
        "runtime_presence_mode",
        "runtime_ready_state",
        "runtime_active_issue_summary",
        "runtime_threads_summary",
        "runtime_maintenance_summary",
        "runtime_learning_summary",
        "runtime_operator_summary",
        "strategic_continuity_summary",
        "active_threads",
        "relationship_carryover",
        "maintenance_carryover",
        "continuity_scope",
        "relationship_summary",
        "unfinished_thread_present",
        "refined_memory_class",
        "refined_memory_worthy",
        "refined_memory_retrieval_priority",
        "workbench_has_proposal",
        "workbench_top_proposal_type",
        "workbench_top_proposal_title",
        "workbench_summary",
        "workbench_execution_ready",
        "workbench_last_execution_success",
        "workbench_last_execution_summary",
        "improvement_loop_active",
        "improvement_loop_stage",
        "improvement_active_issue",
        "improvement_awaiting_approval",
        "active_concern_count",
        "top_active_concern",
        "concern_reconciliation_summary",
        "learning_focus",
        "learning_summary",
        "workbench_selected_proposal_id",
        "workbench_last_rollback_success",
        "improvement_loop_summary",
    ]
    out: dict[str, Any] = {}
    for k in keys:
        try:
            v = getattr(p, k, None)
            if hasattr(v, "tolist"):
                continue
            if isinstance(v, (str, int, float, bool)) or v is None:
                out[k] = v
            elif isinstance(v, (list, dict)):
                try:
                    json.dumps(v, default=str)
                    out[k] = v
                except Exception:
                    out[k] = str(v)[:800]
            else:
                out[k] = str(v)[:1200]
        except Exception:
            continue
    return out


def build_snapshot(host: dict[str, Any]) -> dict[str, Any]:
    ws = host.get("workspace")
    perception = None
    try:
        if ws is not None and getattr(ws, "state", None) is not None:
            perception = ws.state.perception
    except Exception:
        perception = None

    snap_runtime = host.get("_runtime_self_snapshot")
    if not isinstance(snap_runtime, dict):
        snap_runtime = {}

    _gr_port = os.environ.get("AVA_GRADIO_SERVER_PORT", "7860").strip() or "7860"
    _gr_host = os.environ.get("AVA_GRADIO_SERVER_NAME", "127.0.0.1").strip() or "127.0.0.1"
    _op_port = os.environ.get("AVA_OPERATOR_HTTP_PORT", "5876").strip() or "5876"

    ribbon = {
        "heartbeat_mode": str(getattr(perception, "heartbeat_mode", "") or snap_runtime.get("heartbeat_mode") or "")[:64],
        "routing_selected_model": str(getattr(perception, "routing_selected_model", "") or "")[:120],
        "cognitive_mode": str(getattr(perception, "cognitive_mode", "") or "")[:80],
        "vision_status": str(getattr(perception, "vision_status", "") or "")[:64],
        "voice_turn_state": str(getattr(perception, "voice_turn_state", "") or "idle")[:48],
        "presence_mode": str(getattr(perception, "runtime_presence_mode", "") or snap_runtime.get("presence_mode") or "")[:48],
        "active_issue": str(getattr(perception, "runtime_active_issue_summary", "") or snap_runtime.get("active_issue") or "")[:200],
        "threads_short": str(getattr(perception, "runtime_threads_summary", "") or "")[:200],
        "workbench_hint": str(getattr(perception, "workbench_summary", "") or "")[:160],
        "ready_state": str(getattr(perception, "runtime_ready_state", "") or snap_runtime.get("runtime_readiness") or "")[:32],
        "routing_override": str(host.get("_routing_model_override") or "")[:120],
        "concerns_top": str(getattr(perception, "top_active_concern", "") or "")[:120],
        "nuance_tone": str(getattr(perception, "nuance_tone", "") or "")[:120],
        "gradio_url": f"http://{_gr_host}:{_gr_port}/",
        "operator_http_url": f"http://127.0.0.1:{_op_port}/",
    }

    heartbeat_block = {
        "heartbeat_mode": getattr(perception, "heartbeat_mode", "") if perception else "",
        "heartbeat_summary": getattr(perception, "heartbeat_summary", "") if perception else "",
        "heartbeat_last_reason": getattr(perception, "heartbeat_last_reason", "") if perception else "",
        "heartbeat_tick_id": getattr(perception, "heartbeat_tick_id", 0) if perception else 0,
        "heartbeat_meta": dict(getattr(perception, "heartbeat_meta", {}) or {}) if perception else {},
        "runtime_presence_mode": getattr(perception, "runtime_presence_mode", ""),
        "runtime_operator_summary": getattr(perception, "runtime_operator_summary", ""),
        "runtime_presence_meta": dict(getattr(perception, "runtime_presence_meta", {}) or {}) if perception else {},
        "runtime_threads_summary": getattr(perception, "runtime_threads_summary", "") if perception else "",
        "runtime_active_issue_summary": getattr(perception, "runtime_active_issue_summary", "") if perception else "",
        "runtime_maintenance_summary": getattr(perception, "runtime_maintenance_summary", "") if perception else "",
        "runtime_ready_state": getattr(perception, "runtime_ready_state", "") if perception else "",
        "learning_summary": getattr(perception, "learning_summary", ""),
        "learning_focus": getattr(perception, "learning_focus", ""),
        "learning_meta": dict(getattr(perception, "learning_meta", {}) or {}) if perception else {},
        "snapshot_carryover": snap_runtime,
    }

    rm = dict(getattr(perception, "routing_meta", {}) or {}) if perception else {}
    models_block = {
        "selected_model": getattr(perception, "routing_selected_model", ""),
        "cognitive_mode": getattr(perception, "cognitive_mode", ""),
        "fallback_model": getattr(perception, "routing_fallback_model", ""),
        "routing_reason": str(getattr(perception, "routing_reason", "") or "")[:900],
        "routing_confidence": float(getattr(perception, "routing_confidence", 0.0) or 0.0),
        "routing_meta": rm,
        "switch_reason_last": str(rm.get("switch_reason") or rm.get("switch_explain") or "")[:500],
        "no_switch_reason_last": str(rm.get("no_switch_reason") or rm.get("no_switch_explain") or "")[:500],
        "override_model": host.get("_routing_model_override"),
        "override_mode": host.get("_routing_cognitive_mode_override"),
        "last_switch_mono": host.get("_routing_last_switch_monotonic"),
        "host_last_effective_model": host.get("_routing_last_effective_model"),
        "host_last_cognitive_mode": host.get("_routing_last_cognitive_mode"),
    }

    try:
        from brain.model_routing import discover_available_model_tags

        tags, src = discover_available_model_tags(force=False)
        models_block["available_models"] = sorted(tags) if tags else []
        models_block["discovery_source"] = src
    except Exception as e:
        models_block["available_models"] = []
        models_block["discovery_error"] = str(e)[:200]

    vision_block = {
        "perception": _perception_dict(perception),
    }

    memory_block = {
        "strategic_continuity_summary": getattr(perception, "strategic_continuity_summary", ""),
        "active_threads": getattr(perception, "active_threads", []) or [],
        "relationship_carryover": getattr(perception, "relationship_carryover", ""),
        "maintenance_carryover": getattr(perception, "maintenance_carryover", ""),
        "relationship_summary": getattr(perception, "relationship_summary", ""),
        "unfinished_thread_present": bool(getattr(perception, "unfinished_thread_present", False)),
        "refined_memory_class": getattr(perception, "refined_memory_class", ""),
        "refined_memory_retrieval_priority": getattr(perception, "refined_memory_retrieval_priority", 0.0),
        "memory_refinement_summary": _memory_refinement_summary(perception),
        "live_context": host.get("_live_context_snapshot") if isinstance(host.get("_live_context_snapshot"), dict) else {},
    }

    wb_block = {
        "workbench_has_proposal": bool(getattr(perception, "workbench_has_proposal", False)),
        "workbench_top_proposal_type": getattr(perception, "workbench_top_proposal_type", ""),
        "workbench_top_proposal_title": getattr(perception, "workbench_top_proposal_title", ""),
        "workbench_summary": getattr(perception, "workbench_summary", ""),
        "workbench_execution_ready": getattr(perception, "workbench_execution_ready", False),
        "workbench_last_execution_success": getattr(perception, "workbench_last_execution_success", False),
        "workbench_last_execution_summary": getattr(perception, "workbench_last_execution_summary", ""),
        "workbench_meta": dict(getattr(perception, "workbench_meta", {}) or {}) if perception else {},
        "last_execution_global": str(host.get("_last_workbench_execution_result"))[:1200]
        if host.get("_last_workbench_execution_result") is not None
        else "",
        "last_command_global": str(host.get("_last_workbench_command_result"))[:1200]
        if host.get("_last_workbench_command_result") is not None
        else "",
    }
    idx_fn = host.get("format_workbench_index")
    if callable(idx_fn):
        try:
            wb_block["workbench_index_text"] = str(idx_fn(limit=48))[:8000]
        except Exception as e:
            wb_block["workbench_index_text"] = ""
            wb_block["workbench_index_error"] = str(e)[:200]
    else:
        wb_block["workbench_index_text"] = ""

    loop_block = {
        "improvement_loop_active": bool(getattr(perception, "improvement_loop_active", False)),
        "improvement_loop_stage": getattr(perception, "improvement_loop_stage", ""),
        "improvement_active_issue": getattr(perception, "improvement_active_issue", ""),
        "improvement_awaiting_approval": bool(getattr(perception, "improvement_awaiting_approval", False)),
        "improvement_loop_meta": dict(getattr(perception, "improvement_loop_meta", {}) or {}) if perception else {},
    }

    concerns_block = {
        "active_concern_count": int(getattr(perception, "active_concern_count", 0) or 0),
        "top_active_concern": getattr(perception, "top_active_concern", ""),
        "concern_reconciliation_summary": getattr(perception, "concern_reconciliation_summary", ""),
        "concern_reconciliation_meta": dict(getattr(perception, "concern_reconciliation_meta", {}) or {})
        if perception
        else {},
    }

    tools_block = {
        "last_tool_used": str(host.get("_desktop_last_tool_used") or ""),
        "last_tool_result": str(host.get("_desktop_last_tool_result") or "")[:200],
        "tool_execution_count": int(host.get("_desktop_tool_execution_count", 0) or 0),
        "pending_tier2_proposals": len(list(host.get("_desktop_tier2_pending") or [])),
    }

    inner_life = {
        "current_thought": "",
        "current_curiosity": None,
        "self_summary": "",
        "opinion_count": 0,
        "monologue_thought_count": 0,
    }
    try:
        from brain.inner_monologue import current_thought, thought_count
        from brain.curiosity_topics import get_current_curiosity
        from brain.self_model import get_self_summary
        from brain.opinions import opinion_count

        base_dir = Path(host.get("BASE_DIR") or Path.cwd())
        inner_life["current_thought"] = current_thought(base_dir) or ""
        inner_life["current_curiosity"] = get_current_curiosity(host)
        inner_life["self_summary"] = get_self_summary(host)
        inner_life["opinion_count"] = int(opinion_count(host))
        inner_life["monologue_thought_count"] = int(thought_count(base_dir))
    except Exception:
        pass

    debug_human = {
        "ribbon": ribbon,
        "heartbeat": heartbeat_block,
        "models": models_block,
        "vision": vision_block,
        "memory": memory_block,
        "workbench": wb_block,
        "improvement_loop": loop_block,
        "concerns": concerns_block,
        "tools": tools_block,
        "inner_life": inner_life,
        "reply_path": host.get("reply_path_meta") if isinstance(host.get("reply_path_meta"), dict) else {},
    }

    return {
        "ribbon": ribbon,
        "heartbeat_runtime": heartbeat_block,
        "models": models_block,
        "vision": vision_block,
        "memory_continuity": memory_block,
        "workbench": wb_block,
        "improvement_loop": loop_block,
        "concerns": concerns_block,
        "tools": tools_block,
        "inner_life": inner_life,
        "debug": debug_human,
        "ts": __import__("time").time(),
    }


def build_debug_export(host: dict[str, Any]) -> str:
    snap = build_snapshot(host)
    rb = snap.get("ribbon") or {}
    hb = snap.get("heartbeat_runtime") or {}
    mb = snap.get("models") or {}
    wb = snap.get("workbench") or {}
    lp = snap.get("improvement_loop") or {}
    cc = snap.get("concerns") or {}
    mem = snap.get("memory_continuity") or {}
    lines: list[str] = []
    lines.append("=== Ava operator debug export (AI handoff) ===")
    lines.append("")
    lines.append("## Ribbon / live summary")
    for k in sorted(rb.keys()):
        lines.append(f"- {k}: {rb[k]}")
    lines.append("")
    lines.append("## Heartbeat / runtime presence")
    lines.append(f"- heartbeat_mode: {hb.get('heartbeat_mode')}")
    lines.append(f"- heartbeat_last_reason: {hb.get('heartbeat_last_reason')}")
    lines.append(f"- heartbeat_summary: {hb.get('heartbeat_summary')}")
    lines.append(f"- runtime_presence_mode: {hb.get('runtime_presence_mode')}")
    lines.append(f"- runtime_operator_summary: {hb.get('runtime_operator_summary')}")
    lines.append(f"- runtime_active_issue_summary: {hb.get('runtime_active_issue_summary')}")
    lines.append(f"- runtime_threads_summary: {hb.get('runtime_threads_summary')}")
    lines.append(f"- runtime_maintenance_summary: {hb.get('runtime_maintenance_summary')}")
    lines.append(f"- learning_focus: {hb.get('learning_focus')}")
    lines.append(f"- learning_summary: {hb.get('learning_summary')}")
    sc = hb.get("snapshot_carryover") if isinstance(hb.get("snapshot_carryover"), dict) else {}
    if sc:
        lines.append("- snapshot_carryover:")
        lines.append(json.dumps(sc, indent=2, default=str)[:4000])
    lines.append("")
    lines.append("## Model routing")
    lines.append(f"- selected_model: {mb.get('selected_model')}")
    lines.append(f"- cognitive_mode: {mb.get('cognitive_mode')}")
    lines.append(f"- fallback_model: {mb.get('fallback_model')}")
    lines.append(f"- routing_reason: {mb.get('routing_reason')}")
    lines.append(f"- override_model: {mb.get('override_model')}")
    lines.append(f"- override_mode: {mb.get('override_mode')}")
    lines.append(f"- switch_reason_last: {mb.get('switch_reason_last')}")
    lines.append(f"- no_switch_reason_last: {mb.get('no_switch_reason_last')}")
    lines.append(f"- available_models: {mb.get('available_models')}")
    lines.append("")
    lines.append("## Strategic continuity / memory")
    lines.append(f"- strategic_continuity_summary: {mem.get('strategic_continuity_summary')}")
    lines.append(f"- relationship_carryover: {mem.get('relationship_carryover')}")
    lines.append(f"- unfinished_thread_present: {mem.get('unfinished_thread_present')}")
    lines.append(f"- refined_memory_class: {mem.get('refined_memory_class')}")
    lines.append(f"- memory_refinement_summary: {mem.get('memory_refinement_summary')}")
    lc = mem.get("live_context") if isinstance(mem.get("live_context"), dict) else {}
    if lc:
        lines.append("- live_context:")
        lines.append(json.dumps(lc, indent=2, default=str)[:3500])
    lines.append("")
    lines.append("## Workbench")
    lines.append(f"- workbench_summary: {wb.get('workbench_summary')}")
    lines.append(f"- workbench_has_proposal: {wb.get('workbench_has_proposal')}")
    lines.append(f"- workbench_execution_ready: {wb.get('workbench_execution_ready')}")
    lines.append(f"- workbench_last_execution_summary: {wb.get('workbench_last_execution_summary')}")
    lines.append("")
    lines.append("## Self-improvement loop")
    lines.append(f"- improvement_loop_active: {lp.get('improvement_loop_active')}")
    lines.append(f"- improvement_loop_stage: {lp.get('improvement_loop_stage')}")
    lines.append(f"- improvement_active_issue: {lp.get('improvement_active_issue')}")
    lines.append(f"- improvement_awaiting_approval: {lp.get('improvement_awaiting_approval')}")
    lines.append("")
    lines.append("## Concerns / diagnostics")
    lines.append(f"- active_concern_count: {cc.get('active_concern_count')}")
    lines.append(f"- top_active_concern: {cc.get('top_active_concern')}")
    lines.append(f"- concern_reconciliation_summary: {cc.get('concern_reconciliation_summary')}")
    lines.append("")
    rp = host.get("reply_path_meta") if isinstance(host.get("reply_path_meta"), dict) else {}
    if rp:
        lines.append("## Reply path (compact)")
        lines.append(json.dumps(rp, indent=2, default=str)[:4500])
        lines.append("")
    rs = host.get("_runtime_self_snapshot") if isinstance(host.get("_runtime_self_snapshot"), dict) else {}
    if rs:
        lines.append("## Runtime self snapshot (warm)")
        lines.append(json.dumps(rs, indent=2, default=str)[:3500])
        lines.append("")
    sr = host.get("_startup_resume_snapshot")
    if sr is not None:
        lines.append("## Startup resume (brief)")
        try:
            from dataclasses import asdict, is_dataclass

            if is_dataclass(sr):
                blob = asdict(sr)
            elif isinstance(sr, dict):
                blob = sr
            else:
                blob = {"value": repr(sr)}
            lines.append(json.dumps(blob, indent=2, default=str)[:2000])
        except Exception:
            lines.append(str(sr)[:2000])
        lines.append("")
    wbx = wb.get("workbench_index_text") if isinstance(wb.get("workbench_index_text"), str) else ""
    if wbx:
        lines.append("## Workbench index (preview)")
        lines.append(wbx[:6000])
        lines.append("")
    lines.append("## Full snapshot JSON (truncated)")
    lines.append(json.dumps(snap, indent=2, default=str)[:42000])
    lines.append("")
    lines.append("=== End ===")
    return "\n".join(lines)


def _read_identity_file(host: dict[str, Any], name: str) -> tuple[str, str]:
    base = Path(host.get("BASE_DIR") or Path.cwd())
    safe = {"IDENTITY": base / "ava_core" / "IDENTITY.md", "SOUL": base / "ava_core" / "SOUL.md", "USER": base / "ava_core" / "USER.md"}
    path = safe.get(name.upper())
    if path is None or not path.is_file():
        return "", f"missing:{name}"
    try:
        return path.read_text(encoding="utf-8", errors="replace"), str(path)
    except Exception as e:
        return "", str(e)


def _build_workbench_result_from_host(host: dict[str, Any]):
    """
    Build a WorkbenchProposalResult from current PerceptionState snapshot fields.
    Uses existing Phase 16.6 command layer without mutating proposal generation code.
    """
    try:
        from brain.perception_types import RepairProposal, WorkbenchProposalResult
    except Exception:
        return None

    ws = host.get("workspace")
    perception = None
    try:
        if ws is not None and getattr(ws, "state", None) is not None:
            perception = ws.state.perception
    except Exception:
        perception = None
    if perception is None:
        return WorkbenchProposalResult()

    wb_meta = dict(getattr(perception, "workbench_meta", {}) or {})
    raw_props = wb_meta.get("proposals") if isinstance(wb_meta.get("proposals"), list) else []
    proposals: list[RepairProposal] = []
    for rp in raw_props[:24]:
        if not isinstance(rp, dict):
            continue
        proposals.append(
            RepairProposal(
                proposal_id=str(rp.get("proposal_id") or ""),
                proposal_type=str(rp.get("proposal_type") or "no_action_needed"),
                title=str(rp.get("title") or ""),
                risk_level=str(rp.get("risk_level") or "low"),
                priority=str(rp.get("priority") or "low"),
                confidence=float(rp.get("confidence") or 0.0),
                requires_human_review=bool(rp.get("requires_human_review", True)),
            )
        )

    top: RepairProposal
    if proposals:
        top = proposals[0]
        selected = str(getattr(perception, "workbench_selected_proposal_id", "") or "")
        if selected:
            for p in proposals:
                if p.proposal_id == selected:
                    top = p
                    break
    else:
        top = RepairProposal(
            proposal_id="",
            proposal_type=str(getattr(perception, "workbench_top_proposal_type", "") or "no_action_needed"),
            title=str(getattr(perception, "workbench_top_proposal_title", "") or ""),
            confidence=float(wb_meta.get("top_confidence") or 0.0),
            requires_human_review=bool(wb_meta.get("top_requires_human_review", True)),
            recommended_action=str(wb_meta.get("top_recommended_action") or ""),
            problem_detected=str(wb_meta.get("top_problem") or ""),
        )
    return WorkbenchProposalResult(
        has_proposal=bool(getattr(perception, "workbench_has_proposal", False)),
        top_proposal=top,
        proposals=proposals,
        summary=str(getattr(perception, "workbench_summary", "") or ""),
        meta={"source": "operator_http_perception_meta"},
    )


def create_app():
    from fastapi import Body, FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import FileResponse, PlainTextResponse
    from pydantic import BaseModel

    app = FastAPI(title="Ava Operator API", version="0.1")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://127.0.0.1:5173",
            "http://localhost:5173",
            "tauri://localhost",
            "http://tauri.localhost",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    class OpChatIn(BaseModel):
        message: str = ""

    class RoutingOverrideIn(BaseModel):
        model: str | None = None
        cognitive_mode: str | None = None

    class WorkbenchActionIn(BaseModel):
        proposal_id: str | None = None
        reason: str | None = None
        elevated_approval: bool = False

    @app.get("/api/v1/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "ava-operator"}

    @app.get("/api/v1/snapshot")
    def snapshot() -> dict[str, Any]:
        return build_snapshot(_g())

    def _normalize_chat_payload(raw: Any) -> dict[str, Any]:
        """Ensure clients always see reply text under ``reply`` and a source hint."""
        if isinstance(raw, str):
            text = raw.strip()
            return {
                "ok": True,
                "reply": text,
                "message": text,
                "debug_reply_source": "raw_string" if text else "empty",
            }
        if isinstance(raw, dict):
            out = dict(raw)
            text = ""
            source = "empty"

            for key in ("reply", "assistant_reply", "message", "text"):
                val = out.get(key)
                if isinstance(val, str) and val.strip() and not (key == "message" and out.get("empty_message")):
                    text = val.strip()
                    source = key
                    break

            if not text:
                best_key = ""
                best_val = ""
                for k, v in out.items():
                    if isinstance(v, str):
                        vv = v.strip()
                        if len(vv) > 10 and len(vv) > len(best_val):
                            best_key = str(k)
                            best_val = vv
                if best_val:
                    text = best_val
                    source = f"scanned:{best_key}"

            out["reply"] = text
            out["message"] = text
            out["debug_reply_source"] = source
            out.setdefault("ok", True)
            return out
        return {
            "ok": False,
            "error": "unexpected_chat_response_type",
            "reply": "",
            "message": "",
            "debug_reply_source": "empty",
        }

    @app.post("/api/v1/chat")
    async def operator_chat(body: dict[str, Any] = Body(default_factory=dict)) -> dict[str, Any]:
        if _CHAT_FN is None:
            return {"ok": False, "error": "chat_not_configured", "reply": "", "debug_reply_source": "empty"}
        try:
            message = ""
            if isinstance(body, dict):
                message = str(body.get("message") or "")
            # Keep operator chat in the same server thread with a lock to avoid racey global-state turns.
            with _CHAT_CALL_LOCK:
                raw = _CHAT_FN(message)
            try:
                print(f"[operator_http] /api/v1/chat raw_return_type={type(raw).__name__} raw_return={repr(raw)[:2000]}")
            except Exception:
                pass
            return _normalize_chat_payload(raw)
        except Exception as e:
            return {
                "ok": False,
                "error": str(e),
                "trace": traceback.format_exc()[:1200],
                "reply": "",
                "debug_reply_source": "empty",
            }

    @app.post("/api/v1/routing/override")
    def routing_override(body: RoutingOverrideIn) -> dict[str, Any]:
        h = _g()
        if body.model is None or (isinstance(body.model, str) and not body.model.strip()):
            h.pop("_routing_model_override", None)
            cleared_model = True
        else:
            h["_routing_model_override"] = str(body.model).strip()[:160]
            cleared_model = False
        if body.cognitive_mode is None or not str(body.cognitive_mode).strip():
            h.pop("_routing_cognitive_mode_override", None)
            cleared_mode = True
        else:
            h["_routing_cognitive_mode_override"] = str(body.cognitive_mode).strip()[:80]
            cleared_mode = False
        return {
            "ok": True,
            "override_model": h.get("_routing_model_override"),
            "override_cognitive_mode": h.get("_routing_cognitive_mode_override"),
            "cleared_model": cleared_model,
            "cleared_mode": cleared_mode,
        }

    @app.get("/api/v1/identity/{which}")
    def identity(which: str) -> PlainTextResponse:
        text, err = _read_identity_file(_g(), which)
        if not text:
            return PlainTextResponse(f"(unavailable: {err})", status_code=404)
        return PlainTextResponse(text)

    @app.get("/api/v1/debug/export", response_class=PlainTextResponse)
    def debug_export() -> str:
        return build_debug_export(_g())

    @app.get("/api/v1/vision/latest_frame")
    def vision_latest_frame():
        h = _g()
        p = h.get("CAMERA_LATEST_ANNOTATED_PATH")
        if p is None:
            return PlainTextResponse("camera path unavailable", status_code=404)
        path = Path(p)
        if not path.is_file():
            return PlainTextResponse("no annotated frame yet", status_code=404)
        return FileResponse(str(path), media_type="image/jpeg")

    @app.get("/api/v1/chat/history")
    def chat_history() -> dict[str, Any]:
        h = _g()
        hist_fn = h.get("_get_canonical_history") or h.get("get_canonical_history")
        if callable(hist_fn):
            try:
                rows = list(hist_fn())
                return {"ok": True, "messages": rows[-200:]}
            except Exception as e:
                return {"ok": False, "error": str(e)}
        return {"ok": False, "error": "no_history_fn", "messages": []}

    @app.post("/api/v1/workbench/approve")
    def workbench_approve(body: WorkbenchActionIn) -> dict[str, Any]:
        """
        Operator approve path using existing Phase 16.6 command handling.
        Defaults to approve/apply for current selected/top proposal.
        """
        h = _g()
        wb_result = _build_workbench_result_from_host(h)
        try:
            from brain.perception_types import WorkbenchCommandRequest
            from brain.workbench_commands import handle_workbench_command

            req = WorkbenchCommandRequest(
                command_name="approve_proposal_apply",
                proposal_id=str(body.proposal_id or ""),
                approved=True,
                elevated_approval=bool(body.elevated_approval),
                requested_by="operator_http",
                notes=[str(body.reason or "").strip()] if body.reason else [],
                meta={"source": "operator_http"},
            )
            res = handle_workbench_command(req, proposal_result=wb_result)
            asd = asdict(res)
            h["_last_workbench_command_result"] = asd
            if res.execution_result is not None:
                h["_last_workbench_execution_result"] = asdict(res.execution_result)
            return {
                "ok": bool(res.success),
                "message": str(res.summary or "workbench approve processed"),
                "result": asd,
            }
        except Exception as e:
            return {
                "ok": False,
                "message": f"workbench approve failed: {e}",
                "trace": traceback.format_exc()[:1400],
            }

    @app.post("/api/v1/workbench/reject")
    def workbench_reject(body: WorkbenchActionIn) -> dict[str, Any]:
        """
        Operator reject path (explicit no-execution decision for current proposal).
        This records command intent in existing runtime command result slots.
        """
        h = _g()
        wb_result = _build_workbench_result_from_host(h)
        proposal_id = str(body.proposal_id or "")
        available: list[str] = []
        try:
            if wb_result is not None:
                available = [str(p.proposal_id or "") for p in list(wb_result.proposals or []) if str(p.proposal_id or "")]
        except Exception:
            available = []
        if not proposal_id and wb_result is not None and getattr(wb_result.top_proposal, "proposal_id", ""):
            proposal_id = str(wb_result.top_proposal.proposal_id or "")
        if proposal_id and available and proposal_id not in available:
            return {
                "ok": False,
                "message": f"proposal_id not found in current proposal set: {proposal_id}",
                "available_proposals": available[:20],
            }
        reason = str(body.reason or "").strip() or "rejected_by_operator"
        cmd_result = {
            "command_name": "reject_proposal",
            "proposal_id": proposal_id,
            "success": True,
            "summary": f"Rejected proposal `{proposal_id or '-none-'}` ({reason}).",
            "blocked_reason": "",
            "meta": {"source": "operator_http", "reason": reason},
        }
        h["_last_workbench_command_result"] = cmd_result
        return {
            "ok": True,
            "message": cmd_result["summary"],
            "result": cmd_result,
        }

    return app


def start_operator_http_background(host: dict[str, Any], chat_fn: Callable[..., dict[str, Any]]) -> None:
    configure_operator_runtime(host, chat_fn)
    if os.environ.get("AVA_OPERATOR_HTTP", "1").strip() in ("0", "false", "False"):
        print("[operator_http] disabled (AVA_OPERATOR_HTTP=0)")
        return
    port = int(os.environ.get("AVA_OPERATOR_HTTP_PORT", "5876") or "5876")
    host_bind = os.environ.get("AVA_OPERATOR_HTTP_HOST", "127.0.0.1") or "127.0.0.1"

    app = create_app()

    def _run() -> None:
        try:
            import uvicorn

            uvicorn.run(app, host=host_bind, port=port, log_level="warning")
        except Exception as e:
            print(f"[operator_http] server failed: {e}\n{traceback.format_exc()}")

    t = threading.Thread(target=_run, name="ava-operator-http", daemon=True)
    t.start()
    print(f"[operator_http] listening on http://{host_bind}:{port} (Gradio UI may still be on :7860)")
