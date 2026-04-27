"""
Phase 14 — adaptive proactive trigger evaluation (recommendation-only).

Produces conservative trigger recommendations from structured perception/memory/pattern
signals. This module does not generate speech and does not force initiative actions.
"""
from __future__ import annotations

import traceback
from typing import Optional

from config.ava_tuning import PROACTIVE_CONFIG

from .perception_types import (
    ContinuityOutput,
    IdentityResolutionResult,
    InterpretationLayerResult,
    MemoryImportanceResult,
    PatternLearningResult,
    PerceptionMemoryOutput,
    ProactiveTriggerCandidate,
    ProactiveTriggerResult,
    QualityOutput,
    SceneSummaryResult,
)

prcfg = PROACTIVE_CONFIG

_last_trigger_signature: str = ""
_repeat_trigger_hits: int = 0


def reset_proactive_trigger_guard() -> None:
    """Reset spam-suppression guard (tests/session reset)."""
    global _last_trigger_signature, _repeat_trigger_hits
    _last_trigger_signature = ""
    _repeat_trigger_hits = 0


def _clamp01(v: float) -> float:
    return max(0.0, min(1.0, float(v)))


def _mk_candidate(
    trigger_type: str,
    score: float,
    priority: float,
    reason: str,
    action: str,
    evidence: dict,
) -> ProactiveTriggerCandidate:
    return ProactiveTriggerCandidate(
        trigger_type=trigger_type,
        trigger_score=_clamp01(score),
        trigger_priority=_clamp01(priority),
        trigger_reason=reason,
        suggested_action=action,
        supporting_evidence=dict(evidence),
    )


def _spam_suppression(signature: str) -> tuple[bool, str, int]:
    global _last_trigger_signature, _repeat_trigger_hits
    if signature == _last_trigger_signature:
        _repeat_trigger_hits += 1
    else:
        _last_trigger_signature = signature
        _repeat_trigger_hits = 0
    if _repeat_trigger_hits >= prcfg.spam_repeat_threshold:
        return True, "repeat_trigger_spam_guard", _repeat_trigger_hits
    return False, "", _repeat_trigger_hits


def evaluate_proactive_triggers(
    *,
    perception_memory: Optional[PerceptionMemoryOutput],
    memory_importance: Optional[MemoryImportanceResult],
    pattern_learning: Optional[PatternLearningResult],
    id_res: Optional[IdentityResolutionResult],
    scene: Optional[SceneSummaryResult],
    il: Optional[InterpretationLayerResult],
    qual: QualityOutput,
    cont: ContinuityOutput,
    acquisition_freshness: str,
    visual_truth_trusted: bool,
    voice_user_turn_priority: bool = False,
) -> ProactiveTriggerResult:
    """Evaluate proactive trigger recommendation with conservative suppression gates."""
    try:
        return _evaluate_proactive_triggers_inner(
            perception_memory=perception_memory,
            memory_importance=memory_importance,
            pattern_learning=pattern_learning,
            id_res=id_res,
            scene=scene,
            il=il,
            qual=qual,
            cont=cont,
            acquisition_freshness=acquisition_freshness,
            visual_truth_trusted=visual_truth_trusted,
            voice_user_turn_priority=voice_user_turn_priority,
        )
    except Exception as e:
        print(f"[proactive_triggers] failed: {e}\n{traceback.format_exc()}")
        return ProactiveTriggerResult(
            should_trigger=False,
            trigger_type="no_trigger",
            trigger_score=0.0,
            trigger_priority=0.0,
            trigger_reason="proactive_trigger_error_fallback",
            suppression_reason="error_fallback",
            suggested_action="wait",
            caution_flags=["proactive_trigger_error"],
            supporting_evidence={"error": str(e)},
            candidates=[],
            meta={"fallback": True},
        )


def _evaluate_proactive_triggers_inner(
    *,
    perception_memory: Optional[PerceptionMemoryOutput],
    memory_importance: Optional[MemoryImportanceResult],
    pattern_learning: Optional[PatternLearningResult],
    id_res: Optional[IdentityResolutionResult],
    scene: Optional[SceneSummaryResult],
    il: Optional[InterpretationLayerResult],
    qual: QualityOutput,
    cont: ContinuityOutput,
    acquisition_freshness: str,
    visual_truth_trusted: bool,
    voice_user_turn_priority: bool = False,
) -> ProactiveTriggerResult:
    if voice_user_turn_priority:
        return ProactiveTriggerResult(
            should_trigger=False,
            trigger_type="no_trigger",
            trigger_score=0.0,
            trigger_priority=0.0,
            trigger_reason="voice_user_turn_active",
            suppression_reason="voice_user_turn_priority",
            suggested_action="wait",
            caution_flags=["voice_conversational_floor"],
            supporting_evidence={},
            candidates=[],
            meta={"voice_gate": True},
        )

    pm = perception_memory or PerceptionMemoryOutput(event=None, skipped=True, skip_reason="missing_memory_output")
    mi = memory_importance or MemoryImportanceResult()
    pl = pattern_learning or PatternLearningResult()
    ir = id_res or IdentityResolutionResult()
    sc = scene or SceneSummaryResult()
    layer = il or InterpretationLayerResult()
    event_type = (pm.event.event_type if pm.event is not None else "") or "no_event"
    qlabel = str(getattr(qual.structured, "quality_label", "unreliable")) if qual.structured else "unreliable"
    blur_label = str(getattr(qual, "blur_label", "") or "")

    candidates: list[ProactiveTriggerCandidate] = []
    caution_flags: list[str] = []
    suppression_reason = ""

    # Conservative global suppression gates.
    if not visual_truth_trusted:
        suppression_reason = "vision_untrusted"
    elif acquisition_freshness in ("stale", "unavailable"):
        suppression_reason = "acquisition_not_fresh"
    elif qlabel == "unreliable":
        suppression_reason = "quality_unreliable"
    elif blur_label == "blurry":
        suppression_reason = "blur_too_high"
    elif layer.primary_event == "occupied_or_busy_visual_state":
        suppression_reason = "busy_context_hold_silence"
        caution_flags.append("busy_or_occupied")
    elif layer.no_meaningful_change and mi.decision.importance_score < prcfg.stable_no_change_importance_max:
        suppression_reason = "stable_no_meaningful_change"

    # Candidate generation (recommendations only).
    if event_type == "person_entered":
        candidates.append(
            _mk_candidate(
                "person_entered_trigger",
                prcfg.person_entered_score_base
                + (prcfg.person_entered_importance_scale * mi.decision.importance_score),
                prcfg.person_entered_priority,
                "person_entered_with_contextual_importance",
                "consider_gentle_greeting",
                {"event_type": event_type, "importance": mi.decision.importance_score},
            )
        )
    if event_type == "unknown_person_present" and mi.decision.importance_score >= prcfg.unknown_person_importance_min:
        candidates.append(
            _mk_candidate(
                "unknown_person_trigger",
                prcfg.unknown_person_score_base
                + (prcfg.unknown_person_importance_scale * mi.decision.importance_score),
                prcfg.unknown_person_priority,
                "unknown_person_present_and_notable",
                "consider_cautious_check",
                {"identity_state": ir.identity_state, "importance": mi.decision.importance_score},
            )
        )
    if event_type in ("person_entered", "known_person_present") and ir.resolved_identity:
        candidates.append(
            _mk_candidate(
                "return_after_absence_trigger",
                prcfg.return_absence_score_base
                + (prcfg.return_absence_continuity_scale * float(cont.continuity_confidence)),
                prcfg.return_absence_priority,
                "recognized_person_present_after_transition",
                "consider_welcome_back_check_in",
                {"resolved_identity": ir.resolved_identity, "continuity": float(cont.continuity_confidence)},
            )
        )
    if (
        pl.primary_signal.pattern_type == "unusual_event_pattern"
        and pl.primary_signal.unusualness_score >= prcfg.unusual_pattern_unusualness_min
    ):
        candidates.append(
            _mk_candidate(
                "unusual_pattern_trigger",
                prcfg.unusual_pattern_score_base
                + (prcfg.unusual_pattern_unusualness_scale * pl.primary_signal.unusualness_score),
                prcfg.unusual_pattern_priority,
                "pattern_unusualness_elevated",
                "consider_observational_check_in",
                {"pattern_type": pl.primary_signal.pattern_type, "unusualness": pl.primary_signal.unusualness_score},
            )
        )
    if layer.primary_event == "scene_changed" and mi.decision.importance_score >= prcfg.notable_change_importance_min:
        candidates.append(
            _mk_candidate(
                "notable_change_trigger",
                prcfg.notable_change_score_base
                + (prcfg.notable_change_importance_scale * mi.decision.importance_score),
                prcfg.notable_change_priority,
                "scene_change_is_notable",
                "consider_light_acknowledgement",
                {"scene_state": sc.overall_scene_state, "importance": mi.decision.importance_score},
            )
        )
    if (
        pl.primary_signal.pattern_type == "baseline_idle_pattern"
        and pl.primary_signal.familiarity_score >= prcfg.check_in_familiarity_min
    ):
        candidates.append(
            _mk_candidate(
                "check_in_trigger",
                prcfg.check_in_score_base
                + (prcfg.check_in_familiarity_scale * pl.primary_signal.familiarity_score),
                prcfg.check_in_priority,
                "long_idle_baseline_may_allow_gentle_check_in",
                "consider_soft_check_in",
                {"idle_familiarity": pl.primary_signal.familiarity_score},
            )
        )
    if layer.primary_event == "occupied_or_busy_visual_state":
        candidates.append(
            _mk_candidate(
                "hold_silence_trigger",
                prcfg.hold_silence_score,
                prcfg.hold_silence_priority,
                "busy_or_occupied_state_prefers_silence",
                "hold_silence",
                {"event_type": layer.primary_event},
            )
        )

    if not candidates:
        candidates.append(
            _mk_candidate(
                "no_trigger",
                0.0,
                0.0,
                "no_conservative_trigger_candidate",
                "wait",
                {"event_type": event_type},
            )
        )

    # Pick top candidate by score then priority.
    primary = sorted(candidates, key=lambda c: (float(c.trigger_score), float(c.trigger_priority)), reverse=True)[0]
    should_trigger = bool(primary.trigger_type != "no_trigger" and primary.suggested_action != "hold_silence")

    # Spam suppression for repeated opportunities.
    signature = f"{primary.trigger_type}|{event_type}|{ir.resolved_identity or ''}|{sc.overall_scene_state}"
    spam_suppress, spam_reason, repeat_hits = _spam_suppression(signature)
    if spam_suppress:
        suppression_reason = spam_reason
        caution_flags.append("spam_guard")

    if primary.trigger_type == "hold_silence_trigger":
        should_trigger = False
        suppression_reason = suppression_reason or "hold_silence_recommended"
        caution_flags.append("hold_silence")

    if suppression_reason:
        should_trigger = False

    # Mark suppressed candidates for visibility.
    for c in candidates:
        c.suppressed = bool(not should_trigger and c.trigger_type == primary.trigger_type)
        c.suppression_reason = suppression_reason if c.suppressed else ""
        c.meta = {"repeat_hits": repeat_hits}

    result = ProactiveTriggerResult(
        should_trigger=should_trigger,
        trigger_type=primary.trigger_type if should_trigger else "no_trigger",
        trigger_score=float(primary.trigger_score if should_trigger else 0.0),
        trigger_priority=float(primary.trigger_priority if should_trigger else 0.0),
        trigger_reason=primary.trigger_reason,
        suppression_reason=suppression_reason,
        suggested_action=primary.suggested_action if should_trigger else "wait",
        caution_flags=sorted(set(caution_flags + list(primary.caution_flags))),
        supporting_evidence={
            "event_type": event_type,
            "importance_score": float(mi.decision.importance_score),
            "importance_label": mi.decision.importance_label,
            "pattern_type": pl.primary_signal.pattern_type,
            "pattern_unusualness": float(pl.primary_signal.unusualness_score),
            "pattern_familiarity": float(pl.primary_signal.familiarity_score),
            "identity_state": ir.identity_state,
            "resolved_identity": ir.resolved_identity,
            "scene_state": sc.overall_scene_state,
            "acquisition_freshness": acquisition_freshness,
            "quality_label": qlabel,
            "blur_label": blur_label,
            "continuity_confidence": float(cont.continuity_confidence),
        },
        candidates=candidates,
        meta={
            "visual_truth_trusted": bool(visual_truth_trusted),
            "repeat_hits": repeat_hits,
            "candidate_count": len(candidates),
        },
    )
    print(
        f"[proactive_triggers] type={primary.trigger_type} "
        f"should={result.should_trigger} score={result.trigger_score:.2f} "
        f"suppressed={bool(result.suppression_reason)}"
    )
    return result
