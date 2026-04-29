"""
Periodic background ticks for systems that need to run independently of conversation.

- Heartbeat tick every 30s (so snapshot has fresh heartbeat data without chat activity)
- Video frame capture every ~67ms (15 fps) — feeds the VideoMemory rolling buffer
- Clipboard monitor every 2s (publishes _clipboard_content / _clipboard_type to globals)
- All threads are daemon, all calls are wrapped in try/except.
"""
from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any

_HB_INTERVAL = 30.0
_VIDEO_INTERVAL = 1.0 / 15.0  # 15 fps
_CLIPBOARD_INTERVAL = 2.0
_CODE_HINTS = ("def ", "class ", "import ", "function ", "const ", "var ", "let ", "{\n", "}\n")


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

    # InsightFace runs on every Nth frame (heavy: 30-50ms per call on GPU).
    # Annotator draws overlays from the cached _face_results every frame.
    _frame_idx = 0
    _insight_every_n = 3  # ~5fps face detection at 15fps capture

    while True:
        try:
            ret, frame = cap.read()
            if ret and frame is not None:
                _frame_idx += 1

                # Run InsightFace on a subset of frames; cache results in g.
                insight = g.get("_insight_face")
                if insight is not None and getattr(insight, "available", False):
                    if _frame_idx % _insight_every_n == 0:
                        try:
                            face_results = insight.analyze_frame(frame)
                            g["_face_results"] = face_results
                            if face_results:
                                # Pick the highest-confidence face as "the person"
                                best = max(face_results, key=lambda r: float(r.get("confidence") or 0.0))
                                g["_recognized_person_id"] = str(best.get("person_id") or "unknown")
                                g["_recognized_confidence"] = float(best.get("confidence") or 0.0)
                                g["_recognized_age"] = best.get("age", 0)
                                g["_recognized_gender"] = best.get("gender", "?")
                            else:
                                g["_recognized_person_id"] = "unknown"
                                g["_recognized_confidence"] = 0.0
                        except Exception as _ie:
                            print(f"[video_capture] insight analyze error: {_ie}")

                # Annotate the frame with whatever face_results we currently have.
                annotated = frame
                try:
                    from brain.camera_annotator import annotate_frame as _annotate
                    annotated = _annotate(frame, g.get("_face_results"), g)
                except Exception as _ae:
                    print(f"[video_capture] annotate error: {_ae}")

                # Push annotated frame so the UI sees the overlay live.
                try:
                    from brain.frame_store import push_frame as _push_frame
                    _push_frame(annotated)
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
                    # Write the *raw* (unannotated) frame to video memory so
                    # episodic recall isn't polluted with overlays.
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


def _clipboard_monitor_loop(g: dict[str, Any]) -> None:
    """Poll the system clipboard every _CLIPBOARD_INTERVAL seconds.

    Publishes:
      g["_clipboard_content"]      first 500 chars of the latest clipboard text
      g["_clipboard_type"]         one of "url", "code", "text"
      g["_clipboard_changed_ts"]   wall time of last change
    Errors are swallowed (clipboard race conditions on Windows are common).
    """
    try:
        import pyperclip  # type: ignore
    except Exception as e:
        print(f"[clipboard] pyperclip unavailable: {e!r}")
        return
    last = ""
    while True:
        try:
            current = pyperclip.paste()
        except Exception:
            time.sleep(_CLIPBOARD_INTERVAL)
            continue
        try:
            if isinstance(current, str) and current.strip() and current != last:
                last = current
                snippet = current[:500]
                g["_clipboard_content"] = snippet
                g["_clipboard_changed_ts"] = time.time()
                low = current.lower().lstrip()
                if low.startswith("http://") or low.startswith("https://"):
                    g["_clipboard_type"] = "url"
                elif any(kw in current for kw in _CODE_HINTS):
                    g["_clipboard_type"] = "code"
                else:
                    g["_clipboard_type"] = "text"
        except Exception:
            pass
        time.sleep(_CLIPBOARD_INTERVAL)


def bootstrap_background_ticks(g: dict[str, Any]) -> None:
    """Start the heartbeat tick thread, video capture thread, and clipboard monitor."""
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

    if not g.get("_background_clipboard_thread_started"):
        t3 = threading.Thread(target=_clipboard_monitor_loop, args=(g,), daemon=True, name="ava-bg-clipboard")
        t3.start()
        g["_background_clipboard_thread_started"] = True
        print("[background_ticks] clipboard monitor thread started (every 2s)")
