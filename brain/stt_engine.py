from __future__ import annotations

import tempfile
import threading
import time
import wave
from pathlib import Path


class STTEngine:
    def __init__(self) -> None:
        self._available = False
        self._model = None
        self._backend = "none"
        self._lock = threading.Lock()
        self._init_model()

    def _init_model(self) -> None:
        # Whisper base: better accuracy than tiny especially for short phrases.
        # Try GPU first (cuda + float16), fall back to CPU int8.
        try:
            from faster_whisper import WhisperModel  # type: ignore
        except Exception as e:
            print(f"[stt_engine] faster_whisper import failed: {e!r}")
            self._model = None
            self._available = False
            return
        for device, compute in (("cuda", "float16"), ("cpu", "int8")):
            try:
                self._model = WhisperModel("base", device=device, compute_type=compute)
                self._available = True
                self._device = device
                print(f"[stt_engine] Whisper base loaded device={device} compute={compute}")
                return
            except Exception as e:
                print(f"[stt_engine] base on {device} failed ({e!r}) — trying next")
        self._model = None
        self._available = False

    def is_available(self) -> bool:
        return bool(self._available and self._model is not None)

    def backend_name(self) -> str:
        return self._backend

    # ── recording ──────────────────────────────────────────────

    def _record_sounddevice(self, seconds: float, sample_rate: int):
        import numpy as np  # type: ignore
        import sounddevice as sd  # type: ignore
        frames = int(max(1, round(seconds * sample_rate)))
        audio = sd.rec(frames, samplerate=sample_rate, channels=1, dtype="float32")
        sd.wait()
        self._backend = "sounddevice"
        return np.squeeze(audio, axis=1)

    def _record_pyaudio(self, seconds: float, sample_rate: int):
        import numpy as np  # type: ignore
        import pyaudio  # type: ignore
        pa = pyaudio.PyAudio()
        chunk = 1024
        stream = pa.open(format=pyaudio.paInt16, channels=1, rate=sample_rate, input=True, frames_per_buffer=chunk)
        total_chunks = max(1, int(sample_rate * seconds / chunk))
        chunks: list[bytes] = []
        try:
            for _ in range(total_chunks):
                chunks.append(stream.read(chunk, exception_on_overflow=False))
        finally:
            stream.stop_stream()
            stream.close()
            pa.terminate()
        data = b"".join(chunks)
        pcm = np.frombuffer(data, dtype=np.int16).astype("float32") / 32768.0
        self._backend = "pyaudio"
        return pcm

    def _record_audio(self, seconds: float = 5.0, sample_rate: int = 16000):
        try:
            return self._record_sounddevice(seconds, sample_rate), sample_rate
        except Exception:
            try:
                return self._record_pyaudio(seconds, sample_rate), sample_rate
            except Exception:
                return None, sample_rate

    # ── VAD helper ─────────────────────────────────────────────

    @staticmethod
    def _has_speech(audio, sample_rate: int = 16000, rms_threshold: float = 0.008, min_speech_seconds: float = 0.3) -> bool:
        """Return True if audio contains detectable speech above threshold."""
        try:
            import numpy as np
            block = int(sample_rate * 0.05)  # 50ms blocks
            speech_blocks = 0
            required_blocks = int(min_speech_seconds / 0.05)
            for start in range(0, len(audio) - block, block):
                chunk = audio[start:start + block]
                rms = float(np.sqrt(np.mean(chunk ** 2)))
                if rms > rms_threshold:
                    speech_blocks += 1
                    if speech_blocks >= required_blocks:
                        return True
            return False
        except Exception:
            return True  # fail open — let transcription decide

    # ── listen_session (VAD-gated, silence-terminated) ─────────

    def listen_session(
        self,
        max_seconds: float = 12.0,
        silence_seconds: float = 1.5,
        sample_rate: int = 16000,
        rms_threshold: float = 0.008,
    ) -> dict | None:
        """
        Opens microphone, streams 100ms blocks, stops when silence_seconds
        of quiet follows speech. Returns None immediately if no speech detected.
        Returns dict: {text, confidence, duration_seconds, speech_detected}.
        """
        if not self.is_available():
            return None
        try:
            import numpy as np
            import sounddevice as sd
        except ImportError:
            return self._listen_once_compat()

        t0 = time.monotonic()
        BLOCK = int(sample_rate * 0.1)  # 100ms
        all_audio: list = []
        speech_started = False
        last_speech_t = None

        with self._lock:
            try:
                stream = sd.InputStream(samplerate=sample_rate, channels=1, dtype="float32", blocksize=BLOCK)
                stream.start()
                self._backend = "sounddevice"
                while True:
                    elapsed = time.monotonic() - t0
                    if elapsed >= max_seconds:
                        break
                    block_data, _ = stream.read(BLOCK)
                    chunk = np.squeeze(block_data, axis=1) if block_data.ndim > 1 else block_data
                    all_audio.append(chunk)
                    rms = float(np.sqrt(np.mean(chunk ** 2)))
                    if rms > rms_threshold:
                        speech_started = True
                        last_speech_t = time.monotonic()
                    elif speech_started and last_speech_t is not None:
                        silent_for = time.monotonic() - last_speech_t
                        if silent_for >= silence_seconds:
                            break
                stream.stop()
                stream.close()
            except Exception:
                try:
                    stream.stop()
                    stream.close()
                except Exception:
                    pass
                return self._listen_once_compat()

        if not all_audio:
            return None
        try:
            audio = np.concatenate(all_audio)
        except Exception:
            return None

        duration = len(audio) / sample_rate
        if not self._has_speech(audio, sample_rate, rms_threshold):
            return {"text": None, "confidence": 0.0, "duration_seconds": duration, "speech_detected": False}

        result = self._transcribe_array(audio, sample_rate)
        result["duration_seconds"] = duration
        result["speech_detected"] = True
        return result

    def _transcribe_array(self, audio, sample_rate: int = 16000) -> dict:
        """Transcribe a numpy float32 array. Returns {text, confidence}."""
        try:
            import numpy as np
            clipped = np.clip(audio, -1.0, 1.0)
            pcm16 = (clipped * 32767.0).astype(np.int16)
        except Exception:
            return {"text": None, "confidence": 0.0}

        wav_path = Path(tempfile.gettempdir()) / "ava_stt_session.wav"
        try:
            with wave.open(str(wav_path), "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                wf.writeframes(pcm16.tobytes())
        except Exception:
            return {"text": None, "confidence": 0.0}

        try:
            segments, info = self._model.transcribe(
                str(wav_path),
                language="en",
                vad_filter=True,
                beam_size=5,  # better accuracy than greedy default
            )
            parts = []
            avg_logprob_sum = 0.0
            seg_count = 0
            for seg in segments:
                t = getattr(seg, "text", "").strip()
                if t:
                    parts.append(t)
                    avg_logprob_sum += float(getattr(seg, "avg_logprob", -1.0) or -1.0)
                    seg_count += 1
            text = " ".join(" ".join(p.split()) for p in parts).strip()
            # Convert avg_logprob (-inf..0) to 0..1 confidence
            if seg_count > 0:
                avg_lp = avg_logprob_sum / seg_count
                confidence = max(0.0, min(1.0, (avg_lp + 1.0)))  # -1.0 logprob → 0.0 conf
            else:
                confidence = 0.0
            return {"text": text or None, "confidence": round(confidence, 3)}
        except Exception:
            return {"text": None, "confidence": 0.0}

    def _listen_once_compat(self) -> dict | None:
        """Fallback: fixed 5s recording via pyaudio or sounddevice."""
        audio, sample_rate = self._record_audio(seconds=5.0, sample_rate=16000)
        if audio is None:
            return None
        try:
            import numpy as np
            peak = float(np.max(np.abs(audio))) if audio.size else 0.0
            if peak < 0.01:
                return {"text": None, "confidence": 0.0, "speech_detected": False, "duration_seconds": 5.0}
            if not self._has_speech(audio, sample_rate):
                return {"text": None, "confidence": 0.0, "speech_detected": False, "duration_seconds": 5.0}
        except Exception:
            pass
        result = self._transcribe_array(audio, sample_rate)
        result.setdefault("speech_detected", True)
        result.setdefault("duration_seconds", 5.0)
        return result

    def listen_once(self) -> str | None:
        """Legacy single-shot listen. Returns text or None."""
        result = self._listen_once_compat()
        if result is None:
            return None
        return result.get("text")
