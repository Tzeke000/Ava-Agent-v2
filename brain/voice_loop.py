"""
Phase 74 — Real Voice Loop (STT → LLM → TTS tight loop).

VoiceLoop runs as a background daemon thread.
States: passive → listening → thinking → speaking → passive

Starts automatically at launch when both TTS and STT are available.
Respects input_muted and tts_enabled globals.
"""
from __future__ import annotations

import threading
import time
from typing import Any


class VoiceLoop:
    STATES = ("passive", "listening", "thinking", "speaking")

    def __init__(self, g: dict[str, Any]) -> None:
        self._g = g
        self._state = "passive"
        self._active = False
        self._thread: threading.Thread | None = None

    # ── public interface ──────────────────────────────────────

    def start(self) -> bool:
        stt = self._g.get("stt_engine")
        tts = self._g.get("tts_engine")
        if stt is None or tts is None:
            return False
        if not (callable(getattr(stt, "is_available", None)) and stt.is_available()):
            return False
        if not (callable(getattr(tts, "is_available", None)) and tts.is_available()):
            return False
        self._active = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="ava-voice-loop")
        self._thread.start()
        print("[voice_loop] started passive listening")
        return True

    def stop(self) -> None:
        self._active = False

    @property
    def state(self) -> str:
        return self._state

    @property
    def active(self) -> bool:
        return self._active

    def on_wake(self) -> None:
        """Called by wake word / clap detector to trigger active listening."""
        if not self._active:
            return
        self._g["_voice_loop_wake_requested"] = True

    # ── internal loop ─────────────────────────────────────────

    def _set_state(self, state: str) -> None:
        self._state = state
        self._g["_voice_loop_state"] = state

    def _loop(self) -> None:
        while self._active:
            try:
                # Passive: wait for wake signal
                self._set_state("passive")
                self._wait_for_wake()
                if not self._active:
                    break
                # Active: listen, think, speak
                self._listen_and_respond()
            except Exception as e:
                print(f"[voice_loop] error in loop: {e}")
                self._set_state("passive")
                time.sleep(2.0)

    def _wait_for_wake(self) -> None:
        """Block until wake word / clap fires or _voice_loop_wake_requested is set."""
        while self._active:
            if self._g.get("_voice_loop_wake_requested") or self._g.get("_wake_word_detected"):
                self._g.pop("_voice_loop_wake_requested", None)
                self._g.pop("_wake_word_detected", None)
                return
            time.sleep(0.2)

    def _listen_and_respond(self) -> None:
        if self._g.get("input_muted"):
            return

        stt = self._g.get("stt_engine")
        tts = self._g.get("tts_engine")
        if stt is None or tts is None:
            return

        # Listening
        self._set_state("listening")
        print("[voice_loop] listening…")
        try:
            result = stt.listen_session(max_seconds=12.0, silence_seconds=1.5)
        except Exception:
            self._set_state("passive")
            return

        if result is None or not result.get("speech_detected"):
            self._set_state("passive")
            return
        text = str(result.get("text") or "").strip()
        if not text:
            self._set_state("passive")
            return

        print(f"[voice_loop] heard: {text[:120]!r}")

        # Thinking
        self._set_state("thinking")
        try:
            from brain.reply_engine import run_ava
            reply, _visual, _profile, _actions, _reflection = run_ava(text)
        except Exception as e:
            print(f"[voice_loop] run_ava failed: {e}")
            self._set_state("passive")
            return

        reply_text = str(reply or "").strip()
        if not reply_text:
            self._set_state("passive")
            return

        # Speaking
        self._set_state("speaking")
        import re as _re
        clean = _re.sub(r"[*_`#\[\]()]", "", reply_text)
        clean = _re.sub(r"\s+", " ", clean).strip()[:400]
        if clean and _re.search(r"[A-Za-z0-9]", clean):
            tts_enabled = bool(self._g.get("tts_enabled", False))
            if tts_enabled and callable(getattr(tts, "speak", None)):
                tts.speak(clean, blocking=True)

        self._set_state("passive")


# ── module singleton ──────────────────────────────────────────

_voice_loop_instance: VoiceLoop | None = None


def get_voice_loop(g: dict[str, Any] | None = None) -> VoiceLoop | None:
    global _voice_loop_instance
    return _voice_loop_instance


def start_voice_loop(g: dict[str, Any]) -> bool:
    global _voice_loop_instance
    loop = VoiceLoop(g)
    ok = loop.start()
    if ok:
        _voice_loop_instance = loop
        g["_voice_loop"] = loop
    return ok
