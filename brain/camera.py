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
from typing import Any, Optional

import cv2

from .frame_quality import assess_frame_quality_basic, compute_frame_quality
from .frame_store import (
    LIVE_CACHE_MAX_AGE_SEC,
    classify_acquisition_freshness,
    read_live_frame_with_meta,
)

# Frames older than this (ms) are not treated as current evidence.
STALE_FRAME_MS = 1000
# After blockage/stale, require this many consecutive fresh frames before "stable".
FRESH_STREAK_FOR_STABLE = 3
# Below this aggregate quality score [0,1], vision is "low_quality" (E1 minimal heuristic; E3 expands).
LOW_QUALITY_THRESHOLD = 0.28


@dataclass
class ResolvedFrame:
    """Single resolved frame with freshness + quality metadata for vision gating (Better Eyes E1)."""

    frame: Any
    frame_ts: float  # wall time when frame was captured (or UI submit time)
    frame_age_ms: float
    source: str  # "ui" | "live" | "none"
    frame_seq: int
    frame_fp: int  # cheap content fingerprint (0 if no frame)
    is_fresh: bool
    vision_status: str  # no_frame | stale_frame | recovering | stable | low_quality
    visual_truth_trusted: bool  # if True, perception may use identity/emotion as current
    frame_quality: float  # [0, 1]
    frame_quality_reasons: list[str]
    recovery_state: str  # none | needs_fresh | clearing | quality_hold
    fresh_frame_streak: int
    last_stable_identity: str | None  # last trusted recognition person_id (continuity; E4 extends)
    # Phase 2 acquisition layer: fresh | aging | stale | unavailable (live cache vs UI age)
    acquisition_freshness: str = "unavailable"
    # Phase 4 structured quality (same overall as frame_quality; see brain.frame_quality)
    quality_detail: Optional[Any] = None


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
        self._last_stable_person_id: str | None = None
        self._last_stable_wall_ts: float = 0.0

    def note_trusted_identity(self, person_id: str | None) -> None:
        """Call when a frame is visually trusted and recognition yields a known person."""
        if person_id:
            self._last_stable_person_id = person_id
            self._last_stable_wall_ts = time.time()

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
            acquisition_freshness = classify_acquisition_freshness(
                True,
                frame_age_ms / 1000.0,
            )
        else:
            meta = read_live_frame_with_meta(
                max_age=LIVE_CACHE_MAX_AGE_SEC,
                device_index=self.device_index,
            )
            frame = meta.frame
            cap_ts = float(meta.capture_ts) if meta.frame is not None else 0.0
            if frame is None:
                source = "none"
                live_used = False
                frame_age_ms = float("inf")
                cap_ts = 0.0
                acquisition_freshness = "unavailable"
            else:
                source = "live"
                live_used = True
                frame_age_ms = max(0.0, (t_wall - float(cap_ts)) * 1000.0)
                # Prefer store classification; re-classify if wall age drifted vs meta.age_sec
                acquisition_freshness = classify_acquisition_freshness(
                    True,
                    frame_age_ms / 1000.0,
                )

        fp_val = self._frame_fp(frame) if frame is not None else 0
        is_fresh = frame is not None and frame_age_ms <= STALE_FRAME_MS
        if frame is not None:
            fq_detail = compute_frame_quality(frame)
            frame_quality = fq_detail.overall_quality_score
            frame_quality_reasons = list(fq_detail.reason_flags)
        else:
            fq_detail = None
            frame_quality, frame_quality_reasons = 0.0, ["no_frame"]

        if frame is None:
            vision_status = "no_frame"
            self._fresh_frame_streak = 0
            self._recovery_armed = True
        elif not is_fresh:
            vision_status = "stale_frame"
            self._fresh_frame_streak = 0
            self._recovery_armed = True
        elif frame_quality < LOW_QUALITY_THRESHOLD:
            # Fresh but unusable for confident vision — same recovery semantics as dropout.
            vision_status = "low_quality"
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

        if vision_status == "stable" and trusted:
            recovery_state = "none"
        elif vision_status == "recovering":
            recovery_state = "clearing"
        elif vision_status == "low_quality":
            recovery_state = "quality_hold"
        elif vision_status in ("no_frame", "stale_frame"):
            recovery_state = "needs_fresh"
        else:
            recovery_state = "needs_fresh"

        if frame is None:
            age_ms_out = -1.0
            ts_out = 0.0
            acquisition_freshness = "unavailable"
        else:
            ts_out = float(cap_ts) if cap_ts else t_wall
            age_ms_out = (
                frame_age_ms if frame_age_ms != float("inf") else 999999.0
            )

        fq_s = f"{frame_quality:.2f}"
        rsn = ",".join(frame_quality_reasons) if frame_quality_reasons else "-"
        ql = getattr(fq_detail, "quality_label", "-") if fq_detail else "-"
        print(
            f"[camera] src={source} age_ms={age_ms_out:.0f} acq={acquisition_freshness} "
            f"fq={fq_s} qlabel={ql} fq_r={rsn} vision={vision_status} recovery={recovery_state} "
            f"streak={self._fresh_frame_streak} trusted={trusted} seq={seq} "
            f"last_id={self._last_stable_person_id or '-'}"
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
            frame_quality=frame_quality,
            frame_quality_reasons=list(frame_quality_reasons),
            recovery_state=recovery_state,
            fresh_frame_streak=self._fresh_frame_streak,
            last_stable_identity=self._last_stable_person_id,
            acquisition_freshness=acquisition_freshness,
            quality_detail=fq_detail,
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
            if r.vision_status == "no_frame":
                msg = "No camera image"
            elif r.vision_status == "stale_frame":
                msg = "Stale or outdated camera frame"
            elif r.vision_status == "low_quality":
                msg = "Frame quality too low for a reliable read"
            elif r.vision_status == "recovering":
                msg = "Vision stabilizing (not a current read yet)"
            else:
                msg = "Vision unavailable"
            state.face_status = msg
            state.recognized_text = "Recognition held — vision not stable"
            state.person_id = None
            return state
        state.face_status = self.detect_face(r.frame, g)
        state.recognized_text, state.person_id = self.recognize_face(r.frame, g)
        return state
