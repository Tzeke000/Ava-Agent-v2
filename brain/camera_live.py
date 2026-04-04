"""
Low-level live camera read with a short-lived frame cache.

Manual test plan (obstruction / recovery) — see brain/camera.py module docstring.
"""
import time

try:
    import cv2
except Exception:
    cv2 = None

_last = {"ts": 0.0, "frame": None}


def read_live_frame(max_age: float = 1.5):
    """
    Returns (frame_bgr_or_none, capture_wall_time).

    capture_wall_time is when this frame was produced (or last read from device).
    When serving a cached frame within max_age, returns the original capture time
    so callers can compute true age vs wall clock.
    """
    now = time.time()
    if _last["frame"] is not None and now - _last["ts"] <= max_age:
        return _last["frame"], float(_last["ts"])
    if cv2 is None:
        print("[camera_live] cv2 unavailable (import failed)")
        return None, 0.0
    cap = cv2.VideoCapture(0)
    if not cap or not cap.isOpened():
        print("[camera_live] VideoCapture(0) failed or not opened")
        return None, 0.0
    try:
        ok, frame = cap.read()
    finally:
        cap.release()
    if ok and frame is not None:
        _last["frame"] = frame
        _last["ts"] = now
        return frame, now
    print("[camera_live] live read returned no frame (device read failed or empty)")
    return None, 0.0
