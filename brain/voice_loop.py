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
        prev = self._state
        self._state = state
        self._g["_voice_loop_state"] = state
        if prev != state:
            print(f"[voice_loop] state: {prev} → {state}")

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
            print("[voice_loop] skipped — input_muted is True")
            return

        stt = self._g.get("stt_engine")
        tts = self._g.get("tts_engine")
        if stt is None or tts is None:
            print(f"[voice_loop] skipped — stt={'set' if stt else 'None'} tts={'set' if tts else 'None'}")
            return

        # Listening
        self._set_state("listening")
        print("[voice_loop] listening…")
        try:
            result = stt.listen_session(max_seconds=12.0, silence_seconds=1.5)
        except Exception as e:
            print(f"[voice_loop] listen_session error: {e!r}")
            self._set_state("passive")
            return

        if result is None or not result.get("speech_detected"):
            print("[voice_loop] no speech detected")
            self._set_state("passive")
            return
        text = str(result.get("text") or "").strip()
        if not text:
            print("[voice_loop] speech detected but empty transcription")
            self._set_state("passive")
            return

        print(f"[voice_loop] heard: {text[:120]!r}")

        # Thinking
        self._set_state("thinking")
        print(f"[voice_loop] calling run_ava with: {text[:100]!r}")
        try:
            from brain.reply_engine import run_ava
            run_ava_result = run_ava(text)
            reply, _visual, _profile, _actions, _reflection = run_ava_result
            print(f"[voice_loop] run_ava returned reply_chars={len(str(reply or ''))}")
        except Exception as e:
            import traceback as _tb
            print(f"[voice_loop] run_ava failed: {e!r}\n{_tb.format_exc()[:600]}")
            self._set_state("passive")
            return

        reply_text = str(reply or "").strip()
        if not reply_text:
            print("[voice_loop] reply was empty — nothing to speak")
            self._set_state("passive")
            return
        print(f"[voice_loop] reply preview: {reply_text[:80]!r}")

        # Speaking
        self._set_state("speaking")
        import re as _re
        clean = _re.sub(r"[*_`#\[\]()]", "", reply_text)
        clean = _re.sub(r"\s+", " ", clean).strip()[:400]
        if not (clean and _re.search(r"[A-Za-z0-9]", clean)):
            print("[voice_loop] reply had no speakable content after cleanup")
            self._set_state("passive")
            return

        tts_enabled = bool(self._g.get("tts_enabled", False))
        speak_callable = callable(getattr(tts, "speak", None))
        print(f"[voice_loop] tts check: enabled={tts_enabled} speak_callable={speak_callable} engine={getattr(tts, '_engine_name', '?')}")
        if not tts_enabled:
            print("[voice_loop] TTS disabled in globals — not speaking. Toggle via /api/v1/tts/toggle.")
            self._set_state("passive")
            return
        if not speak_callable:
            print("[voice_loop] tts.speak is not callable")
            self._set_state("passive")
            return

        try:
            print(f"[voice_loop] speaking response ({len(clean)} chars)…")
            tts.speak(clean, blocking=True)
            print("[voice_loop] done speaking")
        except Exception as e:
            print(f"[voice_loop] TTS failed to speak: {e!r}")

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
