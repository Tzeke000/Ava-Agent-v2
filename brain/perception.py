"""
Unified perception from camera + user text.

Vision gating: identity, emotion, and present-tense scene claims require visual_truth_trusted
(camera layer: stable after fresh frames / recovery — see brain/camera.py).

Manual test plan matches brain/camera.py (obstruction → recovering → stable).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .shared import now_ts
from .vision import analyze_face_emotion


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
    # Freshness / recovery (Phase: stable vision gating)
    vision_status: str = "stable"
    frame_ts: float = 0.0
    frame_age_ms: float = -1.0
    frame_source: str = "none"
    frame_seq: int = 0
    is_fresh: bool = False
    fresh_frame_streak: int = 0
    visual_truth_trusted: bool = True


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
    state.fresh_frame_streak = getattr(camera_manager, "_fresh_frame_streak", 0)
    state.visual_truth_trusted = resolved.visual_truth_trusted

    if resolved.frame is None:
        state.face_status = "No camera image"
        state.recognized_text = "No frame — cannot assess the scene as current."
        state.face_detected = False
        state.person_count = 0
        state.gaze_present = False
        print(
            f"[perception] vision={state.vision_status} trusted=False "
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
        else:
            state.face_status = "Vision unavailable"
            state.recognized_text = "No reliable visual read right now."
        state.face_identity = None
        state.face_emotion = None
        state.face_detected = False
        state.person_count = 0
        state.gaze_present = False
        state.salience = _compute_salience(state)
        print(
            f"[perception] vision={state.vision_status} age_ms={state.frame_age_ms:.0f} "
            f"src={state.frame_source} streak={state.fresh_frame_streak} trusted=False "
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

    state.salience = _compute_salience(state)
    print(
        f"[perception] vision={state.vision_status} age_ms={state.frame_age_ms:.0f} "
        f"src={state.frame_source} streak={state.fresh_frame_streak} trusted=True "
        f"(recognition/emotion allowed)"
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
