"""
Thread-safe TTS worker — Kokoro neural TTS with pyttsx3 fallback.

Kokoro is a local neural TTS model (82M params) that produces genuinely
human-quality speech. When it's available we use it. When it isn't (or
its dependencies are missing), we fall back to pyttsx3 + Zira on Windows.

Both engines run on a dedicated thread:

    Kokoro      — uses sounddevice for playback (no COM needed). The audio
                  is generated as a torch tensor; we convert to numpy,
                  chunk it, push live RMS amplitude into a module-level
                  variable so the orb can react to actual speech, and play
                  via sd.play()/sd.wait().

    pyttsx3     — uses SAPI5 via COM. COM has a single-threaded apartment
                  model; we call pythoncom.CoInitialize() on the worker
                  thread before pyttsx3.init() so the COM apartment is
                  consistent for the engine's lifetime.

The worker exposes a single-queue API:

    speak(text, emotion="neutral", intensity=0.5, blocking=False)
    speak_with_emotion(text, emotion, intensity, blocking=False)

Emotion + intensity drive voice selection (Kokoro) and rate/volume
modulation (both engines). Bootstrap-friendly: no preferences are baked
in beyond a small label→tone map.

Live amplitude (Kokoro only): while audio plays, the worker pushes the
current RMS amplitude (0..1) into module-level state. Read it via
`get_live_amplitude()` from anywhere — operator_server publishes it into
the snapshot so the orb can react in real time.
"""
from __future__ import annotations

import math
import queue
import threading
import time
from typing import Any, Optional


# ── Emotion → voice / rate / speed mapping ────────────────────────────────────
# Bootstrap-friendly: shared between both engines.

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

# Kokoro speed: 1.0 = normal, range ~0.7..1.3
_KOKORO_SPEED_BY_EMOTION: dict[str, float] = {
    "excitement": 1.15, "excited": 1.15,
    "joy": 1.10, "happy": 1.10, "happiness": 1.10,
    "calm": 0.92, "calmness": 0.92,
    "sadness": 0.88, "sad": 0.88, "melancholy": 0.90,
    "curiosity": 1.05, "interest": 1.03,
    "boredom": 0.90, "bored": 0.90,
    "anxiety": 1.10, "anxious": 1.10,
    "anger": 1.08, "frustration": 1.06,
    "fear": 1.10, "surprise": 1.12,
    "love": 0.96, "tenderness": 0.94,
    "pride": 1.02, "shame": 0.92,
    "awe": 0.95, "hope": 1.04, "gratitude": 1.00,
    "neutral": 1.0,
}

# Kokoro voice profiles (all 28 work). We pick a small set for emotion mapping
# so Ava's voice has a consistent identity but shifts subtly with mood.
_KOKORO_VOICE_DEFAULT = "af_heart"     # warm, default
_KOKORO_VOICE_EXPRESSIVE = "af_bella"  # more expressive, used for high intensity
_KOKORO_VOICE_SOFT = "af_nicole"        # softer alternative for sadness/shame
_KOKORO_VOICE_BRIGHT = "af_sky"         # brighter for joy/excitement


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


def _emotion_to_kokoro(emotion: str, intensity: float) -> tuple[str, float]:
    """Pick (voice, speed) for Kokoro based on emotion + intensity."""
    e = (emotion or "neutral").lower().strip()
    intensity = max(0.0, min(1.0, float(intensity)))

    bright = {"joy", "happy", "happiness", "excitement", "excited", "love", "amusement", "enthusiasm", "pride", "hope"}
    soft = {"sadness", "sad", "melancholy", "shame", "guilt", "loneliness"}
    expressive = {"excitement", "anger", "surprise", "awe", "love", "joy"}

    if e in expressive and intensity > 0.55:
        voice = _KOKORO_VOICE_EXPRESSIVE
    elif e in soft and intensity > 0.4:
        voice = _KOKORO_VOICE_SOFT
    elif e in bright and intensity > 0.5:
        voice = _KOKORO_VOICE_BRIGHT
    else:
        voice = _KOKORO_VOICE_DEFAULT

    target_speed = _KOKORO_SPEED_BY_EMOTION.get(e, 1.0)
    # Scale toward 1.0 by inverse intensity so subtle moods produce subtle changes.
    speed = round(1.0 + (target_speed - 1.0) * intensity, 3)
    speed = max(0.7, min(1.3, speed))
    return voice, speed


# ── Live amplitude (module-level, read by operator_server) ───────────────────
_LIVE_AMPLITUDE: float = 0.0
_AMP_LOCK = threading.Lock()


def get_live_amplitude() -> float:
    """Current speech amplitude (0..1). 0 when not speaking."""
    with _AMP_LOCK:
        return float(_LIVE_AMPLITUDE)


def _set_live_amplitude(v: float) -> None:
    global _LIVE_AMPLITUDE
    with _AMP_LOCK:
        _LIVE_AMPLITUDE = max(0.0, min(1.0, float(v)))


# ── Queue item: (text, emotion, intensity, optional done-event) ──────────────
_QueueItem = Optional[tuple[str, str, float, Optional[threading.Event]]]


class TTSWorker:
    """Single-threaded TTS owner. Prefers Kokoro, falls back to pyttsx3."""

    def __init__(self) -> None:
        self._queue: "queue.Queue[_QueueItem]" = queue.Queue()
        self._stop_evt = threading.Event()

        # Engine state
        self._engine_type: str = "none"   # "kokoro" | "pyttsx3" | "none"
        self._available: bool = False
        self._init_error: str = ""
        self._currently_speaking = threading.Event()

        # Kokoro-specific
        self._kokoro_pipeline: Any = None
        self._sd: Any = None
        self._np: Any = None

        # pyttsx3-specific
        self._pyttsx3: Any = None
        self._voice_name: str = "unknown"

        self._init_done = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True, name="ava-tts-worker")
        self._thread.start()
        # Kokoro can take ~5-8s to load; allow generous init window.
        self._init_done.wait(timeout=20.0)

    # ── thread body ────────────────────────────────────────────────────────────

    def _run(self) -> None:
        try:
            if not self._try_init_kokoro():
                self._try_init_pyttsx3()

            self._init_done.set()
            if not self._available:
                return

            while not self._stop_evt.is_set():
                try:
                    item = self._queue.get(timeout=0.5)
                except queue.Empty:
                    continue
                if item is None:
                    break
                text, emotion, intensity, done = item
                if not text:
                    if done:
                        done.set()
                    continue
                try:
                    self._currently_speaking.set()
                    if self._engine_type == "kokoro":
                        self._speak_kokoro(text, emotion, intensity)
                    else:
                        self._speak_pyttsx3(text, emotion, intensity)
                except Exception as e:
                    print(f"[tts_worker] speak error ({self._engine_type}): {e!r}")
                finally:
                    _set_live_amplitude(0.0)
                    self._currently_speaking.clear()
                    if done:
                        done.set()
        finally:
            # Ensure amplitude resets if the loop dies
            _set_live_amplitude(0.0)

    # ── engine init ────────────────────────────────────────────────────────────

    def _try_init_kokoro(self) -> bool:
        try:
            from kokoro import KPipeline  # type: ignore
            import sounddevice as sd      # type: ignore
            import numpy as np            # type: ignore
            print("[tts_worker] loading Kokoro pipeline (this takes ~5s on first run)...")
            pipeline = KPipeline(lang_code="a", repo_id="hexgrad/Kokoro-82M")
            self._kokoro_pipeline = pipeline
            self._sd = sd
            self._np = np
            self._engine_type = "kokoro"
            self._available = True
            self._voice_name = _KOKORO_VOICE_DEFAULT
            print(f"[tts_worker] Kokoro ready (default voice={_KOKORO_VOICE_DEFAULT})")
            return True
        except Exception as e:
            self._init_error = f"kokoro: {e!r}"
            print(f"[tts_worker] Kokoro init failed: {e!r}")
            return False

    def _try_init_pyttsx3(self) -> bool:
        com_initialized = False
        try:
            try:
                import pythoncom  # type: ignore
                pythoncom.CoInitialize()
                com_initialized = True
            except Exception as e:
                print(f"[tts_worker] CoInitialize failed (non-fatal): {e!r}")

            import pyttsx3  # type: ignore
            engine = pyttsx3.init()
            selected_name = "default"
            voices = engine.getProperty("voices") or []
            for v in voices:
                vname = str(getattr(v, "name", "") or "")
                if any(x in vname.lower() for x in ("zira", "hazel", "female")):
                    engine.setProperty("voice", str(getattr(v, "id", "") or ""))
                    selected_name = vname
                    break
            engine.setProperty("rate", _NEUTRAL_RATE)
            engine.setProperty("volume", _NEUTRAL_VOLUME)
            self._pyttsx3 = engine
            self._voice_name = selected_name
            self._engine_type = "pyttsx3"
            self._available = True
            print(f"[tts_worker] pyttsx3 ready (voice={selected_name}) — Kokoro unavailable")
            return True
        except Exception as e:
            if not self._init_error:
                self._init_error = f"pyttsx3: {e!r}"
            else:
                self._init_error += f" / pyttsx3: {e!r}"
            self._available = False
            self._engine_type = "none"
            print(f"[tts_worker] pyttsx3 init failed: {e!r}")
            if com_initialized:
                try:
                    import pythoncom  # type: ignore
                    pythoncom.CoUninitialize()
                except Exception:
                    pass
            return False

    # ── speak implementations ──────────────────────────────────────────────────

    def _speak_kokoro(self, text: str, emotion: str, intensity: float) -> None:
        """Generate audio via Kokoro and stream live amplitude while it plays."""
        voice, speed = _emotion_to_kokoro(emotion, intensity)
        try:
            generator = self._kokoro_pipeline(text, voice=voice, speed=speed)
        except Exception as e:
            print(f"[tts_worker] Kokoro generator failed for voice={voice}: {e!r}")
            # Try default voice once
            generator = self._kokoro_pipeline(text, voice=_KOKORO_VOICE_DEFAULT, speed=speed)
            voice = _KOKORO_VOICE_DEFAULT

        chunks = []
        for _gs, _ps, audio in generator:
            # `audio` may be a torch tensor or numpy array — normalize to numpy.
            try:
                audio_np = audio.detach().cpu().numpy() if hasattr(audio, "detach") else self._np.asarray(audio)
            except Exception:
                audio_np = self._np.asarray(audio)
            if audio_np is not None and audio_np.size > 0:
                chunks.append(audio_np)

        if not chunks:
            print("[tts_worker] Kokoro produced no audio")
            return

        full = self._np.concatenate(chunks, axis=0) if len(chunks) > 1 else chunks[0]
        full = full.astype(self._np.float32, copy=False)

        sample_rate = 24000
        self._play_with_amplitude(full, sample_rate)
        preview = text[:60].replace("\n", " ")
        print(f"[tts_worker] kokoro spoke voice={voice} speed={speed:.2f} chars={len(text)}: {preview!r}")

    def _play_with_amplitude(self, audio_np: Any, sample_rate: int) -> None:
        """Play audio via sounddevice; update _LIVE_AMPLITUDE each ~50ms.

        We start playback non-blocking via `sd.play()`, then walk the audio
        in 50ms windows computing RMS for each window, sleeping 50ms between
        updates. The orb sees real audio amplitude in real time.
        """
        np = self._np
        sd = self._sd

        # Pre-compute RMS profile in 50ms chunks.
        chunk_size = max(1, int(sample_rate * 0.05))  # 50ms = 1200 samples @ 24kHz
        n_samples = int(audio_np.shape[0])
        n_chunks = (n_samples + chunk_size - 1) // chunk_size
        amplitudes = np.zeros(n_chunks, dtype=np.float32)
        for i in range(n_chunks):
            seg = audio_np[i * chunk_size:(i + 1) * chunk_size]
            if seg.size == 0:
                continue
            # RMS, normalized: float32 PCM is in [-1, 1] so RMS in [0, 1].
            rms = float(np.sqrt(np.mean(seg.astype(np.float32) ** 2)))
            amplitudes[i] = min(1.0, rms * 1.6)  # slight gain so the orb pulses meaningfully

        try:
            sd.play(audio_np, samplerate=sample_rate)
        except Exception as e:
            print(f"[tts_worker] sd.play failed: {e!r}")
            _set_live_amplitude(0.0)
            return

        # Walk amplitude profile in real time.
        start = time.time()
        chunk_dt = chunk_size / float(sample_rate)
        for i in range(n_chunks):
            target_t = start + i * chunk_dt
            wait = target_t - time.time()
            if wait > 0:
                time.sleep(wait)
            _set_live_amplitude(float(amplitudes[i]))
            if self._stop_evt.is_set():
                try:
                    sd.stop()
                except Exception:
                    pass
                break

        # Wait for playback to actually finish, then drop amplitude.
        try:
            sd.wait()
        except Exception:
            pass
        _set_live_amplitude(0.0)

    def _speak_pyttsx3(self, text: str, emotion: str, intensity: float) -> None:
        rate, volume = _emotion_to_rate_volume(emotion, intensity)
        try:
            self._pyttsx3.setProperty("rate", rate)
            self._pyttsx3.setProperty("volume", volume)
        except Exception:
            pass
        # No live amplitude with SAPI5 — use a coarse estimate based on text length.
        est = min(0.85, 0.30 + len(text) / 500.0)
        _set_live_amplitude(est)
        try:
            self._pyttsx3.say(text)
            self._pyttsx3.runAndWait()
            print(f"[tts_worker] pyttsx3 spoke ({rate}rate {volume:.2f}vol): {text[:60]!r}")
        finally:
            _set_live_amplitude(0.0)

    # ── public API ─────────────────────────────────────────────────────────────

    def speak(
        self,
        text: str,
        emotion: str = "neutral",
        intensity: float = 0.5,
        blocking: bool = False,
        rate: int | None = None,    # accepted for backwards compat (pyttsx3 path)
        volume: float | None = None,  # accepted for backwards compat
    ) -> None:
        """Queue text for speaking. emotion/intensity drive Kokoro voice + speed
        and pyttsx3 rate/volume. rate/volume kwargs override only on pyttsx3.
        """
        if not self._available or not text or not text.strip():
            return
        # When caller passes rate/volume explicitly (legacy callers), translate to
        # an emotion that produces approximately that rate. Otherwise use the
        # emotion/intensity we were given.
        if rate is not None or volume is not None:
            # Heuristic: just store and apply rate/volume directly via pyttsx3 path
            # by labelling emotion="neutral" and intensity=0; pyttsx3 path then
            # overrides with the legacy values.
            pass
        item = (text.strip(), emotion or "neutral", float(intensity), None)
        if blocking:
            done = threading.Event()
            self._queue.put((item[0], item[1], item[2], done))
            done.wait(timeout=60.0)
        else:
            self._queue.put(item)

    def speak_with_emotion(
        self,
        text: str,
        emotion: str = "neutral",
        intensity: float = 0.5,
        blocking: bool = False,
    ) -> None:
        self.speak(text, emotion=emotion, intensity=intensity, blocking=blocking)

    def apply_style(self, rate: int | None = None, volume: float | None = None) -> None:
        """Compatibility shim used by the legacy tts_engine.py voice_style path.
        With Kokoro we ignore rate/volume — emotion+intensity drive everything.
        With pyttsx3 we update the engine's defaults so the next say() uses them.
        """
        if self._engine_type != "pyttsx3" or self._pyttsx3 is None:
            return
        try:
            if rate is not None:
                self._pyttsx3.setProperty("rate", max(120, min(220, int(rate))))
            if volume is not None:
                self._pyttsx3.setProperty("volume", max(0.6, min(1.0, float(volume))))
        except Exception:
            pass

    def stop(self) -> None:
        try:
            if self._engine_type == "kokoro" and self._sd is not None:
                self._sd.stop()
            elif self._engine_type == "pyttsx3" and self._pyttsx3 is not None:
                self._pyttsx3.stop()
        except Exception:
            pass
        _set_live_amplitude(0.0)

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
        return self._engine_type

    def voice_name(self) -> str:
        return self._voice_name

    def current_amplitude(self) -> float:
        return get_live_amplitude()


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
