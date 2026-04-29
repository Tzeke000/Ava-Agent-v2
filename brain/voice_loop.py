"""
Phase 74 — Real Voice Loop (STT → LLM → TTS tight loop) with attentive state.

States:
  passive   → wait for wake word / clap. Slow polling.
  attentive → just finished speaking. Faster polling, no wake word required;
              any speech > 1s is treated as direct address. Decays back to
              passive after 60s of silence.
  listening → actively recording user speech.
  thinking  → run_ava is producing a reply.
  speaking  → TTS is playing.

Wake-word recognition uses brain.wake_detector. When a transcribed clip is
ambiguous, brain.wake_learner asks for clarification. After STT completes we
also analyse the audio with brain.voice_mood_detector and stash the result
for prompt_builder.
"""
from __future__ import annotations

import threading
import time
from typing import Any


_ATTENTIVE_TIMEOUT_SEC = 60.0       # decay back to passive after this long
_ATTENTIVE_MIN_SPEECH_SEC = 1.0     # speech longer than this counts as input
_DEFAULT_SILENCE_SEC = 2.5          # initial wait
_CONTINUE_SILENCE_SEC = 4.0         # if first transcript was short, wait longer
_LONG_SILENCE_SEC = 1.5             # if first transcript was long, end fast
_SHORT_WORDS = 3                    # under this → keep listening
_LONG_WORDS = 10                    # over this → end fast


class VoiceLoop:
    STATES = ("passive", "attentive", "listening", "thinking", "speaking")

    def __init__(self, g: dict[str, Any]) -> None:
        self._g = g
        self._state = "passive"
        self._active = False
        self._thread: threading.Thread | None = None
        self._last_audio_ts: float = 0.0  # any speech detected
        self._last_speak_end_ts: float = 0.0
        self._last_audio_array: Any = None  # cached for voice mood

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
                # ── Choose passive vs attentive ────────────────────────────
                in_attentive = (
                    self._last_speak_end_ts > 0
                    and (time.time() - self._last_speak_end_ts) < _ATTENTIVE_TIMEOUT_SEC
                )
                if in_attentive:
                    self._set_state("attentive")
                    triggered = self._attentive_wait()
                else:
                    self._set_state("passive")
                    triggered = self._passive_wait()
                if not self._active:
                    break
                if not triggered:
                    # attentive timed out → fall back to passive
                    continue
                self._listen_and_respond()
            except Exception as e:
                print(f"[voice_loop] error in loop: {e}")
                self._set_state("passive")
                time.sleep(2.0)

    def _passive_wait(self) -> bool:
        """Block until wake word / clap fires. Returns True when triggered."""
        while self._active:
            if self._g.get("_voice_loop_wake_requested") or self._g.get("_wake_word_detected"):
                self._g.pop("_voice_loop_wake_requested", None)
                self._g.pop("_wake_word_detected", None)
                return True
            time.sleep(0.2)
        return False

    def _attentive_wait(self) -> bool:
        """While in attentive state: poll mic faster, react to any speech > 1s
        without requiring a wake word. Decays to passive after 60s silence."""
        attentive_started = time.time()
        while self._active:
            # Wake / clap triggers immediately exit to listening.
            if self._g.get("_voice_loop_wake_requested") or self._g.get("_wake_word_detected"):
                self._g.pop("_voice_loop_wake_requested", None)
                self._g.pop("_wake_word_detected", None)
                return True
            # Quick mic snapshot for ~0.8s — if we hear something significant, trigger.
            stt = self._g.get("stt_engine")
            if stt is not None and callable(getattr(stt, "is_available", None)) and stt.is_available():
                try:
                    snap = stt.listen_session(max_seconds=0.8, silence_seconds=0.4)
                    if isinstance(snap, dict) and snap.get("speech_detected"):
                        dur = float(snap.get("duration_seconds") or 0)
                        if dur >= _ATTENTIVE_MIN_SPEECH_SEC:
                            # Stash the partial as initial input — listen_and_respond
                            # will continue from there.
                            self._g["_attentive_initial_text"] = snap.get("text") or ""
                            return True
                except Exception:
                    pass
            # Silence-only branch: time out after 60s.
            if (time.time() - self._last_speak_end_ts) >= _ATTENTIVE_TIMEOUT_SEC:
                return False
            time.sleep(0.4)
        return False

    def _silence_seconds_for(self, word_count: int) -> float:
        if word_count < _SHORT_WORDS:
            return _CONTINUE_SILENCE_SEC
        if word_count > _LONG_WORDS:
            return _LONG_SILENCE_SEC
        return _DEFAULT_SILENCE_SEC

    def _listen_and_respond(self) -> None:
        if self._g.get("input_muted"):
            print("[voice_loop] skipped — input_muted is True")
            return

        stt = self._g.get("stt_engine")
        tts = self._g.get("tts_engine")
        if stt is None or tts is None:
            print(f"[voice_loop] skipped — stt={'set' if stt else 'None'} tts={'set' if tts else 'None'}")
            return

        # ── LISTEN ────────────────────────────────────────────────────────────
        self._set_state("listening")
        print("[voice_loop] listening…")
        initial_text = str(self._g.pop("_attentive_initial_text", "") or "").strip()
        try:
            # Initial pass at 2.5s silence cutoff — most utterances finish here.
            result = stt.listen_session(max_seconds=12.0, silence_seconds=_DEFAULT_SILENCE_SEC)
        except Exception as e:
            print(f"[voice_loop] listen_session error: {e!r}")
            self._set_state("passive")
            return

        if result is None or not result.get("speech_detected"):
            # If we entered listening because attentive heard a partial, keep that.
            if initial_text:
                text = initial_text
                result = {"text": text, "speech_detected": True, "duration_seconds": 1.0}
            else:
                print("[voice_loop] no speech detected")
                self._set_state("passive")
                return
        text = str((result or {}).get("text") or "").strip()
        if initial_text and not text.lower().startswith(initial_text.lower()[:20]):
            text = (initial_text + " " + text).strip()

        # Word-count-aware continuation: if Zeke gave us only a couple words,
        # extend the silence window and keep listening up to 4s more.
        word_count = len(text.split())
        if word_count > 0 and word_count < _SHORT_WORDS:
            try:
                cont = stt.listen_session(max_seconds=6.0, silence_seconds=_CONTINUE_SILENCE_SEC)
                if isinstance(cont, dict) and cont.get("speech_detected"):
                    extra = str(cont.get("text") or "").strip()
                    if extra:
                        text = (text + " " + extra).strip()
                        print(f"[voice_loop] short utterance extended: +{len(extra)} chars")
            except Exception:
                pass

        if not text:
            print("[voice_loop] empty transcription after listen")
            self._set_state("passive")
            return
        print(f"[voice_loop] heard: {text[:120]!r}")

        # ── WAKE-WORD CHECK (passive mode only) ───────────────────────────────
        # In attentive state we already decided this is for Ava. In passive we
        # need to confirm direct address before invoking run_ava.
        in_attentive_when_started = self._state in ("attentive", "listening") and self._last_speak_end_ts > 0 and (
            time.time() - self._last_speak_end_ts
        ) < _ATTENTIVE_TIMEOUT_SEC

        if not in_attentive_when_started:
            try:
                from brain.wake_detector import get_wake_detector
                wd = get_wake_detector()
                is_direct, conf, reason = wd.classify(text, self._g)
                print(f"[voice_loop] wake-classify direct={is_direct} conf={conf:.2f} reason={reason}")
                # Borderline → ask for clarification via WakeLearner.
                if not is_direct or conf < 0.6:
                    try:
                        from brain.wake_learner import get_wake_learner
                        wl = get_wake_learner()
                        if wl is not None and wl.can_clarify():
                            asked = wl.ask_clarification(text, self._g)
                            if asked:
                                print("[voice_loop] asked wake clarification — skipping run_ava this turn")
                                self._set_state("passive")
                                return
                    except Exception as _e:
                        print(f"[voice_loop] wake clarify error: {_e!r}")
                    if not is_direct:
                        print("[voice_loop] not direct address — skipping")
                        self._set_state("passive")
                        return
            except Exception as e:
                print(f"[voice_loop] wake detector error: {e!r}")

        # ── VOICE MOOD ANALYSIS (best-effort, reuses STT audio) ───────────────
        try:
            self._analyze_voice_mood_from_result(result)
        except Exception as e:
            print(f"[voice_loop] voice mood error: {e!r}")

        # ── THINKING ──────────────────────────────────────────────────────────
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

        # ── SPEAKING ──────────────────────────────────────────────────────────
        self._set_state("speaking")
        import re as _re
        clean = _re.sub(r"[*_`#\[\]()]", "", reply_text)
        clean = _re.sub(r"\s+", " ", clean).strip()[:400]
        if not (clean and _re.search(r"[A-Za-z0-9]", clean)):
            print("[voice_loop] reply had no speakable content after cleanup")
            self._set_state("passive")
            return

        tts_enabled = bool(self._g.get("tts_enabled", False))
        if not tts_enabled:
            print("[voice_loop] TTS disabled in globals — not speaking. Toggle via /api/v1/tts/toggle.")
            self._set_state("passive")
            return

        spoke_ok = self._speak(clean)
        self._last_speak_end_ts = time.time() if spoke_ok else 0.0

        # Drop into attentive so a quick follow-up doesn't need a wake word.
        if spoke_ok:
            self._set_state("attentive")
        else:
            self._set_state("passive")

    # ── helpers ───────────────────────────────────────────────────────────────

    def _analyze_voice_mood_from_result(self, stt_result: dict | None) -> None:
        """Run voice_mood_detector on the audio array STT already captured.

        Avoids the 1.5s extra recording the previous implementation did. If the
        STT result doesn't include the audio (older API or fallback path), we
        just skip — no fresh recording, no added latency. Best-effort.
        """
        det = self._g.get("_voice_mood_detector")
        if det is None or not getattr(det, "available", False):
            return
        if not isinstance(stt_result, dict):
            return
        audio = stt_result.get("audio_array")
        sr = int(stt_result.get("sample_rate") or 16000)
        if audio is None:
            return
        try:
            mood = det.analyze(audio, sr=sr)
            mood["ts"] = time.time()
            self._g["_voice_mood"] = mood
            print(
                f"[voice_mood] {mood.get('label')} energy={mood.get('energy')} "
                f"q={mood.get('is_question')} (reused STT audio)"
            )
        except Exception as e:
            print(f"[voice_mood] analyze error: {e!r}")

    def _speak(self, clean: str) -> bool:
        worker = self._g.get("_tts_worker")
        if worker is not None and getattr(worker, "available", False):
            try:
                emotion = "neutral"
                intensity = 0.5
                try:
                    mood_state = self._g.get("_current_mood")
                    if isinstance(mood_state, dict):
                        emotion = str(mood_state.get("current_mood") or mood_state.get("primary_emotion") or "neutral")
                        intensity = float(mood_state.get("energy") or mood_state.get("intensity") or 0.5)
                    else:
                        load_mood = self._g.get("load_mood")
                        if callable(load_mood):
                            m = load_mood() or {}
                            emotion = str(m.get("current_mood") or m.get("primary_emotion") or "neutral")
                            intensity = float(m.get("energy") or m.get("intensity") or 0.5)
                except Exception:
                    pass
                print(f"[voice_loop] speaking response ({len(clean)} chars) emotion={emotion} intensity={intensity:.2f}")
                worker.speak_with_emotion(clean, emotion=emotion, intensity=intensity, blocking=True)
                print("[voice_loop] done speaking (worker)")
                return True
            except Exception as e:
                print(f"[voice_loop] worker.speak_with_emotion failed: {e!r} — falling back to tts_engine")

        tts = self._g.get("tts_engine")
        speak_callable = callable(getattr(tts, "speak", None))
        if not speak_callable:
            print("[voice_loop] tts.speak is not callable")
            return False
        try:
            print(f"[voice_loop] speaking response ({len(clean)} chars) via tts_engine fallback")
            tts.speak(clean, blocking=True)
            print("[voice_loop] done speaking (engine)")
            return True
        except Exception as e:
            print(f"[voice_loop] TTS failed to speak: {e!r}")
            return False


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
