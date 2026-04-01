from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

from .shared import now_ts


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


def build_perception(camera_manager, image, g: dict, user_text: str = "") -> PerceptionState:
    """
    Build a unified PerceptionState from camera + user input.
    This is called once per camera_tick_fn and once per chat_fn.
    Never raises — always returns a valid PerceptionState.
    """
    state = PerceptionState(user_text=user_text or "", timestamp=now_ts())

    try:
        frame, _source, _live_used = camera_manager.resolve_frame(image)
        state.frame = frame
    except Exception:
        return state

    if frame is None:
        return state

    try:
        state.face_status = camera_manager.detect_face(frame, g)
    except Exception:
        state.face_status = "No camera image"

    try:
        cascade = g.get("face_cascade")
        if cascade is not None:
            import cv2

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = cascade.detectMultiScale(gray, 1.3, 5)
            state.person_count = len(faces)
            state.face_detected = state.person_count > 0
            state.gaze_present = state.face_detected
    except Exception:
        pass

    try:
        state.recognized_text, state.face_identity = camera_manager.recognize_face(frame, g)
    except Exception:
        pass

    try:
        if state.face_detected:
            from deepface import DeepFace

            result = DeepFace.analyze(
                frame, actions=["emotion"], enforce_detection=False, silent=True
            )
            if isinstance(result, list):
                result = result[0] if result else {}
            else:
                result = result or {}
            dom = result.get("dominant_emotion")
            state.face_emotion = (str(dom).lower() if dom else "neutral")
    except Exception:
        state.face_emotion = "neutral"

    state.salience = _compute_salience(state)
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
