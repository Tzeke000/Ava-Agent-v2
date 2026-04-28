from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

try:
    import winsound  # type: ignore[attr-defined]
except Exception:  # pragma: no cover
    winsound = None


def _cleanup_spoken_text(text: str) -> str:
    t = str(text or "")
    t = re.sub(r"\[TOOL:[^\]]*\]", " ", t, flags=re.IGNORECASE)
    cleaned_lines: list[str] = []
    for line in t.splitlines():
        low = line.strip().lower()
        if not low:
            continue
        if low.startswith("camera:") or low.startswith("face status:") or low.startswith("recognition:"):
            continue
        if low.startswith("expression:") or low.startswith("vision status:"):
            continue
        cleaned_lines.append(line)
    t = "\n".join(cleaned_lines)
    t = re.sub(r"[#*_`~]", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _bridge_script() -> str:
    return r"""
import argparse
import os
import sys


def _safe_fail(msg: str, code: int = 2):
    print(msg, file=sys.stderr)
    raise SystemExit(code)


def _stub_japanese_deps():
    class _DummyMeCab:
        def __init__(self, *args, **kwargs):
            pass

        def parse(self, text):
            return text

    import types
    sys.modules.setdefault("MeCab", types.SimpleNamespace(Tagger=_DummyMeCab))


def _load_melo_tts(language: str = "EN"):
    _stub_japanese_deps()
    last_err = None
    for mod_name in ("melo.api", "MeloTTS.melo.api"):
        try:
            mod = __import__(mod_name, fromlist=["TTS"])
            TTS = getattr(mod, "TTS")
            return TTS(language=language)
        except Exception as e:
            last_err = e
            continue
    if last_err is not None:
        raise last_err
    raise RuntimeError("MeloTTS TTS import failed")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["check", "synth"], required=True)
    ap.add_argument("--text", default="")
    ap.add_argument("--wav", default="")
    ap.add_argument("--speaker", default="0")
    args = ap.parse_args()

    try:
        model = _load_melo_tts(language="EN")
        if args.mode == "check":
            print("ok")
            return
        if not args.wav:
            _safe_fail("missing --wav", 3)
        text = (args.text or "").strip()
        if not text:
            _safe_fail("missing text", 4)
        speaker = int(args.speaker or 0)
        model.tts_to_file(text, speaker, args.wav)
        print("ok")
        return
    except Exception as e:
        _safe_fail(f"melo_bridge_error: {e}", 5)


if __name__ == "__main__":
    main()
""".strip()


class TTSEngine:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._player_thread: threading.Thread | None = None
        self._last_wav: str | None = None
        self._engine = "none"
        self._available = False
        self._speaker_id = 0
        self._bridge_path = self._ensure_bridge_script()
        self._pyttsx3 = None
        self._init_engine()

    def _ensure_bridge_script(self) -> Path:
        state_dir = Path(__file__).resolve().parent.parent / "state"
        state_dir.mkdir(parents=True, exist_ok=True)
        path = state_dir / "melo_tts_bridge.py"
        try:
            path.write_text(_bridge_script(), encoding="utf-8")
        except Exception:
            pass
        return path

    def _run_py311(self, args: list[str], *, timeout: float = 20.0) -> subprocess.CompletedProcess[str]:
        cmd = ["py", "-3.11"] + args
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)

    def _init_engine(self) -> None:
        try:
            res = self._run_py311([str(self._bridge_path), "--mode", "check"], timeout=30.0)
            if res.returncode == 0:
                self._engine = "melotts"
                self._available = True
                return
        except Exception:
            pass

        try:
            import pyttsx3  # type: ignore

            self._pyttsx3 = pyttsx3.init()
            self._engine = "pyttsx3"
            self._available = True
        except Exception:
            self._engine = "none"
            self._available = False

    def is_available(self) -> bool:
        return bool(self._available)

    def engine_name(self) -> str:
        return self._engine

    def _play_wav_blocking(self, wav_path: str) -> None:
        if winsound is None:
            return
        try:
            winsound.PlaySound(wav_path, winsound.SND_FILENAME)
        except Exception:
            pass

    def _play_wav(self, wav_path: str, blocking: bool) -> None:
        if winsound is None:
            return
        self.stop()
        if blocking:
            self._play_wav_blocking(wav_path)
            return
        t = threading.Thread(target=self._play_wav_blocking, args=(wav_path,), daemon=True, name="ava-tts-playback")
        self._player_thread = t
        t.start()

    def _speak_pyttsx3(self, text: str, blocking: bool) -> None:
        if self._pyttsx3 is None:
            return
        self.stop()
        if blocking:
            self._pyttsx3.say(text)
            self._pyttsx3.runAndWait()
            return

        def _worker() -> None:
            try:
                self._pyttsx3.say(text)
                self._pyttsx3.runAndWait()
            except Exception:
                pass

        t = threading.Thread(target=_worker, daemon=True, name="ava-tts-pyttsx3")
        self._player_thread = t
        t.start()

    def speak(self, text: str, blocking: bool = False) -> None:
        if not self._available:
            return
        clean = _cleanup_spoken_text(text)
        if not clean:
            return
        with self._lock:
            if self._engine == "melotts":
                wav_path = Path(tempfile.gettempdir()) / f"ava_tts_{int(time.time()*1000)}.wav"
                try:
                    res = self._run_py311(
                        [
                            str(self._bridge_path),
                            "--mode",
                            "synth",
                            "--text",
                            clean,
                            "--wav",
                            str(wav_path),
                            "--speaker",
                            str(self._speaker_id),
                        ],
                        timeout=45.0,
                    )
                    if res.returncode != 0 or not wav_path.is_file():
                        # Melo failed mid-session; pivot to pyttsx3 when available.
                        if self._pyttsx3 is None:
                            try:
                                import pyttsx3  # type: ignore

                                self._pyttsx3 = pyttsx3.init()
                            except Exception:
                                self._available = False
                                self._engine = "none"
                                return
                        self._engine = "pyttsx3"
                        self._speak_pyttsx3(clean, blocking)
                        return
                    self._last_wav = str(wav_path)
                    self._play_wav(str(wav_path), blocking=blocking)
                    return
                except Exception:
                    return
            if self._engine == "pyttsx3":
                self._speak_pyttsx3(clean, blocking)

    def stop(self) -> None:
        try:
            if winsound is not None:
                winsound.PlaySound(None, winsound.SND_PURGE)
        except Exception:
            pass
        try:
            if self._pyttsx3 is not None:
                self._pyttsx3.stop()
        except Exception:
            pass
