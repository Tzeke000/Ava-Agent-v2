"""
Periodic background ticks for systems that need to run independently of conversation.

- Heartbeat tick every 30s (so snapshot has fresh heartbeat data without chat activity)
- Video frame capture every ~67ms (15 fps) — feeds the VideoMemory rolling buffer
- All threads are daemon, all calls are wrapped in try/except.
"""
from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any

_HB_INTERVAL = 30.0
_VIDEO_INTERVAL = 1.0 / 15.0  # 15 fps


def _heartbeat_loop(g: dict[str, Any]) -> None:
    while True:
        time.sleep(_HB_INTERVAL)
        try:
            from brain.heartbeat import run_heartbeat_tick_safe, apply_heartbeat_to_perception_state
            from brain.perception import PerceptionState
            workspace = g.get("workspace")
            # Run a lightweight heartbeat tick — no perception args needed (all None ok)
            hb = run_heartbeat_tick_safe(
                g=g, user_text="",
                selftests=None, workbench=None, strategic_continuity=None,
                curiosity=None, outcome_learning=None, improvement_loop=None,
                social_continuity=None, model_routing=None, memory_refinement=None,
            )
            # Mirror onto workspace.perception if exists, so snapshot picks it up
            if workspace is not None:
                state = getattr(workspace, "_state", None)
                if state is None:
                    state = type("WS", (), {})()
                    state.perception = PerceptionState()
                if hasattr(state, "perception"):
                    try:
                        apply_heartbeat_to_perception_state(state.perception, type("Bundle", (), {"heartbeat": hb})())
                    except Exception:
                        pass
            # Also store summary directly in g for snapshot fallback
            g["_heartbeat_last_mode"] = str(getattr(hb, "heartbeat_mode", "") or "")
            g["_heartbeat_last_summary"] = str(getattr(hb, "heartbeat_summary", "") or "")
            g["_heartbeat_last_tick_id"] = int(getattr(hb, "heartbeat_tick_id", 0) or 0)
            g["_heartbeat_last_ts"] = time.time()
        except Exception as e:
            print(f"[background_tick] heartbeat error: {e}")


def _video_frame_capture_thread(g: dict[str, Any]) -> None:
    import cv2
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("[video_capture] camera not available")
        return
    print("[video_capture] camera opened, streaming at 15fps")
    while True:
        try:
            ret, frame = cap.read()
            if ret and frame is not None:
                # Update shared frame buffer so /api/v1/camera/live_frame always
                # serves fresh frames without needing its own VideoCapture.
                try:
                    from brain.frame_store import push_frame as _push_frame
                    _push_frame(frame)
                except Exception:
                    pass
                vm = g.get("_video_memory")
                et = g.get("_expression_detector")
                ez = g.get("_eye_tracker")
                expression = ""
                gaze = ""
                if et and getattr(et, "available", False):
                    try:
                        expr = et.detect_expression(frame)
                        if expr:
                            expression = expr.get("dominant", "")
                    except Exception:
                        pass
                if ez and getattr(ez, "available", False) and getattr(ez, "calibrated", False):
                    try:
                        gaze = ez.get_gaze_region(frame) or ""
                    except Exception:
                        pass
                if vm:
                    vm.add_frame(frame, expression=expression, gaze=gaze)
            time.sleep(_VIDEO_INTERVAL)
        except Exception as e:
            print(f"[video_capture] error: {e}")
            time.sleep(2)
            try:
                cap.release()
            except Exception:
                pass
            cap = cv2.VideoCapture(0)


def bootstrap_background_ticks(g: dict[str, Any]) -> None:
    """Start the heartbeat tick thread and the video capture thread."""
    if not g.get("_background_hb_thread_started"):
        t1 = threading.Thread(target=_heartbeat_loop, args=(g,), daemon=True, name="ava-bg-heartbeat")
        t1.start()
        g["_background_hb_thread_started"] = True
        print("[background_ticks] heartbeat tick thread started (every 30s)")

    if not g.get("_background_video_thread_started"):
        t2 = threading.Thread(target=_video_frame_capture_thread, args=(g,), daemon=True, name="ava-bg-video-capture")
        t2.start()
        g["_background_video_thread_started"] = True
        print("[background_ticks] video frame capture thread started (~15 fps)")
