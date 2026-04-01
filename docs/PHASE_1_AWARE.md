# Ava — Phase 1: AWARE
## Level 1 of 5 — Perceptual Awareness
### Feed this to Cursor first. Complete and test before moving to Phase 2.

---

## Context — What Ava Already Has

The overlay/monkey-patch pattern is fully removed. `avaagent.py` is 6,397 lines and uses direct imports.
These modules already exist and work — do NOT rewrite them:
- `brain/camera.py` — face detection, recognition, training via OpenCV LBPH ✅
- `brain/shared.py` — utility functions ✅
- `brain/health.py` — system health + behavior modifiers ✅
- `brain/goals.py` — goal blending ✅
- `brain/trust_manager.py` — trust levels per person ✅

The current `brain/perception.py` is only 24 lines and is a stub/bridge. It needs to become a real module.

---

## Goal of This Phase

Replace the stub `brain/perception.py` with a real `PerceptionState` dataclass and `build_perception()` function.
This becomes the single unified snapshot of what Ava currently sees and senses.
Every later phase depends on this output.

---

## What to Build

### 1. Rewrite `brain/perception.py`

Replace the entire file with the following:

```python
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
import time

from .shared import now_ts

@dataclass
class PerceptionState:
    frame: Any = None                  # raw camera frame (numpy array or None)
    face_detected: bool = False        # is a face visible in frame
    face_identity: str | None = None   # recognized person_id or None
    face_emotion: str | None = None    # "happy","neutral","angry","surprised","sad","fear","disgust"
    gaze_present: bool = False         # face is roughly facing the camera
    person_count: int = 0              # total faces detected this frame
    user_text: str = ""                # latest message text (empty string if none)
    salience: float = 0.2              # 0.0–1.0 — how much attention this moment deserves
    timestamp: float = field(default_factory=time.time)


def build_perception(camera_manager, image, g: dict, user_text: str = "") -> PerceptionState:
    """
    Build a unified PerceptionState from camera + user input.
    This is called once per camera_tick_fn and once per chat_fn.
    Never raises — always returns a valid PerceptionState.
    """
    state = PerceptionState(user_text=user_text, timestamp=time.time())

    # --- Resolve frame ---
    try:
        frame, source, live_used = camera_manager.resolve_frame(image)
        state.frame = frame
    except Exception:
        return state  # no frame, return minimal state

    if frame is None:
        return state

    # --- Face detection + count ---
    try:
        cascade = g.get('face_cascade')
        if cascade is not None:
            import cv2
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = cascade.detectMultiScale(gray, 1.3, 5)
            state.person_count = len(faces)
            state.face_detected = state.person_count > 0
            state.gaze_present = state.face_detected  # approximation — face visible = roughly present
    except Exception:
        pass

    # --- Face identity (uses existing camera_manager) ---
    try:
        if state.face_detected:
            _, person_id = camera_manager.recognize_face(frame, g)
            state.face_identity = person_id
    except Exception:
        pass

    # --- Face emotion via DeepFace ---
    try:
        if state.face_detected:
            from deepface import DeepFace
            result = DeepFace.analyze(frame, actions=['emotion'], enforce_detection=False, silent=True)
            state.face_emotion = result[0]['dominant_emotion']
    except Exception:
        state.face_emotion = "neutral"

    # --- Salience score ---
    state.salience = _compute_salience(state)

    return state


def _compute_salience(state: PerceptionState) -> float:
    if not state.face_detected:
        return 0.2
    if state.face_emotion in ('angry', 'fear', 'disgust'):
        return 1.0
    if state.user_text:
        return 0.9
    return 0.6
```

### 2. Wire into `avaagent.py` — `camera_tick_fn`

Find `def camera_tick_fn` in `avaagent.py`. At the very top of the function body, replace the existing `camera_manager.analyze(image, globals())` call with:

```python
from brain.perception import build_perception
perception = build_perception(camera_manager, image, globals(), "")
```

Then use `perception.face_detected`, `perception.face_identity`, `perception.face_emotion`, `perception.person_count` wherever the old `CameraState` fields were used.

### 3. Wire into `avaagent.py` — `chat_fn`

Find `def chat_fn` in `avaagent.py`. At the top, replace the `camera_manager.analyze(image, globals())` call with:

```python
from brain.perception import build_perception
perception = build_perception(camera_manager, image, globals(), message)
```

### 4. Add `deepface` to `requirements.txt`

```
deepface
tf-keras
```

---

## Definition of Done

- `brain/perception.py` no longer contains bridge/delegate code
- Every camera tick prints something like: `[perception] face=True emotion=happy salience=0.9`
- `chat_fn` and `camera_tick_fn` both use `PerceptionState` instead of `CameraState`
- DeepFace emotion runs without crashing (defaults to "neutral" on any error)
- All existing face detection and recognition behavior is preserved

---

## Do NOT Change

- `brain/camera.py` — leave it exactly as is
- The face training / capture / recognize UI buttons — they call `camera_manager` directly, leave them
- Any memory, profile, trust, health, or goals logic

---

## What Comes Next

Phase 2 uses `PerceptionState` as its input. Do not start Phase 2 until `build_perception()` is confirmed working.
