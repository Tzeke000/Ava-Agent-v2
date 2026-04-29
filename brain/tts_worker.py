"""
Thread-safe TTS worker.

pyttsx3 on Windows uses SAPI5 via COM. COM has a single-threaded apartment
model: any thread that uses COM objects must call CoInitialize() first and
must do all work on that same thread. Calling pyttsx3.runAndWait() from a
daemon thread that did NOT initialize COM (e.g. voice_loop's daemon) will
either silently fail or hang forever.

TTSWorker fixes this by running pyttsx3 on a dedicated thread that:
  1. Calls pythoncom.CoInitialize() before pyttsx3.init() (correct apartment)
  2. Initializes pyttsx3 inside its own thread
  3. Drains a queue of (text, rate, volume, optional done-event) tuples
  4. Calls .say() + .runAndWait() on its own thread for every item
  5. Calls pythoncom.CoUninitialize() on shutdown

Callers (voice_loop, turn_handler, /api/v1/tts/speak) put text in the queue.
The worker handles serialization automatically — concurrent speak calls are
queued, never overlap.
"""
from __future__ import annotations

import queue
import threading
import time
from typing import Any, Optional


# Per-emotion voice modulation. Bootstrap-friendly: maps the 27 emotion labels
# Ava already uses to (rate, volume) targets. Intensity scales between neutral
# and the emotion's target so subtle mood changes produce subtle voice changes.
_NEUTRAL_RATE = 155
_NEUTRAL_VOLUME = 0.85

_RATE_BY_EMOTION: dict[str, int] = {
    "calm": 145, "calmness": 145,
    "excitement": 185, "excited": 185,
    "joy": 175, "happy": 175, "happiness": 175,
    "sadness": 130, "sad": 130, "melancholy": 132,
    "curiosity": 165, "interest": 160,
    "boredom": 138, "bored": 138,
    "anxiety": 172, "anxious": 172, "worry": 168,
    "anger": 178, "frustration": 172,
    "fear": 174, "surprise": 180,
    "love": 158, "tenderness": 150,
    "pride": 170, "shame": 138,
    "awe": 162, "hope": 168, "gratitude": 160,
    "neutral": _NEUTRAL_RATE,
}

_VOLUME_BY_EMOTION: dict[str, float] = {
    "calm": 0.80, "calmness": 0.80,
    "excitement": 1.00, "excited": 1.00,
    "joy": 0.95, "happy": 0.95, "happiness": 0.95,
    "sadness": 0.72, "sad": 0.72, "melancholy": 0.74,
    "curiosity": 0.85, "interest": 0.85,
    "boredom": 0.75, "bored": 0.75,
    "anxiety": 0.85, "anxious": 0.85, "worry": 0.82,
    "anger": 0.92, "frustration": 0.88,
    "fear": 0.78, "surprise": 0.92,
    "love": 0.82, "tenderness": 0.78,
    "pride": 0.90, "shame": 0.74,
    "awe": 0.84, "hope": 0.88, "gratitude": 0.82,
    "neutral": _NEUTRAL_VOLUME,
}


def _emotion_to_rate_volume(emotion: str, intensity: float) -> tuple[int, float]:
    """Scale (rate, volume) from neutral toward the emotion's target by intensity."""
    e = (emotion or "neutral").lower().strip()
    target_rate = _RATE_BY_EMOTION.get(e, _NEUTRAL_RATE)
    target_vol = _VOLUME_BY_EMOTION.get(e, _NEUTRAL_VOLUME)
    intensity = max(0.0, min(1.0, float(intensity)))
    rate = int(round(_NEUTRAL_RATE + (target_rate - _NEUTRAL_RATE) * intensity))
    volume = round(_NEUTRAL_VOLUME + (target_vol - _NEUTRAL_VOLUME) * intensity, 3)
    rate = max(120, min(220, rate))
    volume = max(0.6, min(1.0, volume))
    return rate, volume


# Queue item: (text, rate, volume, optional done-event)
_QueueItem = Optional[tuple[str, int, float, Optional[threading.Event]]]


class TTSWorker:
    def __init__(self) -> None:
        self._queue: "queue.Queue[_QueueItem]" = queue.Queue()
        self._stop_evt = threading.Event()
        self._engine: Any = None
        self._engine_name: str = "none"
        self._voice_name: str = "unknown"
        self._available: bool = False
        self._init_done = threading.Event()
        self._init_error: str = ""
        self._currently_speaking = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True, name="ava-tts-worker")
        self._thread.start()
        self._init_done.wait(timeout=10.0)

    # ── thread body ────────────────────────────────────────────────────────────

    def _run(self) -> None:
        # Initialize COM on THIS thread before touching pyttsx3 / SAPI5.
        com_initialized = False
        try:
            try:
                import pythoncom  # type: ignore
                pythoncom.CoInitialize()
                com_initialized = True
                print("[tts_worker] COM initialized on worker thread")
            except Exception as e:
                print(f"[tts_worker] CoInitialize failed (non-fatal): {e!r}")

            self._init_engine_in_thread()
            if not self._available:
                return

            while not self._stop_evt.is_set():
                try:
                    item = self._queue.get(timeout=0.5)
                except queue.Empty:
                    continue
                if item is None:
                    break
                text, rate, volume, done = item
                if not text:
                    if done:
                        done.set()
                    continue
                try:
                    self._currently_speaking.set()
                    try:
                        self._engine.setProperty("rate", max(120, min(220, int(rate))))
                        self._engine.setProperty("volume", max(0.6, min(1.0, float(volume))))
                    except Exception:
                        pass
                    self._engine.say(text)
                    self._engine.runAndWait()
                    print(f"[tts_worker] spoke ({rate}rate {volume:.2f}vol): {text[:60]!r}")
                except Exception as e:
                    print(f"[tts_worker] speak error: {e!r}")
                finally:
                    self._currently_speaking.clear()
                    if done:
                        done.set()
        finally:
            if com_initialized:
                try:
                    import pythoncom  # type: ignore
                    pythoncom.CoUninitialize()
                except Exception:
                    pass

    def _init_engine_in_thread(self) -> None:
        try:
            import pyttsx3  # type: ignore
            engine = pyttsx3.init()
            selected_name = "default"
            voices = engine.getProperty("voices") or []
            for voice in voices:
                voice_name = str(getattr(voice, "name", "") or "")
                if any(x in voice_name.lower() for x in ("zira", "hazel", "female")):
                    engine.setProperty("voice", str(getattr(voice, "id", "") or ""))
                    selected_name = voice_name
                    break
            engine.setProperty("rate", _NEUTRAL_RATE)
            engine.setProperty("volume", _NEUTRAL_VOLUME)
            self._engine = engine
            self._voice_name = selected_name
            self._engine_name = "pyttsx3"
            self._available = True
            print(f"[tts_worker] pyttsx3 ready (voice={selected_name})")
        except Exception as e:
            self._available = False
            self._engine_name = "none"
            self._init_error = f"{e!r}"
            print(f"[tts_worker] init failed: {e!r}")
        finally:
            self._init_done.set()

    # ── public API ─────────────────────────────────────────────────────────────

    def speak(
        self,
        text: str,
        rate: int = _NEUTRAL_RATE,
        volume: float = _NEUTRAL_VOLUME,
        blocking: bool = False,
    ) -> None:
        """Queue text for speaking. Returns immediately unless blocking=True."""
        if not self._available or not text or not text.strip():
            return
        if blocking:
            done = threading.Event()
            self._queue.put((text.strip(), int(rate), float(volume), done))
            done.wait(timeout=60.0)
        else:
            self._queue.put((text.strip(), int(rate), float(volume), None))

    def speak_with_emotion(
        self,
        text: str,
        emotion: str = "neutral",
        intensity: float = 0.5,
        blocking: bool = False,
    ) -> None:
        """Queue text using emotion-derived rate/volume."""
        rate, volume = _emotion_to_rate_volume(emotion, intensity)
        self.speak(text, rate=rate, volume=volume, blocking=blocking)

    def apply_style(self, rate: int | None = None, volume: float | None = None) -> None:
        """Compatibility shim — used by tts_engine.py to push voice_style updates.

        Sets defaults applied to the *next* speak() that doesn't override them.
        Cannot mutate engine properties directly from another thread; the queue
        item carries the actual rate/volume that the worker applies.
        """
        if rate is not None:
            try:
                self._default_rate = max(120, min(220, int(rate)))
            except Exception:
                pass
        if volume is not None:
            try:
                self._default_volume = max(0.6, min(1.0, float(volume)))
            except Exception:
                pass

    def stop(self) -> None:
        try:
            if self._engine is not None:
                self._engine.stop()
        except Exception:
            pass

    def shutdown(self) -> None:
        self._stop_evt.set()
        try:
            self._queue.put(None)
        except Exception:
            pass

    # ── status ─────────────────────────────────────────────────────────────────

    def is_available(self) -> bool:
        return self._available

    @property
    def available(self) -> bool:
        return self._available

    def is_speaking(self) -> bool:
        return self._currently_speaking.is_set()

    def engine_name(self) -> str:
        return self._engine_name

    def voice_name(self) -> str:
        return self._voice_name


# ── Module singleton ──────────────────────────────────────────────────────────
_singleton: Optional[TTSWorker] = None
_singleton_lock = threading.Lock()


def get_tts_worker() -> TTSWorker:
    """Return process-wide TTSWorker singleton, creating it lazily."""
    global _singleton
    if _singleton is not None:
        return _singleton
    with _singleton_lock:
        if _singleton is None:
            _singleton = TTSWorker()
    return _singleton
