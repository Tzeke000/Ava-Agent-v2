"""
Camera capture, face utilities, and frame freshness / recovery gating.

Manual test plan (obstruction / recovery):
- Normal: unobstructed camera → vision_status stable quickly, recognition/emotion allowed.
- Cover lens several seconds → no_frame or stale_frame, low trust, no confident identity.
- Uncover 1–2 ticks only → recovering (or stale if cache age high), uncertain wording.
- Uncover and hold 3+ consecutive fresh frames → stable, trusted pipeline resumes.

Do not diagnose UI/Gradio refresh failures from vision alone — there is no UI-health signal here.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2

from .camera_live import read_live_frame

# Frames older than this (ms) are not treated as current evidence.
STALE_FRAME_MS = 1000
# After blockage/stale, require this many consecutive fresh frames before "stable".
FRESH_STREAK_FOR_STABLE = 3


@dataclass
class ResolvedFrame:
    """Single resolved frame with freshness metadata for vision gating."""

    frame: Any
    frame_ts: float  # wall time when frame was captured (or UI submit time)
    frame_age_ms: float
    source: str  # "ui" | "live" | "none"
    frame_seq: int
    frame_fp: int  # cheap content fingerprint (0 if no frame)
    is_fresh: bool
    vision_status: str  # no_frame | stale_frame | recovering | stable
    visual_truth_trusted: bool  # if True, perception may use identity/emotion as current


@dataclass
class CameraState:
    frame: Any = None
    face_status: str = "No camera image"
    recognized_text: str = "No camera image"
    person_id: str | None = None
    source: str = "ui"
    live_used: bool = False


class CameraManager:
    def __init__(self, device_index: int = 0):
        self.device_index = device_index
        self._frame_seq = 0
        self._fresh_frame_streak = 0
        self._recovery_armed = False
        self._last_ui_fp: int | None = None
        self._last_ui_wall_ts = 0.0

    @staticmethod
    def _frame_fp(frame: Any) -> int:
        if frame is None:
            return 0
        try:
            import numpy as np

            if isinstance(frame, np.ndarray) and frame.size:
                flat = frame.reshape(-1)
                step = max(1, flat.size // 8000)
                return hash(flat[::step].tobytes())
        except Exception:
            pass
        return hash(id(frame))

    def resolve_frame_detailed(self, image=None) -> ResolvedFrame:
        """
        Resolve frame and compute vision_status / trust for downstream perception.

        last-known-good cached live frames can be stale by age; UI frames use a
        fingerprint so a paused duplicate image accrues age across ticks.
        """
        t_wall = time.time()
        self._frame_seq += 1
        seq = self._frame_seq

        if image is not None:
            frame = image
            fp = self._frame_fp(frame)
            if fp != self._last_ui_fp:
                self._last_ui_fp = fp
                self._last_ui_wall_ts = t_wall
                frame_age_ms = 0.0
            else:
                frame_age_ms = max(0.0, (t_wall - self._last_ui_wall_ts) * 1000.0)
            cap_ts = t_wall
            source = "ui"
            live_used = False
        else:
            frame, cap_ts = read_live_frame()
            if frame is None:
                source = "none"
                live_used = False
                frame_age_ms = float("inf")
                cap_ts = 0.0
            else:
                source = "live"
                live_used = True
                frame_age_ms = max(0.0, (t_wall - float(cap_ts)) * 1000.0)

        fp_val = self._frame_fp(frame) if frame is not None else 0
        is_fresh = frame is not None and frame_age_ms <= STALE_FRAME_MS

        if frame is None:
            vision_status = "no_frame"
            self._fresh_frame_streak = 0
            self._recovery_armed = True
        elif not is_fresh:
            vision_status = "stale_frame"
            self._fresh_frame_streak = 0
            self._recovery_armed = True
        else:
            if self._recovery_armed:
                self._fresh_frame_streak += 1
                if self._fresh_frame_streak >= FRESH_STREAK_FOR_STABLE:
                    vision_status = "stable"
                    self._recovery_armed = False
                else:
                    vision_status = "recovering"
            else:
                vision_status = "stable"
                self._fresh_frame_streak = FRESH_STREAK_FOR_STABLE

        trusted = vision_status == "stable"

        if frame is None:
            age_ms_out = -1.0
            ts_out = 0.0
        else:
            ts_out = float(cap_ts) if cap_ts else t_wall
            age_ms_out = (
                frame_age_ms if frame_age_ms != float("inf") else 999999.0
            )

        print(
            f"[camera] src={source} age_ms={age_ms_out:.0f} "
            f"vision={vision_status} streak={self._fresh_frame_streak} trusted={trusted} seq={seq}"
        )

        return ResolvedFrame(
            frame=frame,
            frame_ts=ts_out,
            frame_age_ms=age_ms_out,
            source=source,
            frame_seq=seq,
            frame_fp=fp_val,
            is_fresh=is_fresh,
            vision_status=vision_status,
            visual_truth_trusted=trusted,
        )

    def resolve_frame(self, image=None):
        """Backward-compatible (frame, source, live_used). Prefer resolve_frame_detailed for gating."""
        r = self.resolve_frame_detailed(image)
        src = "none" if r.source == "none" else r.source
        return r.frame, src, r.source == "live"

    def is_recovering(self) -> bool:
        return self._recovery_armed

    def get_face_recognizer(self, g: dict):
        recognizer = g.get("face_recognizer")
        if recognizer is None:
            if hasattr(cv2, "face") and hasattr(cv2.face, "LBPHFaceRecognizer_create"):
                recognizer = cv2.face.LBPHFaceRecognizer_create()
                g["face_recognizer"] = recognizer
            else:
                return None
        return recognizer

    def load_face_labels(self, g: dict):
        path = g.get("FACE_LABELS_PATH")
        if not path:
            return {}
        labels = {}
        try:
            p = Path(path)
            if p.exists():
                import json

                raw = json.loads(p.read_text(encoding="utf-8"))
                labels = {int(k): v for k, v in raw.items()}
        except Exception as e:
            print(f"Face labels load error: {e}")
        g["face_labels"] = labels
        return labels

    def save_face_labels(self, g: dict):
        path = g.get("FACE_LABELS_PATH")
        labels = g.get("face_labels", {})
        if not path:
            return
        try:
            import json

            p = Path(path)
            p.write_text(
                json.dumps({str(k): v for k, v in labels.items()}, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as e:
            print(f"Face labels save error: {e}")

    def detect_face(self, image, g: dict):
        if image is None:
            return "No camera image"
        try:
            cascade = g.get("face_cascade")
            if cascade is None:
                return "Face detection unavailable"
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            faces = cascade.detectMultiScale(gray, 1.3, 5)
            return "Face detected" if len(faces) > 0 else "No face detected"
        except Exception as e:
            return f"Face detection error: {e}"

    def extract_face_crop(self, image, g: dict):
        if image is None:
            return None
        try:
            cascade = g.get("face_cascade")
            if cascade is None:
                return None
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            faces = cascade.detectMultiScale(gray, 1.3, 5)
            if len(faces) == 0:
                return None
            x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
            crop = gray[y : y + h, x : x + w]
            return cv2.resize(crop, (200, 200))
        except Exception:
            return None

    def capture_face_sample(self, image, person_id: str, g: dict) -> str:
        crop = self.extract_face_crop(image, g)
        if crop is None:
            return "❌ No face detected in snapshot."
        faces_dir = Path(g.get("FACES_DIR", "faces"))
        person_dir = faces_dir / person_id
        person_dir.mkdir(parents=True, exist_ok=True)
        filename = person_dir / f"{int(__import__('time').time() * 1000)}.png"
        try:
            cv2.imwrite(str(filename), crop)
            return f"✅ Saved face sample for {person_id}: {filename.name}"
        except Exception as e:
            return f"❌ Failed to save face sample: {e}"

    def train_face_recognizer(self, g: dict) -> str:
        recognizer = self.get_face_recognizer(g)
        if recognizer is None:
            return "❌ OpenCV face recognizer is unavailable. Install opencv-contrib-python in this venv."
        faces_dir = Path(g.get("FACES_DIR", "faces"))
        face_labels = g.get("face_labels", {})
        images, labels, label_map = [], [], {}
        label_counter = 0
        for person_dir in sorted(faces_dir.iterdir()) if faces_dir.exists() else []:
            if not person_dir.is_dir():
                continue
            person_id = person_dir.name
            files = (
                list(person_dir.glob("*.png"))
                + list(person_dir.glob("*.jpg"))
                + list(person_dir.glob("*.jpeg"))
            )
            if not files:
                continue
            label_map[label_counter] = person_id
            for file in files:
                try:
                    img = cv2.imread(str(file), cv2.IMREAD_GRAYSCALE)
                    if img is None:
                        continue
                    img = cv2.resize(img, (200, 200))
                    images.append(img)
                    labels.append(label_counter)
                except Exception:
                    continue
            label_counter += 1
        if not images:
            return "❌ No face samples found to train."
        try:
            import numpy as np

            recognizer.train(images, np.array(labels))
            model_path = Path(g.get("FACE_MODEL_PATH", "state/face_model.yml"))
            model_path.parent.mkdir(parents=True, exist_ok=True)
            recognizer.write(str(model_path))
            g["face_labels"] = label_map
            self.save_face_labels(g)
            return f"✅ Trained face recognizer on {len(images)} images across {len(label_map)} people."
        except Exception as e:
            return f"❌ Face training failed: {e}"

    def recognize_face(self, image, g: dict):
        recognizer = self.get_face_recognizer(g)
        if recognizer is None:
            return "Facial recognition unavailable in this OpenCV build", None
        model_path = Path(g.get("FACE_MODEL_PATH", "state/face_model.yml"))
        if not model_path.exists():
            return "Face model not trained", None
        crop = self.extract_face_crop(image, g)
        if crop is None:
            return "No face detected", None
        try:
            recognizer.read(str(model_path))
        except Exception:
            pass
        face_labels = g.get("face_labels") or self.load_face_labels(g)
        threshold = float(g.get("FACE_RECOGNITION_THRESHOLD", 80.0))
        try:
            label, confidence = recognizer.predict(crop)
            person_id = face_labels.get(int(label))
            if person_id is None:
                return f"Unknown face ({confidence:.1f})", None
            if confidence <= threshold:
                load_profile_by_id = g.get("load_profile_by_id")
                if callable(load_profile_by_id):
                    try:
                        profile = load_profile_by_id(person_id)
                        return f"Recognized: {profile.get('name', person_id)} ({confidence:.1f})", person_id
                    except Exception:
                        pass
                return f"Recognized: {person_id} ({confidence:.1f})", person_id
            return f"Unknown face ({confidence:.1f})", None
        except Exception as e:
            return f"Recognition error: {e}", None

    def analyze(self, image, g: dict) -> CameraState:
        r = self.resolve_frame_detailed(image)
        state = CameraState(frame=r.frame, source=r.source, live_used=r.source == "live")
        if r.frame is None:
            return state
        if not r.visual_truth_trusted:
            state.face_status = (
                "No camera image"
                if r.vision_status == "no_frame"
                else (
                    "Stale or outdated camera frame"
                    if r.vision_status == "stale_frame"
                    else "Vision stabilizing (not a current read yet)"
                )
            )
            state.recognized_text = "Recognition held — vision not stable"
            state.person_id = None
            return state
        state.face_status = self.detect_face(r.frame, g)
        state.recognized_text, state.person_id = self.recognize_face(r.frame, g)
        return state
