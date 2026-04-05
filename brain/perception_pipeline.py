"""
Phase 3 — staged perception pipeline.

Stages (conceptual): acquisition → quality gate → detection → recognition →
interpretation (emotion + salience) → continuity (Phase 7) → identity fallback (Phase 8) →
scene summary (Phase 9) → interpretation layer (Phase 10) → perception memory (Phase 11) →
package → :class:`perception.PerceptionState` via adapter.

Failures in one stage do not abort the turn; each stage returns safe defaults and ``StageResult``.
"""
from __future__ import annotations

import traceback
from typing import Any

from .perception_types import (
    AcquisitionOutput,
    ContinuityOutput,
    ContinuityResult,
    DetectionOutput,
    IdentityResolutionResult,
    InterpretationLayerResult,
    InterpretationOutput,
    PerceptionMemoryOutput,
    SceneSummaryResult,
    PackageOutput,
    PerceptionPipelineBundle,
    QualityOutput,
    RecognitionOutput,
    SalienceResult,
    StageResult,
)
from .frame_quality import compute_frame_quality, confidence_scales_from_label
from .salience import build_salience_result, salience_items_as_dicts
from .continuity import update_continuity
from .identity_fallback import resolve_identity_fallback
from .scene_summary import build_scene_summary
from .interpretation import build_interpretation_layer
from .perception_memory import build_perception_memory_output
from .shared import now_ts


def _apply_quality_fields_to_state(state: Any, q: QualityOutput) -> None:
    """Copy structured quality + scales onto PerceptionState (Phase 4)."""
    state.recognition_quality_scale = q.recognition_confidence_scale
    state.expression_quality_scale = q.expression_confidence_scale
    sq = q.structured
    if sq is None:
        state.quality_label = "unreliable"
        state.blur_value = 0.0
        state.blur_label = "sharp"
        state.blur_confidence_scale = 1.0
        state.blur_recognition_scale = 1.0
        state.blur_expression_scale = 1.0
        state.blur_interpretation_scale = 1.0
        state.blur_reason_flags = []
        state.blur_quality_score = 0.0
        state.darkness_quality_score = 0.0
        state.overexposure_quality_score = 0.0
        state.motion_smear_quality_score = 1.0
        state.occlusion_quality_score = 1.0
        return
    state.quality_label = sq.quality_label
    state.blur_value = getattr(sq, "blur_value", 0.0)
    state.blur_label = getattr(sq, "blur_label", "sharp")
    state.blur_confidence_scale = getattr(sq, "blur_confidence_scale", 1.0)
    state.blur_recognition_scale = getattr(sq, "blur_recognition_scale", 1.0)
    state.blur_expression_scale = getattr(sq, "blur_expression_scale", 1.0)
    state.blur_interpretation_scale = getattr(sq, "blur_interpretation_scale", 1.0)
    state.blur_reason_flags = list(getattr(sq, "blur_reason_flags", []) or [])
    state.blur_quality_score = sq.blur_score
    state.darkness_quality_score = sq.darkness_score
    state.overexposure_quality_score = sq.overexposure_score
    state.motion_smear_quality_score = sq.motion_smear_score
    state.occlusion_quality_score = sq.occlusion_score


def _motion_smear_from_quality(qual: QualityOutput) -> float:
    sq = qual.structured
    if sq is None:
        return 1.0
    return float(getattr(sq, "motion_smear_score", 1.0))


def _log_top_salient(sal_res: SalienceResult) -> None:
    top = next((x for x in sal_res.items if x.is_top), None)
    if top:
        print(
            f"[perception_pipeline] top_salient={top.item_type}:{top.label} "
            f"score={top.score:.2f} combined={sal_res.combined_scalar:.2f}"
        )
    else:
        print(f"[perception_pipeline] top_salient=none combined={sal_res.combined_scalar:.2f}")


def _apply_continuity_structured_to_state(state: Any, cont: Any) -> None:
    """Copy Phase 7 continuity snapshot onto PerceptionState (not public ``identity_state`` — Phase 8)."""
    cr = getattr(cont, "structured", None)
    if cr is None:
        return
    state.continuity_confidence = float(cr.continuity_confidence)
    state.continuity_prior_identity = cr.prior_identity
    state.continuity_current_identity = cr.current_identity
    state.continuity_matched_factors = dict(cr.matched_factors)
    state.continuity_matched_notes = list(cr.matched_notes)
    state.continuity_frame_gap = int(cr.frame_gap)
    state.continuity_seconds_since_prior = float(cr.seconds_since_prior)
    state.continuity_suppress_flip = bool(cr.suppress_flip)


def _apply_identity_resolution_to_state(state: Any, ir: IdentityResolutionResult | None) -> None:
    """Copy Phase 8 identity resolution (canonical ``identity_state``) onto PerceptionState."""
    if ir is None:
        state.identity_state = "no_face"
        state.resolved_face_identity = None
        state.stable_face_identity = None
        state.identity_fallback_source = "none"
        state.identity_fallback_notes = []
        state.identity_confidence = 0.0
        return
    state.identity_state = ir.identity_state
    state.resolved_face_identity = ir.resolved_identity
    state.stable_face_identity = ir.stable_identity
    state.identity_fallback_source = ir.fallback_source
    state.identity_fallback_notes = list(ir.fallback_notes)
    state.identity_confidence = float(ir.identity_confidence)


def _apply_scene_summary_to_state(state: Any, ss: SceneSummaryResult | None) -> None:
    """Copy Phase 9 scene summary onto PerceptionState."""
    if ss is None:
        state.scene_compact_summary = ""
        state.scene_overall_state = "uncertain"
        state.scene_summary_confidence = 0.0
        state.scene_face_presence = "unknown"
        state.scene_face_count_estimate = 0
        state.scene_primary_identity_line = ""
        state.scene_key_entities = []
        state.scene_lighting_summary = ""
        state.scene_blur_summary = ""
        state.scene_change_summary = ""
        state.scene_entrant_summary = ""
        state.scene_summary_notes = []
        state.scene_summary_meta = {}
        return
    state.scene_compact_summary = ss.compact_text_summary
    state.scene_overall_state = ss.overall_scene_state
    state.scene_summary_confidence = float(ss.summary_confidence)
    state.scene_face_presence = ss.face_presence
    state.scene_face_count_estimate = int(ss.face_count_estimate)
    state.scene_primary_identity_line = ss.primary_identity_summary
    state.scene_key_entities = list(ss.key_entities)
    state.scene_lighting_summary = ss.lighting_summary
    state.scene_blur_summary = ss.blur_summary
    state.scene_change_summary = ss.scene_change_summary
    state.scene_entrant_summary = ss.entrant_summary
    state.scene_summary_notes = list(ss.notes)
    state.scene_summary_meta = dict(ss.meta)


def _apply_interpretation_layer_to_state(state: Any, il: InterpretationLayerResult | None) -> None:
    """Copy Phase 10 semantic interpretation onto PerceptionState."""
    if il is None:
        state.interpretation_event_types = []
        state.interpretation_primary_event = "uncertain_visual_state"
        state.interpretation_confidence = 0.0
        state.interpretation_priority = 0.0
        state.interpretation_subject = None
        state.interpretation_identity = None
        state.interpretation_notes = []
        state.interpretation_no_meaningful_change = True
        state.interpretation_evidence = {}
        return
    state.interpretation_event_types = list(il.event_types)
    state.interpretation_primary_event = il.primary_event
    state.interpretation_confidence = float(il.event_confidence)
    state.interpretation_priority = float(il.event_priority)
    state.interpretation_subject = il.interpreted_subject
    state.interpretation_identity = il.interpreted_identity
    state.interpretation_notes = list(il.interpretation_notes)
    state.interpretation_no_meaningful_change = bool(il.no_meaningful_change)
    state.interpretation_evidence = dict(il.evidence)


def _apply_perception_memory_to_state(state: Any, pm: PerceptionMemoryOutput | None) -> None:
    """Copy Phase 11 memory-ready record summary onto PerceptionState (no persistence)."""
    if pm is None:
        state.perception_memory_suppressed = False
        state.perception_memory_event_type = ""
        state.perception_memory_candidate = False
        state.perception_memory_confidence = 0.0
        state.perception_memory_summary = ""
        state.perception_memory_meta = {}
        state.perception_memory_skip_reason = ""
        return
    state.perception_memory_skip_reason = pm.skip_reason or ""
    if pm.event is None:
        state.perception_memory_suppressed = bool(pm.skipped)
        state.perception_memory_event_type = ""
        state.perception_memory_candidate = False
        state.perception_memory_confidence = 0.0
        state.perception_memory_summary = ""
        state.perception_memory_meta = {
            "skipped": bool(pm.skipped),
            "skip_reason": state.perception_memory_skip_reason,
        }
        return
    state.perception_memory_suppressed = False
    ev = pm.event
    state.perception_memory_event_type = ev.event_type
    state.perception_memory_candidate = bool(ev.memory_worthy_candidate)
    state.perception_memory_confidence = float(ev.event_confidence)
    state.perception_memory_summary = ev.scene_summary_snippet
    state.perception_memory_meta = {
        "wall_time": ev.wall_time,
        "frame_seq": ev.frame_seq,
        "event_priority": ev.event_priority,
        "identity_state": ev.identity_state,
        "resolved_identity": ev.resolved_identity,
        "stable_identity": ev.stable_identity,
        "interpretation_primary": ev.interpretation_primary_event,
        "evidence": dict(ev.evidence),
        "notes": list(ev.notes),
        "relevant_entities": list(ev.relevant_entities),
    }


def _apply_salience_structured_to_state(state: Any, interp: InterpretationOutput) -> None:
    """Copy Phase 6 salience snapshot onto PerceptionState (safe if structured missing)."""
    sr = interp.salience_structured
    if sr is None:
        state.salience_items = []
        state.salience_top_label = ""
        state.salience_top_type = ""
        state.salience_top_score = 0.0
        state.salience_combined_scalar = float(interp.salience)
        return
    state.salience_items = salience_items_as_dicts(sr.items)
    top = next((x for x in sr.items if x.is_top), None)
    state.salience_top_label = top.label if top else ""
    state.salience_top_type = top.item_type if top else ""
    state.salience_top_score = float(top.score) if top else 0.0
    state.salience_combined_scalar = float(sr.combined_scalar)


def _stage_acquisition(camera_manager: Any, image: Any) -> AcquisitionOutput:
    try:
        resolved = camera_manager.resolve_frame_detailed(image)
        print(
            f"[perception_pipeline] acquisition ok src={resolved.source} "
            f"has_frame={resolved.frame is not None} seq={resolved.frame_seq}"
        )
        return AcquisitionOutput(
            StageResult(ok=True, meta={"frame_seq": resolved.frame_seq, "source": resolved.source}),
            resolved=resolved,
        )
    except Exception as e:
        print(f"[perception_pipeline] acquisition failed: {e}\n{traceback.format_exc()}")
        return AcquisitionOutput(StageResult(ok=False, error=str(e)), resolved=None)


def _stage_quality(resolved: Any) -> QualityOutput:
    if resolved is None:
        print("[perception_pipeline] quality skipped (no resolved frame)")
        return QualityOutput(
            stage=StageResult(ok=False, skipped=True, error="no_resolution"),
            visual_truth_trusted=False,
            vision_status="stable",
            recognition_confidence_scale=1.0,
            expression_confidence_scale=1.0,
        )
    structured = getattr(resolved, "quality_detail", None)
    if structured is None and resolved.frame is not None:
        structured = compute_frame_quality(resolved.frame)
    label = structured.quality_label if structured is not None else "unreliable"
    q_rec, q_expr = confidence_scales_from_label(label)
    blur_val = 0.0
    blur_label = "sharp"
    br = be = bi = 1.0
    if structured is not None:
        blur_val = float(getattr(structured, "blur_value", 0.0))
        blur_label = getattr(structured, "blur_label", "sharp")
        br = float(getattr(structured, "blur_recognition_scale", 1.0))
        be = float(getattr(structured, "blur_expression_scale", 1.0))
        bi = float(getattr(structured, "blur_interpretation_scale", 1.0))
    rec_scale = q_rec * br
    expr_scale = q_expr * be
    conf = 1.0 if resolved.visual_truth_trusted else 0.0
    print(
        f"[perception_pipeline] quality vision={resolved.vision_status} "
        f"trusted={resolved.visual_truth_trusted} fq={resolved.frame_quality:.2f} "
        f"qlabel={label} recovery={resolved.recovery_state} "
        f"blur_value={blur_val:.1f} blur_label={blur_label} "
        f"blur_scale rec={br:.2f} expr={be:.2f} interp={bi:.2f} "
        f"combined_rec={rec_scale:.2f} combined_expr={expr_scale:.2f}"
    )
    return QualityOutput(
        stage=StageResult(
            ok=True,
            confidence=conf,
            meta={
                "vision_status": resolved.vision_status,
                "quality_label": label,
                "blur_label": blur_label,
                "blur_value": blur_val,
            },
        ),
        visual_truth_trusted=resolved.visual_truth_trusted,
        vision_status=resolved.vision_status,
        frame_quality=resolved.frame_quality,
        frame_quality_reasons=list(resolved.frame_quality_reasons or []),
        is_fresh=resolved.is_fresh,
        recovery_state=resolved.recovery_state,
        fresh_frame_streak=resolved.fresh_frame_streak,
        structured=structured,
        recognition_confidence_scale=rec_scale,
        expression_confidence_scale=expr_scale,
        blur_value=blur_val,
        blur_label=blur_label,
        blur_recognition_scale=br,
        blur_expression_scale=be,
        blur_interpretation_scale=bi,
        quality_only_recognition_scale=q_rec,
        quality_only_expression_scale=q_expr,
    )


def _stage_detection(camera_manager: Any, resolved: Any, g: dict) -> DetectionOutput:
    if resolved is None or resolved.frame is None:
        print("[perception_pipeline] detection skipped (no frame)")
        return DetectionOutput(
            stage=StageResult(ok=False, skipped=True, error="no_frame"),
            face_status="No camera image",
        )
    try:
        face_status = camera_manager.detect_face(resolved.frame, g)
    except Exception as e:
        print(f"[perception_pipeline] detection face_status failed: {e}")
        face_status = "No camera image"
    person_count = 0
    face_detected = False
    gaze_present = False
    face_rects: list[tuple[int, int, int, int]] = []
    try:
        cascade = g.get("face_cascade")
        if cascade is not None:
            import cv2

            gray = cv2.cvtColor(resolved.frame, cv2.COLOR_BGR2GRAY)
            faces = cascade.detectMultiScale(gray, 1.3, 5)
            person_count = len(faces)
            face_detected = person_count > 0
            gaze_present = face_detected
            face_rects = [(int(x), int(y), int(w), int(h)) for (x, y, w, h) in faces]
    except Exception as e:
        print(f"[perception_pipeline] detection cascade failed: {e}")
    print(
        f"[perception_pipeline] detection ok={face_status!r} count={person_count} "
        f"face_detected={face_detected} rects={len(face_rects)}"
    )
    return DetectionOutput(
        stage=StageResult(ok=True, meta={"cascade": person_count >= 0}),
        face_detected=face_detected,
        person_count=person_count,
        face_status=face_status,
        gaze_present=gaze_present,
        face_rects=face_rects,
    )


def _stage_recognition(
    camera_manager: Any, resolved: Any, g: dict, trusted: bool
) -> RecognitionOutput:
    if not trusted or resolved is None or resolved.frame is None:
        print("[perception_pipeline] recognition skipped (untrusted or no frame)")
        return RecognitionOutput(
            stage=StageResult(ok=False, skipped=True, error="skipped_untrusted_or_no_frame"),
            recognized_text="",
            face_identity=None,
            identity_confidence=0.0,
        )
    try:
        recognized_text, face_identity = camera_manager.recognize_face(resolved.frame, g)
    except Exception as e:
        print(f"[perception_pipeline] recognition failed: {e}")
        return RecognitionOutput(
            stage=StageResult(ok=False, error=str(e)),
            recognized_text="",
            face_identity=None,
            identity_confidence=0.0,
        )
    print(
        f"[perception_pipeline] recognition ok identity={face_identity!r} "
        f"preview={(recognized_text or '')[:100]!r}"
    )
    return RecognitionOutput(
        stage=StageResult(ok=True),
        recognized_text=recognized_text or "",
        face_identity=face_identity,
        identity_confidence=0.0,
    )


def _stage_continuity(
    camera_manager: Any,
    resolved: Any,
    det: DetectionOutput,
    recog: RecognitionOutput,
    interp: InterpretationOutput,
    trusted: bool,
) -> ContinuityOutput:
    """Phase 7 temporal continuity after salience; ``note_trusted_identity`` on confirmed recognition."""
    last_stable = getattr(resolved, "last_stable_identity", None) if resolved else None
    sal_top_label = ""
    sal_top_type = ""
    sr = interp.salience_structured
    if sr is not None and sr.items:
        top = next((x for x in sr.items if x.is_top), None)
        if top is None:
            top = sr.items[0]
        sal_top_label = top.label
        sal_top_type = top.item_type

    frame_seq = int(getattr(resolved, "frame_seq", 0) or 0) if resolved else 0
    frame_ts = float(getattr(resolved, "frame_ts", 0.0) or 0.0) if resolved else 0.0
    shape = resolved.frame.shape if resolved is not None and resolved.frame is not None else None

    cr = update_continuity(
        trusted=trusted,
        frame_seq=frame_seq,
        frame_ts=frame_ts,
        frame_shape=shape,
        face_detected=bool(det.face_detected),
        face_rects=list(det.face_rects or []),
        recognized_text=recog.recognized_text or "",
        face_identity=recog.face_identity if trusted else None,
        salience_top_label=sal_top_label,
        salience_top_type=sal_top_type,
    )

    if not trusted or resolved is None:
        print(
            f"[perception_pipeline] continuity state={cr.identity_state} conf={cr.continuity_confidence:.2f} "
            f"(deferred_untrusted)"
        )
        return ContinuityOutput(
            stage=StageResult(ok=False, skipped=True, error="untrusted"),
            last_stable_identity=last_stable,
            continuity_confidence=cr.continuity_confidence,
            tracking_note="continuity_deferred_until_trusted_frame",
            structured=cr,
        )

    if cr.identity_state == "confirmed_recognition" and recog.face_identity:
        last_stable = recog.face_identity
    elif cr.last_stable_identity:
        last_stable = cr.last_stable_identity or last_stable

    tracking_note = ",".join(cr.matched_notes[:5]) if cr.matched_notes else "continuity_v7"
    flip = " suppress_flip" if cr.suppress_flip else ""
    print(
        f"[perception_pipeline] continuity state={cr.identity_state} conf={cr.continuity_confidence:.2f}"
        f"{flip} last_stable={last_stable!r} note={tracking_note!r}"
    )
    return ContinuityOutput(
        stage=StageResult(ok=True, confidence=cr.continuity_confidence),
        last_stable_identity=last_stable,
        continuity_confidence=cr.continuity_confidence,
        tracking_note=tracking_note,
        structured=cr,
    )


def _stage_interpretation(
    resolved: Any,
    det: DetectionOutput,
    recog: RecognitionOutput,
    trusted: bool,
    user_text: str,
    qual: QualityOutput,
) -> InterpretationOutput:
    emotion: str | None = None
    motion = _motion_smear_from_quality(qual)
    shape = resolved.frame.shape if resolved is not None and resolved.frame is not None else None

    if not trusted or resolved is None or resolved.frame is None or not det.face_detected:
        print("[perception_pipeline] interpretation emotion skipped")
        sal_res = build_salience_result(
            frame_shape=shape,
            face_rects=list(det.face_rects or []),
            face_detected=bool(det.face_detected),
            person_count=int(det.person_count or 0),
            face_identity=recog.face_identity if trusted else None,
            face_emotion=None,
            user_text=user_text,
            motion_smear_score=motion,
        )
        _log_top_salient(sal_res)
        return InterpretationOutput(
            stage=StageResult(ok=False, skipped=True, error="no_emotion_path"),
            face_emotion=None,
            salience=sal_res.combined_scalar,
            scene_summary_hint="",
            salience_structured=sal_res,
        )
    try:
        from .vision import analyze_face_emotion

        emotion = analyze_face_emotion(resolved.frame)
    except Exception as e:
        print(f"[perception_pipeline] interpretation emotion failed: {e}")
        emotion = "neutral"
    sal_res = build_salience_result(
        frame_shape=shape,
        face_rects=list(det.face_rects or []),
        face_detected=det.face_detected,
        person_count=det.person_count,
        face_identity=recog.face_identity,
        face_emotion=emotion,
        user_text=user_text,
        motion_smear_score=motion,
    )
    _log_top_salient(sal_res)
    print(
        f"[perception_pipeline] interpretation emotion={emotion!r} salience={sal_res.combined_scalar:.2f} "
        f"(scene_summary_hook=unused)"
    )
    return InterpretationOutput(
        stage=StageResult(ok=True, meta={"emotion": emotion}),
        face_emotion=emotion,
        salience=sal_res.combined_scalar,
        scene_summary_hint="",
        salience_structured=sal_res,
    )


def run_perception_pipeline(
    camera_manager: Any,
    image: Any,
    g: dict,
    user_text: str = "",
) -> PerceptionPipelineBundle:
    """Run all stages in order; each stage tolerates upstream failure."""
    ut = user_text or ""
    acq = _stage_acquisition(camera_manager, image)
    resolved = acq.resolved
    qual = _stage_quality(resolved)

    trusted = bool(
        resolved is not None
        and resolved.visual_truth_trusted
        and resolved.frame is not None
    )
    if trusted:
        det = _stage_detection(camera_manager, resolved, g)
        recog = _stage_recognition(camera_manager, resolved, g, True)
        interp = _stage_interpretation(resolved, det, recog, True, ut, qual)
        cont = _stage_continuity(camera_manager, resolved, det, recog, interp, True)
    else:
        print("[perception_pipeline] detection/recognition short-circuit (untrusted or no frame)")
        det = DetectionOutput(
            stage=StageResult(ok=False, skipped=True, error="untrusted_or_no_frame"),
            face_status="No camera image",
        )
        recog = RecognitionOutput(
            stage=StageResult(ok=False, skipped=True, error="skipped_untrusted"),
            recognized_text="",
            face_identity=None,
            identity_confidence=0.0,
        )
        interp = _stage_interpretation(resolved, det, recog, False, ut, qual)
        cont = _stage_continuity(camera_manager, resolved, det, recog, interp, False)

    cr_struct: ContinuityResult | None = cont.structured
    id_res = resolve_identity_fallback(
        trusted=trusted,
        face_detected=bool(det.face_detected),
        raw_identity=recog.face_identity,
        recognized_text=recog.recognized_text or "",
        recognition_confidence_scale=float(qual.recognition_confidence_scale),
        continuity=cr_struct,
    )
    if (
        trusted
        and id_res.identity_state == "confirmed_recognition"
        and id_res.raw_identity
    ):
        try:
            camera_manager.note_trusted_identity(id_res.raw_identity)
        except Exception as e:
            print(f"[perception_pipeline] identity note_trusted_identity failed: {e}")
    print(
        f"[perception_pipeline] identity resolved state={id_res.identity_state} "
        f"source={id_res.fallback_source} conf={id_res.identity_confidence:.2f} "
        f"resolved={id_res.resolved_identity!r}"
    )

    vs = getattr(resolved, "vision_status", "no_frame") if resolved is not None else "no_frame"
    af = getattr(resolved, "acquisition_freshness", "unavailable") if resolved is not None else "unavailable"
    fseq = int(getattr(resolved, "frame_seq", 0) or 0) if resolved is not None else 0
    ss = build_scene_summary(
        trusted=trusted,
        vision_status=str(vs),
        face_detected=bool(det.face_detected),
        person_count=int(det.person_count or 0),
        id_res=id_res,
        qual=qual,
        interp=interp,
        cont=cont,
        acquisition_freshness=str(af),
        frame_seq=fseq,
    )
    print(
        f"[perception_pipeline] summary state={ss.overall_scene_state} "
        f"identity={ss.primary_identity_summary!r} change={ss.scene_change_summary!r}"
    )

    il = build_interpretation_layer(
        trusted=trusted,
        vision_status=str(vs),
        user_text=ut,
        id_res=id_res,
        scene=ss,
        interp=interp,
        qual=qual,
        cont=cont,
    )
    print(
        f"[perception_pipeline] interpretation primary={il.primary_event!r} "
        f"priority={il.event_priority:.2f} conf={il.event_confidence:.2f}"
    )

    pm = build_perception_memory_output(
        wall_time=now_ts(),
        frame_seq=fseq,
        trusted=trusted,
        acquisition_freshness=str(af),
        id_res=id_res,
        scene=ss,
        il=il,
        qual=qual,
        interp=interp,
        cont=cont,
    )
    if pm.skipped or pm.event is None:
        print(
            f"[perception_pipeline] memory event=— candidate=False "
            f"skipped={pm.skipped} reason={pm.skip_reason!r}"
        )
    else:
        print(
            f"[perception_pipeline] memory event={pm.event.event_type!r} "
            f"candidate={pm.event.memory_worthy_candidate}"
        )

    print(
        f"[perception_pipeline] package trusted={trusted} vision="
        f"{getattr(resolved, 'vision_status', 'n/a') if resolved else 'n/a'}"
    )
    pkg = PackageOutput(stage=StageResult(ok=True))

    return PerceptionPipelineBundle(
        acquisition=acq,
        quality=qual,
        detection=det,
        recognition=recog,
        continuity=cont,
        interpretation=interp,
        package=pkg,
        resolved=resolved,
        user_text=ut,
        identity_resolution=id_res,
        scene_summary=ss,
        interpretation_layer=il,
        perception_memory=pm,
    )


def bundle_to_perception_state(bundle: PerceptionPipelineBundle, user_text: str) -> Any:
    """
    Map pipeline bundle to :class:`perception.PerceptionState` (legacy shape for workspace / avaagent).
    """
    from .perception import PerceptionState
    from .shared import now_ts

    state = PerceptionState(user_text=user_text or "", timestamp=now_ts())
    resolved = bundle.resolved
    q = bundle.quality
    d = bundle.detection
    r = bundle.recognition
    c = bundle.continuity
    i = bundle.interpretation
    idr = bundle.identity_resolution
    ss = bundle.scene_summary
    il = bundle.interpretation_layer
    pm = bundle.perception_memory

    if not bundle.acquisition.stage.ok or resolved is None:
        _apply_scene_summary_to_state(state, ss)
        _apply_interpretation_layer_to_state(state, il)
        _apply_perception_memory_to_state(state, pm)
        return state

    state.frame = resolved.frame
    state.vision_status = resolved.vision_status
    state.frame_ts = resolved.frame_ts
    state.frame_age_ms = resolved.frame_age_ms
    state.frame_source = resolved.source
    state.frame_seq = resolved.frame_seq
    state.is_fresh = resolved.is_fresh
    state.fresh_frame_streak = resolved.fresh_frame_streak
    state.visual_truth_trusted = q.visual_truth_trusted
    state.frame_quality = q.frame_quality
    state.frame_quality_reasons = list(q.frame_quality_reasons)
    state.recovery_state = q.recovery_state
    state.last_stable_identity = getattr(resolved, "last_stable_identity", None)
    state.identity_confidence = 0.0
    state.continuity_confidence = 0.0
    state.acquisition_freshness = getattr(resolved, "acquisition_freshness", "unavailable")
    _apply_quality_fields_to_state(state, q)

    if resolved.frame is None:
        state.face_status = "No camera image"
        state.recognized_text = "No frame — cannot assess the scene as current."
        state.face_detected = False
        state.person_count = 0
        state.gaze_present = False
        print(
            f"[perception] vision={state.vision_status} acq={state.acquisition_freshness} "
            f"qlabel={state.quality_label} fq={state.frame_quality:.2f} recovery={state.recovery_state} "
            f"trusted=False id_conf=0.0 (suppress identity/emotion/scene-as-current)"
        )
        _apply_scene_summary_to_state(state, ss)
        _apply_interpretation_layer_to_state(state, il)
        _apply_perception_memory_to_state(state, pm)
        return state

    if not resolved.visual_truth_trusted:
        if resolved.vision_status == "stale_frame":
            state.face_status = "Stale or outdated camera frame"
            state.recognized_text = (
                "Frame is too old to treat as a current view — not using recognition as ground truth."
            )
        elif resolved.vision_status == "recovering":
            state.face_status = "Vision recovering (stabilizing)"
            state.recognized_text = (
                "Vision is recovering after an interruption — identity and expression are not trusted as current yet."
            )
        elif resolved.vision_status == "low_quality":
            rsn = ", ".join(state.frame_quality_reasons) or "quality"
            state.face_status = "Frame quality too low for a reliable read"
            state.recognized_text = (
                f"Image quality is weak ({rsn}) — not using identity or expression as ground truth yet."
            )
        else:
            state.face_status = "Vision unavailable"
            state.recognized_text = "No reliable visual read right now."
        state.face_identity = None
        state.face_emotion = None
        state.face_detected = False
        state.person_count = 0
        state.gaze_present = False
        _apply_continuity_structured_to_state(state, c)
        _apply_identity_resolution_to_state(state, idr)
        if state.last_stable_identity and state.continuity_confidence < 0.12:
            state.continuity_confidence = 0.12
        base = float(i.salience)
        state.salience = base
        _apply_salience_structured_to_state(state, i)
        print(
            f"[perception] vision={state.vision_status} qlabel={state.quality_label} "
            f"age_ms={state.frame_age_ms:.0f} src={state.frame_source} fq={state.frame_quality:.2f} "
            f"recovery={state.recovery_state} streak={state.fresh_frame_streak} trusted=False "
            f"id_conf=0.0 cont={state.continuity_confidence:.2f} "
            f"(suppress identity/emotion/scene-as-current)"
        )
        _apply_scene_summary_to_state(state, ss)
        _apply_interpretation_layer_to_state(state, il)
        _apply_perception_memory_to_state(state, pm)
        return state

    state.face_status = d.face_status
    state.face_detected = d.face_detected
    state.person_count = d.person_count
    state.gaze_present = d.gaze_present
    state.recognized_text = r.recognized_text
    state.face_identity = r.face_identity
    state.face_emotion = i.face_emotion

    _apply_continuity_structured_to_state(state, c)
    cr = c.structured
    _apply_identity_resolution_to_state(state, idr)

    if idr is not None and idr.resolved_identity:
        state.last_stable_identity = idr.resolved_identity
    if (
        idr is not None
        and state.face_detected
        and idr.identity_state == "unknown_face"
    ):
        state.identity_confidence = max(
            float(state.identity_confidence),
            0.22 * float(q.recognition_confidence_scale),
        )
    if cr is not None:
        state.continuity_confidence = max(
            float(state.continuity_confidence), float(cr.continuity_confidence)
        )
    if not state.face_detected and state.last_stable_identity:
        state.continuity_confidence = max(float(state.continuity_confidence), 0.14)

    # Interpretation / salience: structured combined scalar × quality expression × blur (interp).
    base_sal = float(i.salience)
    state.salience = (
        base_sal * q.quality_only_expression_scale * q.blur_interpretation_scale
    )
    _apply_salience_structured_to_state(state, i)
    _apply_scene_summary_to_state(state, ss)
    _apply_interpretation_layer_to_state(state, il)
    _apply_perception_memory_to_state(state, pm)
    print(
        f"[perception] vision={state.vision_status} acq={state.acquisition_freshness} "
        f"qlabel={state.quality_label} blur_label={state.blur_label} blur_val={state.blur_value:.1f} "
        f"age_ms={state.frame_age_ms:.0f} src={state.frame_source} "
        f"fq={state.frame_quality:.2f} recovery={state.recovery_state} streak={state.fresh_frame_streak} "
        f"trusted=True id_conf={state.identity_confidence:.2f} (rec_scale={q.recognition_confidence_scale:.2f}) "
        f"cont={state.continuity_confidence:.2f} id_state={state.identity_state} "
        f"resolved_id={state.resolved_face_identity!r} raw_id={state.face_identity!r} "
        f"salience={state.salience:.2f} top={state.salience_top_type}:{state.salience_top_label} "
        f"scene={state.scene_overall_state!r} interp={state.interpretation_primary_event!r} "
        f"(base={base_sal:.2f} expr_q={q.quality_only_expression_scale:.2f} blur_interp={q.blur_interpretation_scale:.2f})"
    )
    return state
