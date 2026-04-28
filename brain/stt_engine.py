from __future__ import annotations

import tempfile
import threading
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
        try:
            from faster_whisper import WhisperModel  # type: ignore

            self._model = WhisperModel("tiny", device="cpu", compute_type="int8")
            self._available = True
        except Exception:
            self._model = None
            self._available = False

    def is_available(self) -> bool:
        return bool(self._available and self._model is not None)

    def backend_name(self) -> str:
        return self._backend

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
        stream = pa.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=sample_rate,
            input=True,
            frames_per_buffer=chunk,
        )
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

    def listen_once(self) -> str | None:
        if not self.is_available():
            return None
        with self._lock:
            audio, sample_rate = self._record_audio(seconds=5.0, sample_rate=16000)
            if audio is None:
                return None
            try:
                import numpy as np  # type: ignore

                peak = float(np.max(np.abs(audio))) if audio.size else 0.0
                if peak < 0.01:
                    return None
                clipped = np.clip(audio, -1.0, 1.0)
                pcm16 = (clipped * 32767.0).astype(np.int16)
            except Exception:
                return None

            wav_path = Path(tempfile.gettempdir()) / "ava_stt_listen_once.wav"
            try:
                with wave.open(str(wav_path), "wb") as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(sample_rate)
                    wf.writeframes(pcm16.tobytes())
            except Exception:
                return None

            try:
                segments, _info = self._model.transcribe(str(wav_path), language="en", vad_filter=True)
                text = " ".join(seg.text.strip() for seg in segments if getattr(seg, "text", "").strip())
                text = " ".join(text.split()).strip()
                return text or None
            except Exception:
                return None
