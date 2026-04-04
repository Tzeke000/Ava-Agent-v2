"""
Unified perception from camera + user text.

Vision gating: identity, emotion, and present-tense scene claims require visual_truth_trusted
(camera layer: stable after fresh frames / recovery — see brain/camera.py).

Manual test plan matches brain/camera.py (obstruction → recovering → stable).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .shared import now_ts
from .vision import analyze_face_emotion


def _lbph_distance_to_identity_confidence(recognized_text: str, threshold: float = 80.0) -> float:
    """Map LBPH distance in parentheses to [0,1]; higher = stronger match signal."""
    m = re.search(r"\((\d+\.?\d*)\)\s*$", (recognized_text or "").strip())
    if not m:
        return 0.45
    dist = float(m.group(1))
    if dist <= threshold:
        return max(0.35, min(1.0, 1.0 - (dist / (threshold * 2.2))))
    return max(0.0, 0.25 * (1.0 - min(1.0, (dist - threshold) / 80.0)))


@dataclass
class PerceptionState:
    frame: Any = None
    face_detected: bool = False
    face_identity: str | None = None
    face_emotion: str | None = None
    gaze_present: bool = False
    person_count: int = 0
    user_text: str = ""
    salience: float = 0.2
    timestamp: float = field(default_factory=now_ts)
    face_status: str = "No camera image"
    recognized_text: str = ""
    # Better Eyes E1 — first-class vision / trust (see brain/camera.py)
    vision_status: str = "stable"
    frame_ts: float = 0.0
    frame_age_ms: float = -1.0
    frame_source: str = "none"
    frame_seq: int = 0
    is_fresh: bool = False
    fresh_frame_streak: int = 0
    visual_truth_trusted: bool = True
    frame_quality: float = 0.0
    frame_quality_reasons: list[str] = field(default_factory=list)
    recovery_state: str = "none"
    last_stable_identity: str | None = None
    identity_confidence: float = 0.0
    continuity_confidence: float = 0.0


def build_perception(camera_manager, image, g: dict, user_text: str = "") -> PerceptionState:
    """
    Build PerceptionState from camera + user input.
    When vision is not stable, do not treat identity/emotion as current truth.
    """
    state = PerceptionState(user_text=user_text or "", timestamp=now_ts())

    try:
        resolved = camera_manager.resolve_frame_detailed(image)
    except Exception:
        return state

    state.frame = resolved.frame
    state.vision_status = resolved.vision_status
    state.frame_ts = resolved.frame_ts
    state.frame_age_ms = resolved.frame_age_ms
    state.frame_source = resolved.source
    state.frame_seq = resolved.frame_seq
    state.is_fresh = resolved.is_fresh
    state.fresh_frame_streak = resolved.fresh_frame_streak
    state.visual_truth_trusted = resolved.visual_truth_trusted
    state.frame_quality = resolved.frame_quality
    state.frame_quality_reasons = list(resolved.frame_quality_reasons)
    state.recovery_state = resolved.recovery_state
    state.last_stable_identity = resolved.last_stable_identity
    state.identity_confidence = 0.0
    state.continuity_confidence = 0.0

    if resolved.frame is None:
        state.face_status = "No camera image"
        state.recognized_text = "No frame — cannot assess the scene as current."
        state.face_detected = False
        state.person_count = 0
        state.gaze_present = False
        print(
            f"[perception] vision={state.vision_status} fq={state.frame_quality:.2f} "
            f"recovery={state.recovery_state} trusted=False id_conf=0.0 "
            f"(suppress identity/emotion/scene-as-current)"
        )
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
        if state.last_stable_identity:
            state.continuity_confidence = 0.12
        state.salience = _compute_salience(state)
        print(
            f"[perception] vision={state.vision_status} age_ms={state.frame_age_ms:.0f} "
            f"src={state.frame_source} fq={state.frame_quality:.2f} recovery={state.recovery_state} "
            f"streak={state.fresh_frame_streak} trusted=False id_conf=0.0 cont={state.continuity_confidence:.2f} "
            f"(suppress identity/emotion/scene-as-current)"
        )
        return state

    try:
        state.face_status = camera_manager.detect_face(resolved.frame, g)
    except Exception:
        state.face_status = "No camera image"

    try:
        cascade = g.get("face_cascade")
        if cascade is not None:
            import cv2

            gray = cv2.cvtColor(resolved.frame, cv2.COLOR_BGR2GRAY)
            faces = cascade.detectMultiScale(gray, 1.3, 5)
            state.person_count = len(faces)
            state.face_detected = state.person_count > 0
            state.gaze_present = state.face_detected
    except Exception:
        pass

    try:
        state.recognized_text, state.face_identity = camera_manager.recognize_face(resolved.frame, g)
    except Exception:
        pass

    try:
        if state.face_detected:
            state.face_emotion = analyze_face_emotion(resolved.frame)
    except Exception:
        state.face_emotion = "neutral"

    if state.face_identity:
        state.identity_confidence = _lbph_distance_to_identity_confidence(state.recognized_text)
        try:
            camera_manager.note_trusted_identity(state.face_identity)
        except Exception:
            pass
        state.last_stable_identity = state.face_identity
        state.continuity_confidence = state.identity_confidence
    elif state.face_detected:
        state.identity_confidence = 0.22
        state.continuity_confidence = 0.18 if state.last_stable_identity else 0.0
    else:
        state.identity_confidence = 0.0
        state.continuity_confidence = 0.15 if state.last_stable_identity else 0.0

    state.salience = _compute_salience(state)
    print(
        f"[perception] vision={state.vision_status} age_ms={state.frame_age_ms:.0f} "
        f"src={state.frame_source} fq={state.frame_quality:.2f} recovery={state.recovery_state} "
        f"streak={state.fresh_frame_streak} trusted=True id_conf={state.identity_confidence:.2f} "
        f"cont={state.continuity_confidence:.2f} (recognition/emotion allowed)"
    )
    return state


def _compute_salience(state: PerceptionState) -> float:
    if not state.face_detected:
        return 0.2
    em = (state.face_emotion or "").lower()
    if em in ("angry", "fear", "disgust"):
        return 1.0
    if state.user_text:
        return 0.9
    return 0.6
