"""
InsightFace GPU face recognition engine.

Uses the buffalo_l model pack (RetinaFace detector + ArcFace embedding +
age/gender + 106-pt landmarks + 3D head pose). Runs on
CUDAExecutionProvider when available, falls back to CPU.

This engine is ADDITIVE: the existing FaceRecognizer (face_recognition lib)
remains the backwards-compatible fallback. When this engine is available
the background tick loop publishes detailed _face_results so the camera
annotator can draw bounding boxes, landmarks, head-pose axes, age, gender.

Bootstrap-friendly: no preferences are baked in. Confidence threshold for
positive ID is the only tunable, defaults to 0.45 cosine similarity.
"""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Any, Optional


_SIMILARITY_THRESHOLD = 0.45  # cosine sim ≥ this → positive ID

_SINGLETON: Optional["InsightFaceEngine"] = None
_SINGLETON_LOCK = threading.Lock()


class InsightFaceEngine:
    def __init__(self) -> None:
        self._app: Any = None
        self._known: dict[str, Any] = {}        # person_id -> avg embedding (np.ndarray)
        self._known_counts: dict[str, int] = {}  # photos seen per person
        self._lock = threading.Lock()
        self._available = False
        self._provider: str = "none"
        self._init_error: str = ""

    # ── lifecycle ──────────────────────────────────────────────────────────────

    def initialize(self, faces_dir: Path) -> bool:
        try:
            import onnxruntime as ort  # type: ignore
            from insightface.app import FaceAnalysis  # type: ignore
        except Exception as e:
            self._init_error = f"import: {e!r}"
            print(f"[insight_face] import failed: {e!r}")
            return False

        # Pick the best provider available.
        avail = list(ort.get_available_providers())
        ordered: list[str] = []
        if "CUDAExecutionProvider" in avail:
            ordered.append("CUDAExecutionProvider")
        ordered.append("CPUExecutionProvider")

        try:
            app = FaceAnalysis(name="buffalo_l", providers=ordered)
            app.prepare(ctx_id=0, det_size=(640, 640))
        except Exception as e:
            self._init_error = f"prepare: {e!r}"
            print(f"[insight_face] FaceAnalysis prepare failed: {e!r}")
            # Retry CPU-only if GPU prepare fails
            try:
                app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
                app.prepare(ctx_id=-1, det_size=(640, 640))
                ordered = ["CPUExecutionProvider"]
                self._init_error = ""
            except Exception as e2:
                self._init_error = f"prepare-cpu: {e2!r}"
                print(f"[insight_face] CPU prepare also failed: {e2!r}")
                return False

        self._app = app
        self._provider = ordered[0]
        self._load_faces(faces_dir)
        self._available = True
        print(f"[insight_face] ready provider={self._provider} known_people={len(self._known)}")
        return True

    def _load_faces(self, faces_dir: Path) -> None:
        try:
            import cv2  # type: ignore
            import numpy as np  # type: ignore
        except Exception as e:
            print(f"[insight_face] load deps missing: {e!r}")
            return
        if not faces_dir.is_dir():
            print(f"[insight_face] faces dir missing: {faces_dir}")
            return
        loaded = 0
        for person_dir in sorted(faces_dir.iterdir()):
            if not person_dir.is_dir():
                continue
            pid = person_dir.name
            embs: list[Any] = []
            for img_path in list(person_dir.glob("*.jpg")) + list(person_dir.glob("*.png")):
                try:
                    img = cv2.imread(str(img_path))
                    if img is None:
                        continue
                    faces = self._app.get(img)
                    if faces:
                        embs.append(faces[0].embedding)
                except Exception as e:
                    print(f"[insight_face] skip {img_path.name}: {e!r}")
            if embs:
                avg = np.mean(np.stack(embs, axis=0), axis=0)
                self._known[pid] = avg
                self._known_counts[pid] = len(embs)
                loaded += len(embs)
                print(f"[insight_face]   {pid}: {len(embs)} photos")
        print(f"[insight_face] loaded {loaded} embeddings from {len(self._known)} people")

    # ── runtime ────────────────────────────────────────────────────────────────

    def analyze_frame(self, frame: Any) -> list[dict[str, Any]]:
        """Return list of dicts: bbox, landmarks (106), pose, age, gender, person_id, confidence."""
        if not self._available or self._app is None or frame is None:
            return []
        try:
            with self._lock:
                faces = self._app.get(frame)
        except Exception as e:
            print(f"[insight_face] analyze error: {e!r}")
            return []

        results: list[dict[str, Any]] = []
        for f in faces:
            try:
                emb = getattr(f, "embedding", None)
                pid = "unknown"
                conf = 0.0
                if emb is not None:
                    pid, conf = self._match(emb)
                bbox = getattr(f, "bbox", None)
                landmark = getattr(f, "landmark_2d_106", None)
                pose = getattr(f, "pose", None)
                age = getattr(f, "age", None)
                gender = getattr(f, "gender", None)
                results.append({
                    "bbox": [int(v) for v in bbox.tolist()] if bbox is not None else [0, 0, 0, 0],
                    "landmarks": landmark.tolist() if landmark is not None else None,
                    "pose": pose.tolist() if pose is not None else [0.0, 0.0, 0.0],
                    "age": int(age) if age is not None else 0,
                    "gender": ("M" if int(gender) == 1 else "F") if gender is not None else "?",
                    "person_id": pid,
                    "confidence": float(conf),
                })
            except Exception as e:
                print(f"[insight_face] face decode error: {e!r}")
        return results

    def _match(self, emb: Any) -> tuple[str, float]:
        if not self._known:
            return "unknown", 0.0
        try:
            import numpy as np  # type: ignore
        except Exception:
            return "unknown", 0.0
        best_pid = "unknown"
        best_score = 0.0
        emb_norm = float(np.linalg.norm(emb)) or 1.0
        for pid, known in self._known.items():
            kn = float(np.linalg.norm(known)) or 1.0
            score = float(np.dot(emb, known) / (emb_norm * kn))
            if score > best_score:
                best_score = score
                best_pid = pid
        if best_score >= _SIMILARITY_THRESHOLD:
            return best_pid, best_score
        return "unknown", best_score

    def add_face(self, person_id: str, image: Any) -> bool:
        """Add a single face image to the known set; averaged into existing embedding."""
        if not self._available or self._app is None:
            return False
        try:
            import numpy as np  # type: ignore
            faces = self._app.get(image)
            if not faces:
                return False
            emb = faces[0].embedding
            with self._lock:
                if person_id in self._known:
                    n = self._known_counts.get(person_id, 1)
                    self._known[person_id] = (self._known[person_id] * n + emb) / (n + 1)
                    self._known_counts[person_id] = n + 1
                else:
                    self._known[person_id] = emb
                    self._known_counts[person_id] = 1
            return True
        except Exception as e:
            print(f"[insight_face] add_face error: {e!r}")
            return False

    # ── status ─────────────────────────────────────────────────────────────────

    @property
    def available(self) -> bool:
        return self._available

    def provider(self) -> str:
        return self._provider

    def known_count(self) -> int:
        return len(self._known)


# ── Module singleton ──────────────────────────────────────────────────────────

def get_insight_face() -> Optional[InsightFaceEngine]:
    """Return the singleton if it has been initialized, None otherwise."""
    return _SINGLETON


def bootstrap_insight_face(g: dict[str, Any]) -> Optional[InsightFaceEngine]:
    """Create and initialize the singleton. Stores result in g['_insight_face'].
    Returns the engine if init succeeded, None on failure."""
    global _SINGLETON
    with _SINGLETON_LOCK:
        if _SINGLETON is not None:
            g["_insight_face"] = _SINGLETON
            return _SINGLETON
        engine = InsightFaceEngine()
        base = Path(g.get("BASE_DIR") or ".")
        ok = engine.initialize(base / "faces")
        if ok:
            _SINGLETON = engine
            g["_insight_face"] = engine
            return engine
        g["_insight_face"] = None
        return None
