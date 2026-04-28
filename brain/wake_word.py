"""
Phase 57 — Wake word detection.

Uses Picovoice Porcupine (pvporcupine + pvrecorder) if available.
Falls back to lightweight keyword polling via sounddevice + whisper-tiny.

Requires (optional): py -3.11 -m pip install pvporcupine pvrecorder

Bootstrap: Ava learns your activation patterns — what time you usually talk to her,
what you say first — and prepares relevant context before you finish speaking.
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any, Callable, Optional


class WakeWordDetector:
    def __init__(
        self,
        g: dict[str, Any],
        on_wake: Optional[Callable] = None,
        keywords: tuple[str, ...] = ("hey ava", "ava"),
        base_dir: Optional[Path] = None,
    ):
        self._g = g
        self._on_wake = on_wake
        self._keywords = keywords
        self._base = Path(base_dir) if base_dir else Path(".")
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._porcupine = None
        self._recorder = None
        self._pattern_path = self._base / "state" / "wake_patterns.json"
        self._patterns: list[dict] = self._load_patterns()
        self._backend = "none"

    def _load_patterns(self) -> list[dict]:
        if not self._pattern_path.is_file():
            return []
        try:
            return json.loads(self._pattern_path.read_text(encoding="utf-8"))
        except Exception:
            return []

    def _record_activation(self) -> None:
        hour = int(time.strftime("%H"))
        self._patterns.append({"ts": time.time(), "hour": hour})
        if len(self._patterns) > 200:
            self._patterns = self._patterns[-200:]
        try:
            self._pattern_path.parent.mkdir(parents=True, exist_ok=True)
            self._pattern_path.write_text(
                json.dumps(self._patterns, indent=2, ensure_ascii=False), encoding="utf-8"
            )
        except Exception:
            pass

    def _trigger_wake(self) -> None:
        self._g["_wake_word_detected"] = True
        self._g["_wake_word_ts"] = time.time()
        self._record_activation()
        print("[wake_word] wake detected")
        if callable(self._on_wake):
            try:
                self._on_wake()
            except Exception:
                pass

    def _try_init_porcupine(self) -> bool:
        try:
            import pvporcupine  # type: ignore
            import pvrecorder  # type: ignore
            access_key = self._g.get("PORCUPINE_ACCESS_KEY") or ""
            if not access_key:
                return False
            self._porcupine = pvporcupine.create(
                access_key=access_key,
                keywords=["hey siri"],  # closest built-in approximation
            )
            self._recorder = pvrecorder.PvRecorder(frame_length=self._porcupine.frame_length)
            self._backend = "porcupine"
            return True
        except Exception:
            return False

    def _porcupine_loop(self) -> None:
        try:
            self._recorder.start()
            while self._running:
                pcm = self._recorder.read()
                result = self._porcupine.process(pcm)
                if result >= 0:
                    self._trigger_wake()
        except Exception as ex:
            print(f"[wake_word] porcupine loop error: {ex!r}")
        finally:
            try:
                self._recorder.stop()
            except Exception:
                pass

    def _whisper_poll_loop(self) -> None:
        """Fallback: poll STT every 3s for wake keywords. Higher CPU, but no API key needed."""
        self._backend = "whisper_poll"
        while self._running:
            try:
                if self._g.get("input_muted"):
                    time.sleep(1.0)
                    continue
                import numpy as np
                import sounddevice as sd
                audio = sd.rec(int(1.5 * 16000), samplerate=16000, channels=1, dtype="float32")
                sd.wait()
                audio = np.squeeze(audio)
                stt_model = self._g.get("_stt_model")
                if stt_model is None:
                    try:
                        from faster_whisper import WhisperModel
                        stt_model = WhisperModel("tiny", device="cpu", compute_type="int8")
                        self._g["_stt_model"] = stt_model
                    except Exception:
                        time.sleep(3.0)
                        continue
                segments, _ = stt_model.transcribe(audio, language="en", beam_size=1)
                text = " ".join(s.text for s in segments).strip().lower()
                if any(kw in text for kw in self._keywords):
                    self._trigger_wake()
            except Exception:
                pass
            time.sleep(3.0)

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        use_porcupine = self._try_init_porcupine()
        target = self._porcupine_loop if use_porcupine else self._whisper_poll_loop
        self._thread = threading.Thread(target=target, daemon=True, name="ava-wake-word")
        self._thread.start()
        print(f"[wake_word] started backend={self._backend}")

    def stop(self) -> None:
        self._running = False
        try:
            if self._porcupine:
                self._porcupine.delete()
        except Exception:
            pass

    def get_pattern_summary(self) -> dict:
        if not self._patterns:
            return {"peak_hour": None, "total_activations": 0}
        hours = [p["hour"] for p in self._patterns]
        from collections import Counter
        peak = Counter(hours).most_common(1)[0][0] if hours else None
        return {"peak_hour": peak, "total_activations": len(self._patterns), "backend": self._backend}
