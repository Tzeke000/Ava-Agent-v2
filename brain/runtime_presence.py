"""
Phase 32 — runtime presence: bounded operator visibility and proactive timing hints.

Aggregates heartbeat, adaptive learning, strategic continuity, and maintenance signals into
one lightweight surface. Does not write ava_core identity files or approve workbench actions.
"""
from __future__ import annotations

import traceback
from pathlib import Path
from typing import Any, Optional

from .adaptive_learning import PREFERENCES_PATH
from .heartbeat import HEARTBEAT_STATE_PATH, load_heartbeat_state
from .perception_types import (
    AdaptiveLearningResult,
    HeartbeatTickResult,
    ImprovementLoopResult,
    OperatorStatusSnapshot,
    RuntimePresenceResult,
    SelfTestRunResult,
    SocialContinuityResult,
    StartupResumeSummary,
    StrategicContinuityResult,
    WorkbenchProposalResult,
)

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SESSION_STATE_PATH = _REPO_ROOT / "state" / "session_state.json"


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def _trunc(s: str, n: int = 240) -> str:
    t = " ".join((s or "").split())
    if len(t) <= n:
        return t
    return t[: n - 1].rstrip() + "…"


def bootstrap_startup_resume(g: dict[str, Any]) -> None:
    """Quiet startup: confirm carryover paths; sets g snapshot for pipeline (no chatter)."""
    if not isinstance(g, dict):
        return
    try:
        hb = load_heartbeat_state()
        adapt_ok = PREFERENCES_PATH.is_file()
        sess_ok = _SESSION_STATE_PATH.is_file()
        hb_ok = HEARTBEAT_STATE_PATH.is_file()
        sr = StartupResumeSummary(
            heartbeat_carryover_loaded=bool(hb_ok),
            adaptive_preferences_loaded=adapt_ok,
            session_state_present=sess_ok,
            quiet_monitoring_default=True,
            meta={"identity_anchors_read_only": True, "no_ava_core_write": True},
        )
        g["_startup_resume_snapshot"] = sr
        if not g.get("_startup_resume_logged"):
            loaded = any((hb_ok, adapt_ok, sess_ok))
            print(
                f"[startup_resume] continuity=heartbeat:{int(hb_ok)} "
                f"adaptive:{int(adapt_ok)} session:{int(sess_ok)} "
                f"loaded={int(loaded)} quiet_monitoring=1"
            )
            g["_startup_resume_logged"] = True
    except Exception as e:
        print(f"[startup_resume] bootstrap skipped: {e}")


def _proactive_silence_bias(
    hb: Optional[HeartbeatTickResult], al: Optional[AdaptiveLearningResult]
) -> float:
    b = 0.18
    if hb is not None:
        if bool(getattr(hb, "should_remain_silent", True)):
            b = max(b, 0.68)
        mode = str(getattr(hb, "heartbeat_mode", "") or "")
        if mode in ("quiet_recovery", "idle_monitoring", "learning_review"):
            b = max(b, 0.52)
        if bool(getattr(hb, "important_state_change", False)):
            b = min(b, 0.45)
    if al is not None:
        w = (al.meta or {}).get("weights_preview") or {}
        sil = float(w.get("silence_when_better_response", 0.5) or 0.5)
        if sil >= 0.62:
            b = max(b, 0.42)
        lf = str(al.learning_focus or "")
        if "silence" in lf:
            b = max(b, 0.38)
    return _clamp01(b)


def build_runtime_presence_safe(
    *,
    g: dict[str, Any],
    heartbeat: Optional[HeartbeatTickResult],
    adaptive_learning: Optional[AdaptiveLearningResult],
    strategic_continuity: Optional[StrategicContinuityResult],
    improvement_loop: Optional[ImprovementLoopResult],
    workbench: Optional[WorkbenchProposalResult],
    selftests: Optional[SelfTestRunResult],
    social_continuity: Optional[SocialContinuityResult],
) -> RuntimePresenceResult:
    try:
        return _build_runtime_presence(
            g=g if isinstance(g, dict) else {},
            heartbeat=heartbeat,
            adaptive_learning=adaptive_learning,
            strategic_continuity=strategic_continuity,
            improvement_loop=improvement_loop,
            workbench=workbench,
            selftests=selftests,
            social_continuity=social_continuity,
        )
    except Exception as e:
        print(f"[runtime_presence] failed: {e}\n{traceback.format_exc()}")
        return RuntimePresenceResult(
            notes=[_trunc(str(e), 160)],
            meta={"error": True},
        )


def _build_runtime_presence(
    *,
    g: dict[str, Any],
    heartbeat: Optional[HeartbeatTickResult],
    adaptive_learning: Optional[AdaptiveLearningResult],
    strategic_continuity: Optional[StrategicContinuityResult],
    improvement_loop: Optional[ImprovementLoopResult],
    workbench: Optional[WorkbenchProposalResult],
    selftests: Optional[SelfTestRunResult],
    social_continuity: Optional[SocialContinuityResult],
) -> RuntimePresenceResult:
    sr_in = g.get("_startup_resume_snapshot")
    startup_loaded = isinstance(sr_in, StartupResumeSummary)
    continuity_loaded = strategic_continuity is not None and bool(
        str(getattr(strategic_continuity.session_carryover, "headline", "") or "").strip()
        or list(strategic_continuity.active_threads or [])
    )

    presence_mode = "quiet_monitoring"
    ilp = improvement_loop
    wb = workbench
    sc = strategic_continuity
    soc = social_continuity

    if ilp is not None and bool(getattr(ilp, "loop_active", False)):
        presence_mode = "maintenance_focus"
    elif wb is not None and bool(getattr(wb, "has_proposal", False)):
        presence_mode = "maintenance_focus"
    elif soc is not None and bool(getattr(soc, "unfinished_thread_present", False)):
        presence_mode = "attention_needed"
    elif heartbeat is not None and str(getattr(heartbeat, "heartbeat_mode", "") or "") == "conversation_active":
        presence_mode = "conversation_adjacent"

    active_issue = ""
    if ilp is not None:
        active_issue = _trunc(str(getattr(ilp, "active_issue", "") or getattr(ilp, "loop_summary", "") or ""), 200)

    threads_sum = ""
    if sc is not None:
        threads_sum = _trunc(str(sc.session_carryover.headline or ""), 200)
        if not threads_sum and sc.active_threads:
            t0 = sc.active_threads[0]
            threads_sum = _trunc(str(getattr(t0, "summary", "") or getattr(t0, "category", "") or ""), 200)

    stsum = selftests.summary if selftests is not None else None
    st_overall = str(stsum.overall_status or "ok") if stsum else "ok"

    maint_parts: list[str] = []
    if ilp is not None:
        maint_parts.append(f"loop={str(ilp.loop_stage or '')[:48]}")
        if bool(getattr(ilp, "awaiting_approval", False)):
            maint_parts.append("awaiting_approval")
        if bool(getattr(ilp, "awaiting_execution", False)):
            maint_parts.append("awaiting_execution")
    if wb is not None and wb.has_proposal:
        maint_parts.append(f"proposal={wb.top_proposal.proposal_type[:40]}")
    if st_overall != "ok":
        maint_parts.append(f"selftests={st_overall}")
    maintenance_status_summary = _trunc("; ".join(maint_parts), 260) if maint_parts else "none_pending"

    learn_sum = ""
    if adaptive_learning is not None:
        learn_sum = _trunc(
            f"focus={adaptive_learning.learning_focus or '—'} "
            f"upd={int(adaptive_learning.learning_update_applied)} "
            f"conf={adaptive_learning.learning_confidence:.2f}",
            220,
        )

    hb_sum = ""
    if heartbeat is not None:
        hb_sum = _trunc(
            f"{heartbeat.heartbeat_mode} tick={heartbeat.heartbeat_tick_id} "
            f"silent={int(bool(heartbeat.should_remain_silent))}",
            200,
        )

    ready_state = "steady"
    if presence_mode == "maintenance_focus":
        ready_state = "observe"
    elif presence_mode == "attention_needed":
        ready_state = "attention"

    op_hb = hb_sum or "heartbeat=idle"
    op_learn = learn_sum or "learning=steady"
    op_maint = maintenance_status_summary[:180]
    op_thr = threads_sum or "threads=quiet"
    op_wb = "workbench=clear"
    if wb is not None and wb.has_proposal:
        op_wb = _trunc(f"workbench={wb.top_proposal.proposal_type}", 120)

    rollup = _trunc(f"{presence_mode}; {ready_state}; {op_maint[:80]}", 280)

    op_view = OperatorStatusSnapshot(
        heartbeat_line=op_hb,
        learning_line=op_learn,
        maintenance_line=op_maint,
        threads_line=op_thr,
        workbench_line=op_wb,
        rollup=rollup,
    )

    operator_status_summary = rollup

    pb = _proactive_silence_bias(heartbeat, adaptive_learning)

    meta = {
        "proactive_silence_bias": pb,
        "presence_mode": presence_mode,
        "identity_anchors_respected": True,
    }

    # Throttled operational log when mode changes or non-quiet
    sig = f"{presence_mode}|{maint_parts and 'm' or ''}|{threads_sum[:40]}"
    last = g.get("_runtime_presence_last_sig")
    should_log = last != sig
    if should_log:
        ai = active_issue[:90] if active_issue else "—"
        th = _trunc(threads_sum, 72) if threads_sum else "—"
        print(
            f"[runtime_presence] mode={presence_mode} ready={ready_state} "
            f"active_issue={ai} threads={th} summary={operator_status_summary[:120]}"
        )
    g["_runtime_presence_last_sig"] = sig

    return RuntimePresenceResult(
        presence_mode=presence_mode,
        startup_loaded=bool(startup_loaded),
        continuity_loaded=bool(continuity_loaded),
        active_issue_summary=active_issue,
        active_threads_summary=threads_sum,
        maintenance_status_summary=maintenance_status_summary,
        learning_status_summary=learn_sum,
        heartbeat_status_summary=hb_sum,
        operator_status_summary=operator_status_summary,
        ready_state=ready_state,
        operator_view=op_view,
        startup_resume=sr_in if isinstance(sr_in, StartupResumeSummary) else None,
        notes=[],
        meta=meta,
    )


def apply_runtime_presence_to_perception_state(state: Any, bundle: Any) -> None:
    """Map :class:`RuntimePresenceResult` onto :class:`~brain.perception.PerceptionState` (Phase 32)."""
    rp = getattr(bundle, "runtime_presence", None)
    if rp is None:
        state.runtime_presence_mode = "unknown"
        state.runtime_ready_state = "steady"
        state.runtime_active_issue_summary = ""
        state.runtime_threads_summary = ""
        state.runtime_maintenance_summary = ""
        state.runtime_learning_summary = ""
        state.runtime_operator_summary = ""
        state.runtime_presence_meta = {"phase": 32, "idle": True}
        return

    state.runtime_presence_mode = str(rp.presence_mode or "quiet_monitoring")[:48]
    state.runtime_ready_state = str(rp.ready_state or "steady")[:32]
    state.runtime_active_issue_summary = str(rp.active_issue_summary or "")[:400]
    state.runtime_threads_summary = str(rp.active_threads_summary or "")[:400]
    state.runtime_maintenance_summary = str(rp.maintenance_status_summary or "")[:400]
    state.runtime_learning_summary = str(rp.learning_status_summary or "")[:400]
    state.runtime_operator_summary = str(rp.operator_status_summary or "")[:500]
    m = dict(rp.meta or {})
    ov = getattr(rp, "operator_view", None)
    if ov is not None:
        m["operator_view"] = {
            "heartbeat_line": ov.heartbeat_line[:220],
            "learning_line": ov.learning_line[:220],
            "maintenance_line": ov.maintenance_line[:260],
            "threads_line": ov.threads_line[:220],
            "workbench_line": ov.workbench_line[:160],
            "rollup": ov.rollup[:320],
        }
    m["heartbeat_status_summary"] = str(rp.heartbeat_status_summary or "")[:260]
    state.runtime_presence_meta = m
