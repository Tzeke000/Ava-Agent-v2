"""
Phase 62 — Clap detection backup wake activation.

Listens for two claps within 1 second as alternate wake trigger.
Low CPU when idle. Falls back gracefully if sounddevice unavailable.
"""
from __future__ import annotations

import threading
import time
from typing import Any, Callable, Optional


class ClapDetector:
    def __init__(self, g: dict[str, Any], on_clap: Optional[Callable] = None):
        self._g = g
        self._on_clap = on_clap
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._clap_times: list[float] = []

    def start(self) -> bool:
        try:
            import sounddevice as sd  # noqa: F401
            import numpy as np  # noqa: F401
        except ImportError:
            return False
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="ava-clap-detect")
        self._thread.start()
        return True

    def stop(self) -> None:
        self._running = False

    def _loop(self) -> None:
        try:
            import sounddevice as sd
            import numpy as np

            SAMPLE_RATE = 16000
            BLOCK_SIZE = 1600  # 100ms blocks
            CLAP_THRESHOLD = 0.4  # RMS amplitude threshold

            def _audio_callback(indata, frames, _time, status):
                if not self._running:
                    return
                if self._g.get("input_muted"):
                    return
                rms = float(np.sqrt(np.mean(indata ** 2)))
                if rms > CLAP_THRESHOLD:
                    now = time.monotonic()
                    self._clap_times.append(now)
                    # Keep only last 3 seconds
                    self._clap_times = [t for t in self._clap_times if now - t < 3.0]
                    # Two claps within 1 second
                    recent = [t for t in self._clap_times if now - t < 1.0]
                    if len(recent) >= 2:
                        self._clap_times.clear()
                        self._trigger()

            with sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=1,
                blocksize=BLOCK_SIZE,
                callback=_audio_callback,
            ):
                while self._running:
                    time.sleep(0.5)
        except Exception:
            self._running = False

    def _trigger(self) -> None:
        self._g["_wake_word_detected"] = True
        self._g["_wake_word_ts"] = time.time()
        print("[clap_detect] double clap detected — wake triggered")
        if callable(self._on_clap):
            try:
                self._on_clap()
            except Exception:
                pass
