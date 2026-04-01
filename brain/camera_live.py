import time
try:
    import cv2
except Exception:
    cv2 = None

_last = {"ts": 0.0, "frame": None}


def read_live_frame(max_age: float = 1.5):
    now = time.time()
    if _last["frame"] is not None and now - _last["ts"] <= max_age:
        return _last["frame"]
    if cv2 is None:
        return None
    cap = cv2.VideoCapture(0)
    if not cap or not cap.isOpened():
        return None
    try:
        ok, frame = cap.read()
    finally:
        cap.release()
    if ok and frame is not None:
        _last["frame"] = frame
        _last["ts"] = now
        return frame
    return None
