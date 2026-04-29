"""
Phase 31 — Resident heartbeat: lightweight background continuity between perception ticks.

Runs inside ``run_perception_pipeline`` (no separate OS thread). Uses wall-clock cadence,
event triggers, and persisted :class:`~brain.perception_types.HeartbeatState` — **does not**
rewrite safety rules, approve workbench actions, or mutate ``ava_core`` identity files.

Identity anchors (IDENTITY.md / SOUL.md / USER.md) remain **read-only** here; learning may only
surface **suggestions** subordinate to those anchors elsewhere.
"""
from __future__ import annotations

import hashlib
import json
import time
import traceback
from pathlib import Path
from typing import Any, Optional

from .model_routing import FALLBACK_SAFE_MODE
from .perception_types import (
    CuriosityResult,
    HeartbeatCarryoverState,
    HeartbeatEvent,
    HeartbeatMode,
    HeartbeatState,
    HeartbeatTickResult,
    ImprovementLoopResult,
    MemoryRefinementResult,
    ModelRoutingResult,
    OutcomeLearningResult,
    SelfTestRunResult,
    SocialContinuityResult,
    StrategicContinuityResult,
    WorkbenchProposalResult,
)
from .shared import now_ts

_BASE = Path(__file__).resolve().parent.parent
HEARTBEAT_DIR = _BASE / "state" / "heartbeat"
HEARTBEAT_STATE_PATH = HEARTBEAT_DIR / "heartbeat_state.json"

# Seconds between **rich** heartbeat evaluations (mode-dependent); cheap ticks always advance tick_id.
_GAP_IDLE = 55.0
_GAP_ACTIVE = 14.0
_GAP_CONVERSATION = 7.0
_GAP_MAINTENANCE = 18.0
_GAP_LEARNING_REVIEW = 280.0
_GAP_QUIET_RECOVERY = 65.0
_GAP_NO_HEARTBEAT = 99999.0

_SAVE_EVERY_N_TICKS = 6


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def _trunc(s: str, n: int = 220) -> str:
    t = " ".join((s or "").split())
    if len(t) <= n:
        return t
    return t[: n - 1].rstrip() + "…"


def _digest(s: str) -> str:
    return hashlib.sha256((s or "").encode("utf-8", errors="ignore")).hexdigest()[:16]


def _ensure_dir() -> None:
    HEARTBEAT_DIR.mkdir(parents=True, exist_ok=True)


def load_heartbeat_state() -> HeartbeatState:
    _ensure_dir()
    if not HEARTBEAT_STATE_PATH.is_file():
        return HeartbeatState()
    try:
        with open(HEARTBEAT_STATE_PATH, "r", encoding="utf-8") as f:
            raw = json.load(f)
        if not isinstance(raw, dict):
            return HeartbeatState()
        return HeartbeatState(
            tick_id=int(raw.get("tick_id") or 0),
            last_wallclock=float(raw.get("last_wallclock") or 0.0),
            last_rich_learning_ts=float(raw.get("last_rich_learning_ts") or 0.0),
            last_digest=str(raw.get("last_digest") or ""),
            silence_streak=int(raw.get("silence_streak") or 0),
            last_emit_sig=str(raw.get("last_emit_sig") or ""),
            meta=dict(raw.get("meta") or {}),
        )
    except Exception:
        return HeartbeatState()


def save_heartbeat_state(st: HeartbeatState) -> None:
    _ensure_dir()
    try:
        payload = {
            "tick_id": int(st.tick_id),
            "last_wallclock": float(st.last_wallclock),
            "last_rich_learning_ts": float(st.last_rich_learning_ts),
            "last_digest": str(st.last_digest),
            "silence_streak": int(st.silence_streak),
            "last_emit_sig": str(st.last_emit_sig),
            "meta": dict(st.meta),
        }
        tmp = HEARTBEAT_STATE_PATH.with_suffix(".json.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        tmp.replace(HEARTBEAT_STATE_PATH)
    except Exception as e:
        print(f"[heartbeat] save failed: {e}")


def bootstrap_heartbeat_runtime(g: dict[str, Any]) -> None:
    """
    Quiet startup: ensure dirs, load carryover into runtime dict for continuity hooks.
    Does not schedule timers or spam logs.
    """
    if not isinstance(g, dict):
        return
    _ensure_dir()
    st = load_heartbeat_state()
    g["_heartbeat_boot_tick_id"] = int(st.tick_id)
    g["_heartbeat_boot_ts"] = now_ts()
    # Single concise line — not repeated.
    if not g.get("_heartbeat_boot_logged"):
        print(
            f"[heartbeat] carryover tick_id={st.tick_id} mode=idle_monitoring "
            f"(quiet background continuity enabled)"
        )
        g["_heartbeat_boot_logged"] = True


def _workbench_runtime_digest(g: dict[str, Any]) -> str:
    return _digest(
        f"{str(g.get('_last_workbench_execution_result'))[:800]}"
        f"|{str(g.get('_last_workbench_command_result'))[:800]}"
        f"|{str(g.get('_workbench_operator_approved_proposal_id') or '')}"
    )


def _update_route_fallback_streak(st: HeartbeatState, route: Optional[ModelRoutingResult]) -> int:
    if route is None:
        return int(st.meta.get("route_fallback_streak", 0) or 0)
    mode = str(getattr(route, "cognitive_mode", "") or "").strip()
    if mode and mode != FALLBACK_SAFE_MODE:
        st.meta["route_fallback_streak"] = 0
        return 0
    sel = (str(getattr(route, "selected_model", "") or "")).strip()
    fb = (str(getattr(route, "fallback_model", "") or "")).strip()
    cont = bool(getattr(route, "continuity_preserved", True))
    streak = int(st.meta.get("route_fallback_streak", 0) or 0)
    using_fallback = bool(fb and sel and sel == fb)
    if using_fallback or not cont:
        streak += 1
    else:
        streak = 0
    st.meta["route_fallback_streak"] = streak
    return streak


def _voice_snapshot(g: dict[str, Any]) -> tuple[str, bool, bool, str]:
    vc = g.get("_voice_conversation")
    if vc is None:
        return "idle", False, False, ""
    ts = str(getattr(vc, "turn_state", "idle") or "idle")
    usr = bool(getattr(vc, "user_speaking", False))
    ast = bool(getattr(vc, "assistant_speaking", False))
    intr = str(getattr(vc, "interruption_reason", "") or "")
    return ts, usr, ast, intr


def _gap_for_mode(mode: str) -> float:
    if mode == HeartbeatMode.NO_HEARTBEAT:
        return _GAP_NO_HEARTBEAT
    if mode == HeartbeatMode.CONVERSATION_ACTIVE:
        return _GAP_CONVERSATION
    if mode == HeartbeatMode.MAINTENANCE_WATCH:
        return _GAP_MAINTENANCE
    if mode == HeartbeatMode.LEARNING_REVIEW:
        return _GAP_LEARNING_REVIEW
    if mode == HeartbeatMode.QUIET_RECOVERY:
        return _GAP_QUIET_RECOVERY
    if mode == HeartbeatMode.ACTIVE_PRESENCE:
        return _GAP_ACTIVE
    return _GAP_IDLE


def _select_mode(
    *,
    g: dict[str, Any],
    user_text: str,
    selftests: Optional[SelfTestRunResult],
    workbench: Optional[WorkbenchProposalResult],
    strategic_continuity: Optional[StrategicContinuityResult],
    curiosity: Optional[CuriosityResult],
    improvement_loop: Optional[ImprovementLoopResult],
    social_continuity: Optional[SocialContinuityResult],
    outcome_learning: Optional[OutcomeLearningResult],
    memory_refinement: Optional[MemoryRefinementResult],
    route_fallback_streak: int,
) -> tuple[str, list[HeartbeatEvent], float]:
    events: list[HeartbeatEvent] = []
    urgency = 0.0
    ut = (user_text or "").strip()

    v_turn, v_user, v_ast, v_intr = _voice_snapshot(g)
    if v_user or (v_intr and len(v_intr) > 2):
        events.append(
            HeartbeatEvent(kind="voice", detail=f"turn={v_turn} interrupt_hint={v_intr[:80]}", significance=0.62)
        )
        return HeartbeatMode.CONVERSATION_ACTIVE, events, 0.72

    if bool(g.get("_voice_user_turn_priority")):
        events.append(HeartbeatEvent(kind="voice_floor", detail="user_turn_priority", significance=0.55))
        return HeartbeatMode.CONVERSATION_ACTIVE, events, 0.65

    st_sum = selftests.summary if selftests is not None else None
    overall = str(st_sum.overall_status or "ok") if st_sum else "ok"
    if overall != "ok":
        events.append(HeartbeatEvent(kind="selftests", detail=f"overall={overall}", significance=0.7))
        urgency = max(urgency, 0.66)

    if workbench is not None and bool(workbench.has_proposal):
        events.append(
            HeartbeatEvent(
                kind="workbench",
                detail=str(workbench.top_proposal.proposal_type or "proposal")[:120],
                significance=0.64,
            )
        )
        urgency = max(urgency, 0.6)

    ilp = improvement_loop
    if ilp is not None and bool(ilp.loop_active):
        events.append(
            HeartbeatEvent(kind="improvement_loop", detail=str(ilp.loop_stage or "")[:120], significance=0.58)
        )
        return HeartbeatMode.MAINTENANCE_WATCH, events, max(urgency, 0.62)

    if overall != "ok" or (workbench is not None and workbench.has_proposal):
        return HeartbeatMode.MAINTENANCE_WATCH, events, max(urgency, 0.58)

    soc = social_continuity
    if soc is not None:
        if bool(getattr(soc, "unfinished_thread_present", False)):
            events.append(
                HeartbeatEvent(kind="unfinished_thread_social", detail="open_thread_signal", significance=0.48)
            )
            urgency = max(urgency, 0.42)
        if float(getattr(soc, "quiet_preference_signal", 0.5) or 0.5) >= 0.66:
            events.append(
                HeartbeatEvent(kind="quiet_preference", detail="elevated_quiet_signal", significance=0.42)
            )
            if ut == "":
                return HeartbeatMode.QUIET_RECOVERY, events, 0.38

    mref = memory_refinement
    if mref is not None and bool(getattr(mref.decision, "unfinished_thread_candidate", False)):
        events.append(
            HeartbeatEvent(kind="memory_unfinished_thread", detail="refinement_candidate", significance=0.5)
        )
        urgency = max(urgency, 0.44)

    if route_fallback_streak >= 2:
        events.append(
            HeartbeatEvent(
                kind="routing_recurrence",
                detail=f"fallback_streak={route_fallback_streak}",
                significance=_clamp01(0.34 + 0.08 * min(route_fallback_streak, 8)),
            )
        )
        urgency = max(urgency, 0.48)

    sc = strategic_continuity
    if sc is not None:
        for th in list(sc.active_threads or [])[:3]:
            rel = float(getattr(th, "relevance", 0.0) or 0.0)
            if rel >= 0.72:
                cat = str(getattr(th, "category", "") or "")
                summ = str(getattr(th, "summary", "") or "")
                events.append(
                    HeartbeatEvent(
                        kind="strategic_carryover",
                        detail=_trunc(summ or cat, 140),
                        significance=float(_clamp01(rel)),
                    )
                )
                urgency = max(urgency, rel)

    cq = curiosity
    if cq is not None and bool(cq.curiosity_triggered) and float(cq.curiosity_confidence or 0) >= 0.55:
        events.append(
            HeartbeatEvent(
                kind="curiosity",
                detail=str(cq.curiosity_theme or "")[:100],
                significance=float(_clamp01(cq.curiosity_confidence)),
            )
        )
        urgency = max(urgency, 0.45)

    ol = outcome_learning
    if ol is not None and str(ol.outcome_category or "") not in ("", "no_adjustment_needed"):
        if bool(ol.repeated_outcome_pattern):
            events.append(
                HeartbeatEvent(
                    kind="outcome_pattern",
                    detail=str(ol.adjustment_target or "")[:100],
                    significance=float(_clamp01(ol.adjustment_confidence)),
                )
            )
            urgency = max(urgency, 0.44)

    if ut:
        return HeartbeatMode.ACTIVE_PRESENCE, events, max(urgency, 0.48)

    return HeartbeatMode.IDLE_MONITORING, events, urgency


def run_heartbeat_tick_safe(
    *,
    g: dict[str, Any] | None,
    user_text: str,
    selftests: Optional[SelfTestRunResult],
    workbench: Optional[WorkbenchProposalResult],
    strategic_continuity: Optional[StrategicContinuityResult],
    curiosity: Optional[CuriosityResult],
    outcome_learning: Optional[OutcomeLearningResult],
    improvement_loop: Optional[ImprovementLoopResult],
    social_continuity: Optional[SocialContinuityResult],
    model_routing: Optional[ModelRoutingResult] = None,
    memory_refinement: Optional[MemoryRefinementResult] = None,
) -> HeartbeatTickResult:
    try:
        return _run_heartbeat_tick(
            g=g if isinstance(g, dict) else {},
            user_text=user_text or "",
            selftests=selftests,
            workbench=workbench,
            strategic_continuity=strategic_continuity,
            curiosity=curiosity,
            outcome_learning=outcome_learning,
            improvement_loop=improvement_loop,
            social_continuity=social_continuity,
            model_routing=model_routing,
            memory_refinement=memory_refinement,
        )
    except Exception as e:
        print(f"[heartbeat] tick failed: {e}\n{traceback.format_exc()}")
        return HeartbeatTickResult(
            heartbeat_active=False,
            heartbeat_mode=HeartbeatMode.NO_HEARTBEAT,
            tick_reason="error",
            notes=[_trunc(str(e), 160)],
            meta={"error": True},
        )


def _run_heartbeat_tick(
    *,
    g: dict[str, Any],
    user_text: str,
    selftests: Optional[SelfTestRunResult],
    workbench: Optional[WorkbenchProposalResult],
    strategic_continuity: Optional[StrategicContinuityResult],
    curiosity: Optional[CuriosityResult],
    outcome_learning: Optional[OutcomeLearningResult],
    improvement_loop: Optional[ImprovementLoopResult],
    social_continuity: Optional[SocialContinuityResult],
    model_routing: Optional[ModelRoutingResult],
    memory_refinement: Optional[MemoryRefinementResult],
) -> HeartbeatTickResult:
    if g.get("_heartbeat_disabled"):
        return HeartbeatTickResult(
            heartbeat_active=False,
            heartbeat_mode=HeartbeatMode.NO_HEARTBEAT,
            tick_reason="disabled",
            should_remain_silent=True,
            heartbeat_summary="Heartbeat disabled via runtime flag.",
            meta={"disabled": True},
        )

    st = load_heartbeat_state()
    now = time.time()
    st.tick_id += 1

    route_streak = _update_route_fallback_streak(st, model_routing)

    force = bool(g.get("_heartbeat_force_tick"))
    event_hint = str(g.pop("_heartbeat_event_reason", "") or "").strip()

    mode, events, urg = _select_mode(
        g=g,
        user_text=user_text,
        selftests=selftests,
        workbench=workbench,
        strategic_continuity=strategic_continuity,
        curiosity=curiosity,
        improvement_loop=improvement_loop,
        social_continuity=social_continuity,
        outcome_learning=outcome_learning,
        memory_refinement=memory_refinement,
        route_fallback_streak=route_streak,
    )

    # Scheduled learning-review mode when not conversing / not maintenance
    lr_last = float(st.meta.get("last_learning_review_wall", 0) or 0)
    if (
        mode
        not in (
            HeartbeatMode.CONVERSATION_ACTIVE,
            HeartbeatMode.MAINTENANCE_WATCH,
        )
        and mode
        in (
            HeartbeatMode.IDLE_MONITORING,
            HeartbeatMode.ACTIVE_PRESENCE,
            HeartbeatMode.QUIET_RECOVERY,
        )
        and (now - lr_last) >= _GAP_LEARNING_REVIEW
    ):
        mode = HeartbeatMode.LEARNING_REVIEW
        events.append(
            HeartbeatEvent(kind="schedule", detail="learning_review_interval", significance=0.35)
        )

    gap = _gap_for_mode(mode)
    last_rich = float(st.last_rich_learning_ts or 0.0)
    due_rich = (now - last_rich) >= gap or force or bool(event_hint)

    # Fingerprint external signals for "important change" without duplicating subsystem logic
    st_test = ""
    if selftests is not None:
        st_test = f"{selftests.summary.overall_status}:{','.join(selftests.summary.failed_checks[:3])}"
    wb_sig = ""
    if workbench is not None:
        wb_sig = f"{workbench.has_proposal}:{workbench.top_proposal.proposal_id}"
    sc_sig = ""
    if strategic_continuity is not None:
        sc_sig = str(strategic_continuity.session_carryover.headline or "")[:160]
    route_sig = ""
    if model_routing is not None:
        route_sig = (
            f"{getattr(model_routing, 'selected_model', '')}:"
            f"{getattr(model_routing, 'fallback_model', '')}:"
            f"{getattr(model_routing, 'continuity_preserved', True)}"
        )
    mr_sig = ""
    if memory_refinement is not None:
        d = memory_refinement.decision
        mr_sig = f"{bool(getattr(d, 'unfinished_thread_candidate', False))}:{float(getattr(d, 'retrieval_priority', 0)):.2f}"
    g_wb = _workbench_runtime_digest(g)
    sig = _digest(f"{st_test}|{wb_sig}|{sc_sig}|{route_sig}|{mr_sig}|{g_wb}|{mode}")
    important = sig != (st.last_digest or "") or force or bool(event_hint)
    if event_hint:
        events.insert(0, HeartbeatEvent(kind="operator", detail=event_hint, significance=0.75))

    # Silence & anti-spam (never auto-speak from this layer)
    should_silent = True
    suggested = ""
    summary = "cadence_skip"

    if due_rich:
        summary_bits: list[str] = []
        if important:
            if any(e.kind == "workbench" for e in events):
                summary_bits.append("workbench_attention")
                suggested = "review_workbench_proposals_when_convenient"
            if any(e.kind == "selftests" for e in events):
                summary_bits.append("diagnostics_shift")
                suggested = suggested or "check_selftests_when_convenient"
            if any(e.kind == "strategic_carryover" for e in events):
                summary_bits.append("carryover_threads")
                suggested = suggested or "consider_thread_continuity_in_prompting"
            if mode == HeartbeatMode.CONVERSATION_ACTIVE:
                suggested = ""
            elif mode == HeartbeatMode.QUIET_RECOVERY:
                suggested = ""
            elif mode == HeartbeatMode.LEARNING_REVIEW:
                suggested = "optional_learning_review_internal"
            elif mode == HeartbeatMode.IDLE_MONITORING:
                should_silent = urg < 0.62

            emit_sig = _digest(f"{mode}|{suggested}|{sig}")
            if emit_sig == st.last_emit_sig:
                st.silence_streak += 1
                if st.silence_streak < 4:
                    should_silent = True
                    suggested = ""
            else:
                st.silence_streak = 0
            st.last_emit_sig = emit_sig

            summary = ",".join(summary_bits) if summary_bits else "continuity_tick"
        else:
            summary = "no_significant_delta"

    tick_reason = "rich_eval" if due_rich else "cheap_tick"
    if force:
        tick_reason = "event_force"
    elif event_hint:
        tick_reason = f"event:{event_hint[:40]}"

    if due_rich or important:
        st.last_digest = sig
        st.last_rich_learning_ts = now
        if mode == HeartbeatMode.LEARNING_REVIEW:
            st.meta["last_learning_review_wall"] = now

    # Phase 58: autonomous leisure check
    try:
        from brain.leisure import autonomous_leisure_check
        _leisure_result = autonomous_leisure_check(g)
        if _leisure_result:
            print(_leisure_result)
    except Exception:
        pass

    # Phase 71: long-horizon plan tick
    try:
        from brain.planner import get_planner
        get_planner(g.get("BASE_DIR") or Path(__file__).resolve().parent.parent).tick_active_plans(g)
    except Exception:
        pass

    # Phase 45: weekly concept graph decay
    _WEEK_SECONDS = 7 * 24 * 3600
    _last_decay = float(st.meta.get("last_concept_decay_wall") or 0)
    if (now - _last_decay) >= _WEEK_SECONDS:
        try:
            _cg = g.get("_concept_graph") if isinstance(g, dict) else None
            if _cg is not None and callable(getattr(_cg, "decay_unused_nodes", None)):
                _decayed = _cg.decay_unused_nodes(days_threshold=30)
                if _decayed:
                    print(f"[heartbeat] concept_graph weekly decay: {_decayed} nodes affected")
                st.meta["last_concept_decay_wall"] = now
        except Exception:
            pass

    st.last_wallclock = now

    carry = HeartbeatCarryoverState(
        last_recorded_mode=mode,
        strategic_headline_digest=_digest(sc_sig),
        model_route_fallback_streak=route_streak,
        last_selected_model=str(getattr(model_routing, "selected_model", "") or "") if model_routing else "",
        last_fallback_model=str(getattr(model_routing, "fallback_model", "") or "") if model_routing else "",
        workbench_signal_digest=g_wb,
        tick_id_at_snapshot=st.tick_id,
        meta={"identity_anchors_read_only": True},
    )

    meta = {
        "urgency": urg,
        "gap_seconds": gap,
        "due_rich": due_rich,
        "respect_identity_anchors": True,
        "identity_files_write_prohibited": True,
        "route_fallback_streak": route_streak,
    }

    result = HeartbeatTickResult(
        heartbeat_active=True,
        heartbeat_tick_id=st.tick_id,
        heartbeat_mode=mode,
        last_tick_time=now,
        tick_reason=tick_reason,
        important_state_change=bool(important and due_rich),
        suggested_action=_trunc(suggested, 200),
        should_remain_silent=bool(should_silent),
        heartbeat_summary=_trunc(f"{mode}; {summary}" if due_rich else f"{mode}; quiet", 320),
        carryover=carry,
        events=events[:12],
        notes=[],
        meta=meta,
    )

    # Throttled persistence
    if st.tick_id % _SAVE_EVERY_N_TICKS == 0 or due_rich:
        save_heartbeat_state(st)

    # Concise logs — not every tick in steady idle
    log_it = (
        important
        and due_rich
        and (
            mode != HeartbeatMode.IDLE_MONITORING
            or not should_silent
            or st.tick_id % 47 == 0
        )
    )
    if log_it:
        print(
            f"[heartbeat] mode={mode} reason={tick_reason} active=True "
            f"tick={st.tick_id} important_change={'yes' if important and due_rich else 'no'} "
            f"silent={should_silent}"
        )
    elif important and due_rich:
        print(f"[heartbeat] important_change=yes silent={should_silent} mode={mode}")
    if important and due_rich and mode == HeartbeatMode.MAINTENANCE_WATCH:
        print(
            f"[heartbeat] important_change=yes maintenance signals present "
            f"(no auto-action; approvals unchanged)"
        )

    return result


def apply_heartbeat_to_perception_state(state: Any, bundle: Any) -> None:
    """Map :class:`HeartbeatTickResult` onto :class:`~brain.perception.PerceptionState` (Phase 31)."""
    hb = getattr(bundle, "heartbeat", None)
    if hb is None:
        state.heartbeat_active = False
        state.heartbeat_mode = HeartbeatMode.NO_HEARTBEAT
        state.heartbeat_summary = ""
        state.heartbeat_last_reason = ""
        state.heartbeat_tick_id = 0
        state.heartbeat_meta = {"phase": 31, "idle": True}
        return
    state.heartbeat_active = bool(hb.heartbeat_active)
    state.heartbeat_mode = str(hb.heartbeat_mode or HeartbeatMode.NO_HEARTBEAT)[:48]
    state.heartbeat_summary = str(hb.heartbeat_summary or "")[:600]
    state.heartbeat_last_reason = str(hb.tick_reason or "")[:120]
    state.heartbeat_tick_id = int(hb.heartbeat_tick_id or 0)
    m = dict(hb.meta or {})
    m["should_remain_silent"] = bool(hb.should_remain_silent)
    m["important_state_change"] = bool(hb.important_state_change)
    m["suggested_action"] = str(hb.suggested_action or "")[:260]
    m["events"] = [
        {"kind": e.kind, "detail": e.detail[:200], "significance": float(e.significance)}
        for e in list(hb.events or [])[:10]
    ]
    m["notes"] = list(hb.notes or [])[:8]
    co = getattr(hb, "carryover", None)
    if co is not None:
        m["carryover"] = {
            "last_recorded_mode": co.last_recorded_mode,
            "strategic_headline_digest": co.strategic_headline_digest,
            "model_route_fallback_streak": co.model_route_fallback_streak,
            "last_selected_model": co.last_selected_model[:120],
            "last_fallback_model": co.last_fallback_model[:120],
            "workbench_signal_digest": co.workbench_signal_digest[:48],
            "tick_id_at_snapshot": co.tick_id_at_snapshot,
            "meta": dict(co.meta or {}),
        }
    state.heartbeat_meta = m
