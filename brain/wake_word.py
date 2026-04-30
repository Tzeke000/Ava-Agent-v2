"""
Wake word detector — openWakeWord (ONNX) primary, polling fallback.

openWakeWord runs a tiny ONNX model on every 80ms of microphone input.
Total CPU is well under 1% on a desktop. MIT-licensed, no API keys, runs
fully local.

We use `hey_jarvis` as a proxy for "Hey Ava" until a custom `hey_ava`
ONNX model exists at `models/wake_words/hey_ava.onnx`. Phonetics are close
enough that "hey jarvis" / "hey ava" both fire reliably; the proxy stops
once the custom model lands.

Bootstrap: Ava records each activation hour to `state/wake_patterns.json`
so she can later notice when she's typically being talked to.
"""
from __future__ import annotations

import json
import queue
import threading
import time
from collections import Counter
from pathlib import Path
from typing import Any, Callable, Optional


_DEFAULT_THRESHOLD = 0.5     # openWakeWord prediction confidence to trigger
_CHUNK_SAMPLES = 1280        # 80ms at 16kHz — required by openWakeWord
_SAMPLE_RATE = 16000
_TRIGGER_COOLDOWN_SEC = 1.5  # ignore back-to-back hits within this window


class WakeWordDetector:
    def __init__(
        self,
        g: dict[str, Any],
        on_wake: Optional[Callable[[], Any]] = None,
        keywords: tuple[str, ...] = ("hey ava", "ava"),
        base_dir: Optional[Path] = None,
    ):
        self._g = g
        self._on_wake = on_wake
        self._keywords = keywords
        self._base = Path(base_dir) if base_dir else Path(".")
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._pattern_path = self._base / "state" / "wake_patterns.json"
        self._patterns: list[dict] = self._load_patterns()

        # Backend bookkeeping
        self._backend: str = "none"
        self._available: bool = False
        self._last_trigger_ts: float = 0.0

        # openWakeWord state
        self._oww_model: Any = None
        self._oww_keys: list[str] = []
        self._oww_threshold = _DEFAULT_THRESHOLD
        self._audio_q: "queue.Queue[Any]" = queue.Queue(maxsize=64)

    # ── persistence ────────────────────────────────────────────────────────────

    def _load_patterns(self) -> list[dict]:
        if not self._pattern_path.is_file():
            return []
        try:
            return json.loads(self._pattern_path.read_text(encoding="utf-8"))
        except Exception:
            return []

    def _record_activation(self, source: str) -> None:
        hour = int(time.strftime("%H"))
        self._patterns.append({"ts": time.time(), "hour": hour, "source": source})
        if len(self._patterns) > 200:
            self._patterns = self._patterns[-200:]
        try:
            self._pattern_path.parent.mkdir(parents=True, exist_ok=True)
            self._pattern_path.write_text(
                json.dumps(self._patterns, indent=2, ensure_ascii=False), encoding="utf-8"
            )
        except Exception:
            pass

    # ── trigger ────────────────────────────────────────────────────────────────

    def _trigger_wake(self, source: str = "openwakeword") -> None:
        # Per-instance cooldown so model jitter near threshold doesn't spam.
        now = time.time()
        if (now - self._last_trigger_ts) < _TRIGGER_COOLDOWN_SEC:
            return
        self._last_trigger_ts = now

        self._g["_wake_word_detected"] = True
        self._g["_wake_word_ts"] = now
        # Mark wake source — wake_detector treats this as direct address and
        # skips classification (same path as clap-triggered wakes).
        self._g["_wake_source"] = source
        self._g["_wake_source_ts"] = now
        self._record_activation(source)
        print(f"[wake_word] wake triggered (source={source})")
        if callable(self._on_wake):
            try:
                self._on_wake()
            except Exception as e:
                print(f"[wake_word] on_wake handler error: {e!r}")

    # ── openWakeWord init ─────────────────────────────────────────────────────

    def _try_init_oww(self) -> bool:
        try:
            import openwakeword  # type: ignore
            from openwakeword.model import Model  # type: ignore
        except Exception as e:
            print(f"[wake_word] openWakeWord unavailable: {e!r}")
            return False
        try:
            # Idempotent — only downloads on first run.
            try:
                openwakeword.utils.download_models()
            except Exception as e:
                print(f"[wake_word] model download warning: {e!r}")

            # Priority: custom hey_ava model if present, then hey_jarvis as
            # the most reliable proxy (verified 2026-04-29 against synthetic
            # Kokoro "hey ava" samples — hey_jarvis peaked 0.917 on at least
            # one voice; hey_mycroft and hey_rhasspy stayed below 0.02 across
            # all samples, so they're not viable proxies).
            wake_models: list[str] = []
            custom = self._base / "models" / "wake_words" / "hey_ava.onnx"
            if custom.is_file():
                wake_models.append(str(custom))
                print(f"[wake_word] custom hey_ava model loaded: {custom}")
            # Always keep hey_jarvis as a belt-and-suspenders proxy until the
            # custom model is field-validated; remove it from the list once
            # the user is satisfied with the custom model.
            wake_models.append("hey_jarvis")

            self._oww_model = Model(
                wakeword_models=wake_models,
                inference_framework="onnx",
                enable_speex_noise_suppression=False,
            )
            self._oww_keys = list(self._oww_model.models.keys())
            using_custom = any("hey_ava" in k for k in self._oww_keys)
            tag = "custom hey_ava + hey_jarvis fallback" if using_custom else "hey_jarvis (proxy until custom trained)"
            print(f"[wake_word] openWakeWord ready models={self._oww_keys} ({tag})")
            return True
        except Exception as e:
            print(f"[wake_word] openWakeWord init failed: {e!r}")
            self._oww_model = None
            return False

    # ── openWakeWord loop ─────────────────────────────────────────────────────

    def _oww_loop(self) -> None:
        try:
            import numpy as np  # noqa: F401
            import sounddevice as sd  # type: ignore
        except Exception as e:
            print(f"[wake_word] sounddevice unavailable: {e!r}")
            self._running = False
            return

        def _audio_callback(indata, frames, _time_info, _status):
            if not self._running:
                return
            try:
                # openWakeWord expects int16 1-D PCM.
                self._audio_q.put_nowait(indata[:, 0].copy())
            except queue.Full:
                # Drop oldest if backlog grows.
                try:
                    self._audio_q.get_nowait()
                    self._audio_q.put_nowait(indata[:, 0].copy())
                except Exception:
                    pass

        try:
            with sd.InputStream(
                samplerate=_SAMPLE_RATE,
                channels=1,
                dtype="int16",
                blocksize=_CHUNK_SAMPLES,
                callback=_audio_callback,
            ):
                print("[wake_word] openWakeWord listening (always-on, ~1% CPU)")
                while self._running:
                    if self._g.get("input_muted"):
                        # Drain queue & sleep so we don't spin.
                        try:
                            while True:
                                self._audio_q.get_nowait()
                        except queue.Empty:
                            pass
                        time.sleep(0.5)
                        continue
                    try:
                        chunk = self._audio_q.get(timeout=1.0)
                    except queue.Empty:
                        continue
                    try:
                        prediction = self._oww_model.predict(chunk)
                    except Exception as e:
                        print(f"[wake_word] predict error: {e!r}")
                        continue
                    fired = False
                    for name, score in prediction.items():
                        try:
                            s = float(score)
                        except Exception:
                            continue
                        if s >= self._oww_threshold:
                            print(f"[wake_word] {name} score={s:.2f}")
                            self._trigger_wake(source="openwakeword")
                            fired = True
                            break
                    if fired:
                        # Reset model state after a fire to clear scoring history.
                        try:
                            self._oww_model.reset()
                        except Exception:
                            pass
        except Exception as e:
            print(f"[wake_word] oww loop error: {e!r}")

    # ── Whisper-poll fallback (only if openWakeWord can't load) ──────────────

    def _whisper_poll_loop(self) -> None:
        self._backend = "whisper_poll"
        while self._running:
            try:
                if self._g.get("input_muted"):
                    time.sleep(1.0)
                    continue
                import numpy as np
                import sounddevice as sd  # type: ignore
                audio = sd.rec(int(1.5 * 16000), samplerate=16000, channels=1, dtype="float32")
                sd.wait()
                audio = np.squeeze(audio)
                stt_engine = self._g.get("stt_engine")
                if stt_engine is None or not getattr(stt_engine, "is_available", lambda: False)():
                    time.sleep(3.0)
                    continue
                # Reuse the production STT — no separate tiny model.
                result = stt_engine._transcribe_array(audio, sample_rate=16000)
                text = str((result or {}).get("text") or "").lower()
                if any(kw in text for kw in self._keywords):
                    self._trigger_wake(source="whisper_poll")
            except Exception:
                pass
            time.sleep(3.0)

    # ── lifecycle ──────────────────────────────────────────────────────────────

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        use_oww = self._try_init_oww()
        if use_oww:
            self._backend = "openwakeword"
            self._available = True
            target = self._oww_loop
        else:
            self._backend = "whisper_poll"
            self._available = True  # fallback still functional
            target = self._whisper_poll_loop
        self._thread = threading.Thread(target=target, daemon=True, name="ava-wake-word")
        self._thread.start()
        print(f"[wake_word] started backend={self._backend}")

    def stop(self) -> None:
        self._running = False

    @property
    def available(self) -> bool:
        return self._available

    @property
    def backend(self) -> str:
        return self._backend

    def get_pattern_summary(self) -> dict[str, Any]:
        if not self._patterns:
            return {"peak_hour": None, "total_activations": 0, "backend": self._backend}
        hours = [int(p.get("hour") or 0) for p in self._patterns if isinstance(p, dict)]
        peak = Counter(hours).most_common(1)[0][0] if hours else None
        return {
            "peak_hour": peak,
            "total_activations": len(self._patterns),
            "backend": self._backend,
        }
