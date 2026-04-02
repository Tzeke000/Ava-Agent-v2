"""
Face emotion via DeepFace in a Python 3.12 subprocess (host may run 3.14+).
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from typing import Any

import cv2


def _analyze_face_emotion_raw(frame_bgr) -> dict[str, Any] | None:
    if frame_bgr is None:
        return None
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp_path = tmp.name
        cv2.imwrite(tmp_path, frame_bgr)
        img_literal = json.dumps(tmp_path)
        script = (
            "from deepface import DeepFace; import json; "
            "p = " + img_literal + "; "
            "r = DeepFace.analyze(img_path=p, actions=['emotion'], "
            "detector_backend='skip', enforce_detection=False, silent=True); "
            "r = r[0] if isinstance(r, list) else r; "
            "print(json.dumps({'dominant': r.get('dominant_emotion', 'neutral'), 'emotions': r.get('emotion', {})}))"
        )
        res = subprocess.run(
            ["py", "-3.12", "-c", script],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if res.returncode != 0 or not res.stdout.strip():
            return None
        return json.loads(res.stdout.strip())
    except Exception:
        return None
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass


def analyze_face_emotion(frame_bgr) -> str:
    """
    Return dominant emotion label (lowercase), or \"neutral\" if unavailable.
    `frame_bgr` is a BGR numpy image (OpenCV).
    """
    r = _analyze_face_emotion_raw(frame_bgr)
    if not r:
        return "neutral"
    dom = r.get("dominant") or "neutral"
    return str(dom).lower() if dom else "neutral"


def analyze_face_emotion_detailed(frame_bgr) -> dict[str, Any] | None:
    """Dominant label + raw emotion scores dict, or None on failure."""
    return _analyze_face_emotion_raw(frame_bgr)
