from __future__ import annotations

from typing import Any

try:
    import cv2  # type: ignore
except Exception:
    cv2 = None


class CameraManager:
    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled and cv2 is not None
        self.cap = None
        if self.enabled:
            try:
                self.cap = cv2.VideoCapture(0)
            except Exception:
                self.cap = None
                self.enabled = False

    def snapshot_truth(self) -> dict[str, Any]:
        if not self.enabled or self.cap is None:
            return {'camera_enabled': False, 'status': 'disabled_or_unavailable', 'face_detected': False, 'recognition_confidence': 0.0}
        ok, _frame = self.cap.read()
        if not ok:
            return {'camera_enabled': True, 'status': 'no_fresh_frame', 'face_detected': False, 'recognition_confidence': 0.0}
        return {'camera_enabled': True, 'status': 'fresh_frame', 'face_detected': True, 'recognition_confidence': 0.2}
