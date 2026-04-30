"""
brain/reply_engine.py — Main Ava response pipeline.

run_ava extracted from avaagent.py. Handles routing, model selection,
reply guards, tool execution, and delegates to turn_handler for finalization.
"""
from __future__ import annotations

import concurrent.futures
import time
import uuid
from pathlib import Path
from typing import Any

_RUN_AVA_TUNING_SOURCE_LOGGED = False
_PROMPT_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=2, thread_name_prefix="ava-prompt")


def _trace(label: str) -> None:  # TRACE-PHASE1
    """Timestamped diagnostic trace for the run_ava path. Removed/gated in Phase 3."""  # TRACE-PHASE1
    ts = time.strftime("%H:%M:%S") + f".{int(time.time()*1000)%1000:03d}"  # TRACE-PHASE1
    print(f"[trace] {ts} {label}")  # TRACE-PHASE1

# Simple greetings / mood checks / quick factual questions — bypass full
# pipeline for sub-5s response.
_SIMPLE_PATTERNS = (
    "how are you", "how do you feel", "what are you doing",
    "hey ava", "hello ava", "hi ava", "hello", "hi ", "hey ",
    "what's up", "whats up", "sup ava",
    "good morning", "good afternoon", "good evening", "good night",
    "how is your day", "how's it going", "hows it going",
    "what are you thinking", "you there", "you awake", "you up",
    # Time/date — these have voice_command_router builtins, but if the user
    # phrases it indirectly ("can you tell me what time"), the router may
    # miss; route to the fast-path so we never hit the deep LLM path.
    "what time", "what's the time", "whats the time", "what is the time",
    "what day", "what's the date", "what is the date", "what's today",
    # Quick "tell me" prompts that don't need memory or tools.
    "tell me a joke", "one sentence joke", "tell a joke",
    # Single-word probes
    "thanks", "thank you", "ok ava", "okay ava", "got it",
)


def _is_simple_question(text: str) -> bool:
    t = (text or "").lower().strip()
    if not t:
        return False
    if len(t.split()) > 15:
        return False
    # Strip trailing punctuation for matching
    t = t.rstrip("?!.,").strip()
    if t in ("hi", "hey", "hello", "yo"):
        return True
    return any(p in t for p in _SIMPLE_PATTERNS)


def _with_timeout(fn, timeout: float, fallback=None, label: str = ""):
    """Run fn() in a thread; return fallback if it exceeds timeout seconds."""
    try:
        fut = _PROMPT_EXECUTOR.submit(fn)
        return fut.result(timeout=timeout)
    except concurrent.futures.TimeoutError:
        print(f"[run_ava] timeout ({timeout}s) in {label} — using fallback")
        return fallback
    except Exception as e:
        print(f"[run_ava] error in {label}: {e!r}")
        return fallback


def run_ava(
    user_input: str, image: Any = None, active_person_id: str | None = None
) -> tuple[str, dict, dict, list[str], dict]:
    global _RUN_AVA_TUNING_SOURCE_LOGGED
    import avaagent as _av
    _g = vars(_av)

    from brain.prompt_builder import build_prompt, build_prompt_fast
    from brain.turn_handler import finalize_ava_turn
    from langchain_ollama import ChatOllama
    from brain.turn_visual import default_visual_payload
    from brain.output_guard import scrub_visible_reply
    from brain.selfstate import is_selfstate_query, build_selfstate_reply
    from brain.shutdown_ritual import is_shutdown_trigger, run_shutdown_ritual

    llm = _av.llm
    workspace = _av.workspace
    LLM_MODEL = _av.LLM_MODEL
    BASE_DIR = _av.BASE_DIR
    OWNER_PERSON_ID = _av.OWNER_PERSON_ID

    if not _RUN_AVA_TUNING_SOURCE_LOGGED:
        _RUN_AVA_TUNING_SOURCE_LOGGED = True
        print("[run_ava] tuning layer: config/ava_tuning.py")

    active_person_id = active_person_id or _av.get_active_person_id()
    _inp = (user_input or "").strip()
    _g["_last_user_interaction_ts"] = time.time()
    _g["_last_user_message_ts"] = time.time()
    _g["_last_user_input"] = _inp
    _u_low = _inp.lower()
    _g["_desktop_tier3_approved"] = any(
        k in _u_low for k in ("yes do it", "go ahead", "yes, do it", "go ahead and do it")
    )

    _t_start = time.time()  # used to time every step

    def _elapsed() -> str:
        return f"{time.time()-_t_start:.2f}s"

    _trace(f"re.run_ava.start chars={len(_inp)}")  # TRACE-PHASE1
    print(f"[perf] run_ava start person={active_person_id} has_image={image is not None} input_chars={len(_inp)}")

    # ── VOICE COMMAND ROUTER (intercept before LLM) ──────────────────────────
    # Pattern-matches the input against built-in + custom commands. If it
    # matches, the action runs, the response is spoken via the TTS worker, the
    # turn is logged to chat_history, and we return without invoking the LLM.
    try:
        from brain.voice_commands import get_voice_command_router
        from brain.turn_visual import default_visual_payload
        from brain.output_guard import scrub_visible_reply
        _router = get_voice_command_router(BASE_DIR)
        if _router is not None and _inp:
            _handled, _response = _router.route(_inp, _g)
            if _handled and _response:
                print(f"[voice_commands] matched: {_inp[:60]!r} → {_response[:80]!r}")
                # Persist to canonical history + chat_history.jsonl so the UI
                # picks it up like any other turn.
                try:
                    _canon = list(_av._get_canonical_history())
                    _canon.append({"role": "user", "content": user_input})
                    _canon.append({"role": "assistant", "content": _response})
                    _av._set_canonical_history(_canon)
                except Exception:
                    pass
                try:
                    import json as _json
                    from pathlib import Path as _Path
                    _hp = _Path(BASE_DIR) / "state" / "chat_history.jsonl"
                    _hp.parent.mkdir(parents=True, exist_ok=True)
                    _now = time.time()
                    _emo = "neutral"
                    try:
                        _emo = str(_av.load_mood().get("current_mood") or "neutral")
                    except Exception:
                        pass
                    with _hp.open("a", encoding="utf-8") as _f:
                        _f.write(_json.dumps({"ts": _now, "role": "user", "content": user_input}, ensure_ascii=False) + "\n")
                        _f.write(_json.dumps({
                            "ts": _now, "role": "assistant", "content": _response,
                            "model": "voice_command_router", "emotion": _emo,
                            "turn_route": "voice_command",
                        }, ensure_ascii=False) + "\n")
                except Exception:
                    pass
                _profile_vc = _av.load_profile_by_id(active_person_id)
                _vis_vc = default_visual_payload(
                    face_status="—", recognition_status="—", expression_status="—",
                    memory_preview="", turn_route="voice_command",
                    visual_truth_trusted=False, vision_status="voice_command",
                )
                _g["_ava_thinking"] = False
                return scrub_visible_reply(_response), _vis_vc, _profile_vc, [], {"voice_command": True}
    except Exception as _vce:
        print(f"[run_ava] voice_command router error (non-fatal): {_vce!r}")

    # Set thinking flag — UI uses this to show fast blue pulse animation
    _g["_ava_thinking"] = True
    _g["_ava_thinking_since"] = time.time()

    # ── Step: dual-brain foreground signal ────────────────────────────────────
    print(f"[perf] pre-dual-brain {_elapsed()}")
    _db = None
    try:
        from brain.dual_brain import get_dual_brain
        _db = get_dual_brain(_g)
        if _db is not None:
            _db.mark_foreground_start()
            # Tell Stream B to drop what it's doing — Zeke is talking to us.
            # The Ollama lock will serialize anyway, but pausing Stream B first
            # frees the GPU faster for the foreground model.
            try:
                _db.pause_background_now()
            except Exception:
                pass
            _live = _db.get_live_thought()
            if _live:
                _g["_dual_brain_live_thought"] = _live
    except Exception:
        _db = None
    print(f"[perf] post-dual-brain {_elapsed()}")

    # ── Step: gaze-to-screen trigger check ───────────────────────────────────
    print("[run_ava] step: gaze trigger check")
    try:
        _gaze_triggers = ("look at", "see that", "that thing", "over there",
                          "right there", "this one", "that one")
        if any(t in _u_low for t in _gaze_triggers):
            from brain.eye_tracker import get_eye_tracker
            _et = get_eye_tracker()
            if _et is not None and _et.available:
                import threading as _gaze_thread
                def _async_gaze():
                    try:
                        _av.camera_manager.capture_gaze_target(_g)
                    except Exception:
                        pass
                _gaze_thread.Thread(target=_async_gaze, daemon=True, name="ava-gaze-capture").start()
    except Exception:
        pass

    try:
        # ── FAST PATH: simple greetings / mood checks ────────────────────────
        # Bypass workspace.tick, episodic search, concept graph, vector retrieval,
        # privacy scan, dual-brain, etc. Just identity + mood + last 2 messages
        # + LLM. Target: sub-5-second response for "hey ava" style inputs.
        if _is_simple_question(_inp):
            _trace("re.run_ava.fast_path_entered")  # TRACE-PHASE1
            print(f"[run_ava] FAST PATH: simple question (t={time.time()-_t_start:.2f}s)")
            try:
                from langchain_core.messages import HumanMessage
                # Mood
                _mood_label = "calm"
                try:
                    _m = _av.load_mood()
                    _mood_label = str(_m.get("primary_emotion") or _m.get("current_mood") or "calm")
                except Exception:
                    pass
                # Last 2 turns from canonical history
                _last_msgs_str = ""
                try:
                    _hist = list(_av._get_canonical_history())[-4:]
                    _last_msgs_str = "\n".join(
                        f"{m.get('role', 'user')}: {str(m.get('content') or '')[:200]}"
                        for m in _hist
                        if isinstance(m, dict)
                    )
                except Exception:
                    pass
                # Identity (truncated for speed)
                _identity = str(_g.get("_AVA_IDENTITY_BLOCK") or "")[:500]
                _person_name = ""
                try:
                    _profile_for_fp = _av.load_profile_by_id(active_person_id)
                    _person_name = str(_profile_for_fp.get("name") or "").strip()
                except Exception:
                    _profile_for_fp = None
                _addressee = f" Talking to {_person_name}." if _person_name else ""
                _simple_prompt = (
                    f"You are Ava — a local adaptive AI companion to Zeke.{_addressee}\n"
                    f"Identity: {_identity}\n"
                    f"Current mood: {_mood_label}.\n"
                    f"Recent conversation:\n{_last_msgs_str}\n\n"
                    f"User just said: {user_input}\n"
                    f"Respond naturally and warmly in 1-3 sentences. Don't add any tool blocks or formatting."
                )
                # Prefer the identity-baked ava-gemma4 model for the simple
                # fast path; fall back to whatever _pick_fast_model_fallback
                # finds, then to the configured LLM_MODEL.
                _fast_pick = _av._pick_fast_model_fallback()
                _fast_model = _fast_pick or str(_av.LLM_MODEL or "ava-personal:latest")
                print(f"[perf] fast pre-llm-init {_elapsed()}")
                # Cap fast-path replies at ~80 tokens — concise replies are also
                # dramatically faster (less generation time, no waiting for the
                # model to wind down a long reply).
                _llm_fast = ChatOllama(model=_fast_model, temperature=0.7, num_predict=80)
                print(f"[perf] fast post-llm-init {_elapsed()}")
                from brain.ollama_lock import with_ollama
                print(f"[perf] fast pre-invoke {_elapsed()} model={_fast_model}")
                _trace(f"re.ollama_invoke_start fast model={_fast_model}")  # TRACE-PHASE1
                _fast_invoke_t0 = time.time()  # TRACE-PHASE1
                _fp_result = with_ollama(
                    lambda: _llm_fast.invoke([HumanMessage(content=_simple_prompt)]),
                    label=f"fast:{_fast_model}",
                )
                _trace(f"re.ollama_invoke_done fast ms={int((time.time()-_fast_invoke_t0)*1000)}")  # TRACE-PHASE1
                _g["_last_invoked_model"] = _fast_model
                print(f"[perf] fast post-invoke {_elapsed()}")
                _reply_text = (getattr(_fp_result, "content", str(_fp_result)) or "").strip()
                if not _reply_text:
                    _reply_text = "I'm here."
                _reply_text = scrub_visible_reply(_reply_text)
                print(f"[run_ava] FAST PATH complete in {time.time()-_t_start:.2f}s reply_chars={len(_reply_text)}")
                # Append assistant reply to canonical history so the next turn sees it
                try:
                    _canon_after = list(_av._get_canonical_history())
                    _canon_after.append({"role": "assistant", "content": _reply_text})
                    _av._set_canonical_history(_canon_after)
                except Exception:
                    pass
                # Build minimal visual payload + active profile and return
                _vis_fast = default_visual_payload(
                    face_status="—", recognition_status="—",
                    expression_status="—", memory_preview="",
                    turn_route="fast_simple", visual_truth_trusted=False,
                    vision_status="fast_path",
                )
                if _profile_for_fp is None:
                    _profile_for_fp = _av.load_profile_by_id(active_person_id)
                _trace(f"re.run_ava.return path=fast ms={int((time.time()-_t_start)*1000)}")  # TRACE-PHASE1
                return _reply_text, _vis_fast, _profile_for_fp, [], {"fast_path": True}
            except Exception as _fpe:
                print(f"[run_ava] FAST PATH error: {_fpe!r} — falling through to normal path")

        # ── Step: connectivity notice ─────────────────────────────────────────
        print(f"[perf] pre-connectivity {_elapsed()}")
        _conn_changed = bool(_g.get("_connectivity_changed"))
        if _conn_changed:
            _conn_to = str(_g.get("_connectivity_changed_to") or "")
            _g["_connectivity_changed"] = False
            if _conn_to == "online":
                _g["_connectivity_notice"] = "SYSTEM: Internet connection restored. Cloud models now available."
            else:
                _g["_connectivity_notice"] = "SYSTEM: Internet connection lost. Switching to local models only."

        # ── Step: morning briefing (background only — never blocks main thread) ─
        print("[run_ava] step: morning briefing check")
        if not _g.get("_morning_briefing_checked"):
            _g["_morning_briefing_checked"] = True
            try:
                from brain.morning_briefing import should_brief
                if should_brief(_g):
                    # Run briefing generation in background thread — result stored for next turn
                    import threading as _mb_thread
                    def _bg_briefing():
                        try:
                            from brain.morning_briefing import deliver_briefing
                            _b = deliver_briefing(_g)
                            if _b:
                                _g["_pending_morning_briefing"] = _b
                        except Exception as _be:
                            print(f"[run_ava] morning briefing bg error: {_be}")
                    _mb_thread.Thread(target=_bg_briefing, daemon=True, name="ava-morning-brief").start()
            except Exception as _mb_e:
                print(f"[run_ava] morning briefing check error: {_mb_e}")

        # ── Step: onboarding trigger detection ───────────────────────────────
        print("[run_ava] step: onboarding trigger check")
        try:
            from brain.person_onboarding import (
                detect_onboarding_trigger, detect_refresh_trigger,
                start_onboarding, run_onboarding_step, refresh_profile,
            )
            if detect_refresh_trigger(_inp) and _g.get("_onboarding_flow") is None:
                _ref = refresh_profile(active_person_id, _g)
                _ref_reply = (
                    "Sure, let me update your profile. Let's start with some fresh photos."
                    if _ref.get("action") == "retake_photos"
                    else "I've noted the update. Is there anything specific you'd like me to know?"
                )
                _ap = _av.load_profile_by_id(active_person_id)
                return finalize_ava_turn(user_input, _ref_reply, {}, _ap, [], turn_route="profile_refresh")
            _ob_triggered, _ob_name = detect_onboarding_trigger(_inp)
            if _ob_triggered and _g.get("_onboarding_flow") is None:
                _ob_person_id = f"person_{uuid.uuid4().hex[:8]}"
                _ob_flow = start_onboarding(_ob_person_id, Path(BASE_DIR), name_hint=_ob_name)
                _g["_onboarding_flow"] = _ob_flow
                _g["_onboarding_stage"] = _ob_flow.stage
        except Exception as _ob_e:
            print(f"[run_ava] onboarding trigger check error: {_ob_e}")

        # ── Step: onboarding flow routing ─────────────────────────────────────
        if _g.get("_onboarding_flow") is not None:
            print("[run_ava] step: onboarding flow step")
            try:
                from brain.person_onboarding import run_onboarding_step
                _ob_result = run_onboarding_step(_inp, _g)
                if _ob_result is not None:
                    _ob_reply, _ob_stage, _ob_done = _ob_result
                    _ap = _av.load_profile_by_id(active_person_id)
                    return finalize_ava_turn(user_input, _ob_reply, {}, _ap, [], turn_route="onboarding")
            except Exception as _ob_e:
                print(f"[run_ava] onboarding step error: {_ob_e}")
                _g["_onboarding_flow"] = None

        # ── Step: concern reconciliation ──────────────────────────────────────
        print("[run_ava] step: concern reconciliation")
        try:
            from brain.concern_reconciliation import mark_concern_user_dismissed
            _redir = _av._user_redirected_topic(user_input)
            if _redir == "camera":
                mark_concern_user_dismissed("camera_stale", _g)
                mark_concern_user_dismissed("recognition_uncertain", _g)
            elif _redir in ("memory", "general"):
                mark_concern_user_dismissed("maintenance_workbench", _g)
        except Exception:
            pass

        print("[run_ava] step: load active profile")
        active_profile = _av.load_profile_by_id(active_person_id)

        # ── Step: shutdown / inner life / guard routes ────────────────────────
        print("[run_ava] step: special route checks")
        if is_shutdown_trigger(user_input):
            ritual_goodbye = scrub_visible_reply(run_shutdown_ritual(_g))
            return finalize_ava_turn(user_input, ritual_goodbye, {}, active_profile, [], turn_route="shutdown_ritual")

        if _av._is_thinking_or_topic_prompt(user_input):
            from brain.inner_monologue import current_thought as inner_current_thought, get_conversation_starter as inner_get_conversation_starter
            from brain.curiosity_topics import get_current_curiosity
            thought = inner_current_thought(BASE_DIR)
            starter = inner_get_conversation_starter(
                BASE_DIR,
                idle_seconds=time.time() - float(_g.get("_last_user_interaction_ts") or time.time()),
            )
            cur = get_current_curiosity(_g)
            topic_line = str((cur or {}).get("topic") or "").strip()
            reply = thought or starter or (
                f"I have been wondering about {topic_line}." if topic_line else "I have been reflecting on our recent conversations."
            )
            return finalize_ava_turn(user_input, scrub_visible_reply(reply), {}, active_profile, [], turn_route="inner_life_prompt")

        from brain.persona_switcher import should_deflect, get_blocked_reply, get_deflect_reply
        from brain.trust_manager import is_blocked
        if is_blocked(active_profile):
            reply = get_blocked_reply()
            vs = default_visual_payload(
                face_status="Not evaluated (blocked)", recognition_status="—",
                expression_status="—", memory_preview="", turn_route="blocked",
                visual_truth_trusted=False, vision_status="blocked_policy",
            )
            print(f"[run_ava] exit route=blocked")
            return reply, vs, active_profile, [], {}

        if should_deflect(active_profile, user_input):
            reply = get_deflect_reply(active_profile, user_input)
            vs = default_visual_payload(
                face_status="Not evaluated (deflect)", recognition_status="—",
                expression_status="—", memory_preview="", turn_route="deflect",
                visual_truth_trusted=False, vision_status="deflect",
            )
            print(f"[run_ava] exit route=deflect")
            return reply, vs, active_profile, [], {}

        if is_selfstate_query(user_input):
            active_goal_txt = ""
            try:
                gs = _av.load_goal_system()
                ag = gs.get("active_goal")
                if isinstance(ag, dict):
                    active_goal_txt = str(ag.get("name") or ag.get("title") or "").strip()[:200]
                elif ag:
                    active_goal_txt = str(ag)[:200]
            except Exception:
                pass
            narrative = _av._load_self_narrative_snippet()
            reply = scrub_visible_reply(
                build_selfstate_reply(_g, user_input, image, active_profile,
                                      active_goal=active_goal_txt or None, narrative_snippet=narrative)
            )
            return finalize_ava_turn(user_input, reply, {}, active_profile, [], turn_route="selfstate")

        if _av.is_camera_identity_intent(user_input) or _av.is_camera_visual_query(user_input):
            ai_reply, visual, active_profile, actions = _av.handle_camera_identity_turn(
                user_input, image, active_person_id=active_person_id
            )
            ai_reply = _av._apply_reply_guardrails(ai_reply, user_input)
            ai_reply = _av._apply_repetition_control(ai_reply, user_input, active_profile["person_id"], source="chat")
            return finalize_ava_turn(user_input, ai_reply, visual, active_profile, actions, turn_route="camera_identity")

        # ── Step: depth classification ────────────────────────────────────────
        print(f"[run_ava] step: classify reply depth (t={time.time()-_t_start:.2f}s)")
        _depth = _av.classify_reply_depth(user_input, _g)
        use_fast_path = _depth == "fast"
        _g["reply_path_selected"] = "fast" if use_fast_path else "deep"
        _g["reply_path_reason"] = f"classify_reply_depth_{_depth}"

        # ── Step: prompt building (with 30s timeout) ──────────────────────────
        print(f"[perf] pre-build-prompt {_elapsed()} path={'fast' if use_fast_path else 'deep'}")
        _prompt_t0 = time.time()  # TRACE-PHASE1
        if use_fast_path:
            _prompt_callable = lambda: build_prompt_fast(user_input, image=image, active_person_id=active_person_id)
        else:
            _prompt_callable = lambda: build_prompt(user_input, image=image, active_person_id=active_person_id)
        _prompt_result = _with_timeout(
            _prompt_callable,
            timeout=30.0,  # prompt building can take time for deep path
            fallback=None,
            label="build_prompt",
        )
        _trace(f"re.prompt_built ms={int((time.time()-_prompt_t0)*1000)}")  # TRACE-PHASE1
        if _prompt_result is None:
            # Prompt build timed out — fall back to minimal prompt
            print("[run_ava] step: prompt build timed out, using minimal fallback")
            from langchain_core.messages import HumanMessage, SystemMessage
            messages = [
                SystemMessage(content=str(_av.SYSTEM_PROMPT or "")),
                HumanMessage(content=user_input),
            ]
            visual = {}
            active_profile = _av.load_profile_by_id(active_person_id)
        else:
            messages, visual, active_profile = _prompt_result

        # ── Step: model selection ─────────────────────────────────────────────
        print(f"[perf] post-build-prompt {_elapsed()}")
        print("[run_ava] step: model selection")
        try:
            _invoke_llm = llm
            try:
                _ws_st = workspace.state
                _perc_r = getattr(_ws_st, "perception", None) if _ws_st is not None else None
                _route_model = ""
                if _perc_r is not None:
                    _route_model = str(getattr(_perc_r, "routing_selected_model", "") or "").strip()
                if use_fast_path:
                    if _route_model and _route_model != LLM_MODEL:
                        _invoke_llm = ChatOllama(model=_route_model, temperature=0.45)
                        print(f"[run_ava] fast_path_routed_model={_route_model}")
                    else:
                        _fast_model = _av._pick_fast_model_fallback()
                        if _fast_model:
                            _invoke_llm = ChatOllama(model=_fast_model, temperature=0.45)
                            print(f"[run_ava] fast_path_model={_fast_model}")
                else:
                    _deep_model = _av._pick_deep_model_fallback()
                    if _deep_model:
                        _invoke_llm = ChatOllama(model=_deep_model, temperature=0.55)
                        print(f"[run_ava] deep_path_model={_deep_model}")
                    elif _route_model and _route_model != LLM_MODEL:
                        _invoke_llm = ChatOllama(model=_route_model, temperature=0.6)
                        print(f"[run_ava] phase25_routing_model={_route_model}")
            except Exception:
                pass

            # ── Step: LLM call (serialized via Ollama lock) ───────────────────
            _used_model_label = getattr(_invoke_llm, 'model', '?')
            print(f"[perf] pre-invoke {_elapsed()} model={_used_model_label}")
            from brain.ollama_lock import with_ollama
            _trace(f"re.ollama_invoke_start deep model={_used_model_label}")  # TRACE-PHASE1
            _deep_invoke_t0 = time.time()  # TRACE-PHASE1
            result = with_ollama(
                lambda: _invoke_llm.invoke(messages),
                label=f"main:{_used_model_label}",
            )
            _trace(f"re.ollama_invoke_done deep ms={int((time.time()-_deep_invoke_t0)*1000)}")  # TRACE-PHASE1
            _g["_last_invoked_model"] = str(_used_model_label)
            print(f"[perf] post-invoke {_elapsed()} model={_used_model_label}")
            raw_reply = getattr(result, "content", str(result)).strip()
            if not raw_reply:
                raw_reply = "I'm here."
            print(f"[run_ava] step: llm response received reply_chars={len(raw_reply)} (t={_elapsed()})")

            # Phase 44: self-evaluation
            try:
                from brain.model_evaluator import get_evaluator
                _used_model = str(getattr(_invoke_llm, "model", "") or "")
                if "ava-personal" in _used_model:
                    get_evaluator(Path(BASE_DIR)).submit_for_evaluation(user_input, raw_reply, _used_model)
            except Exception:
                pass
        except Exception as e:
            raw_reply = f"I hit an internal error: {e}"
            print(f"[run_ava] llm_invoke failed: {e!r}")

        # ── Step: action blocks + guardrails ──────────────────────────────────
        print("[run_ava] step: process action blocks")
        person_id = active_profile["person_id"]
        ai_reply, actions = _av.process_ava_action_blocks(raw_reply, person_id, latest_user_input=user_input)

        try:
            conflict_trigger = any(
                k in _u_low
                for k in ("be honest", "honest feedback", "hard truth", "hurt my feelings", "private", "privacy", "long term", "long-term")
            )
            if conflict_trigger:
                from brain.deep_self import resolve_value_conflict
                _conf = resolve_value_conflict(user_input, _g)
                if isinstance(_conf, dict):
                    _line = str(_conf.get("integrated_response") or "").strip()
                    if _line:
                        ai_reply = f"{ai_reply}\n\n(Values check: {_line})"
        except Exception:
            pass

        from brain.identity_loader import process_identity_actions
        ai_reply = process_identity_actions(ai_reply)
        ai_reply = _av._apply_reply_guardrails(ai_reply, user_input)
        ai_reply = _av._apply_repetition_control(ai_reply, user_input, person_id, source="chat")
        ai_reply = _av._scrub_internal_leakage(ai_reply)
        ai_reply = scrub_visible_reply(ai_reply)
        ai_reply, tool_actions = _av._execute_tool_tags_from_reply(ai_reply)
        if tool_actions:
            actions = list(actions or []) + tool_actions

        # ── Step: curiosity + opinions ────────────────────────────────────────
        print("[run_ava] step: curiosity update")
        try:
            from brain.curiosity_topics import add_topic as add_curiosity_topic, mark_resolved as mark_curiosity_resolved, add_topic_from_conversation
            from brain.opinions import get_opinion, form_opinion
            _t = _av._extract_simple_topic(user_input)
            if _t:
                add_curiosity_topic(_t, user_input[:220], _g)
                _op = get_opinion(_t, _g)
                if _op is None:
                    form_opinion(_t, user_input[:300], _g)
                if "answered" in user_input.lower() or "resolved" in user_input.lower():
                    mark_curiosity_resolved(_t, _g)
            add_topic_from_conversation(user_input, _g)
        except Exception:
            pass

        # Phase 84: prepend morning briefing if ready (result from background thread)
        _mb_pending = str(_g.pop("_pending_morning_briefing", "") or "").strip()
        if _mb_pending:
            ai_reply = f"{_mb_pending}\n\n{ai_reply}"

        # ── Step: emotional style + quality ──────────────────────────────────
        print("[run_ava] step: expression style + quality check")
        try:
            from brain.expression_style import apply_emotional_style
            ai_reply = apply_emotional_style(ai_reply, _g)
        except Exception:
            pass

        try:
            from brain.response_quality import response_quality_check
            ai_reply, _quality_issues = response_quality_check(ai_reply, _inp, {}, _g)
            if _quality_issues:
                print(f"[run_ava] quality issues: {_quality_issues}")
        except Exception:
            pass

        # ── Step: dual-brain handoff ──────────────────────────────────────────
        print("[run_ava] step: handoff_insight_to_foreground")
        try:
            if _db is not None:
                ai_reply = _db.handoff_insight_to_foreground(ai_reply, _inp)
                _db.mark_foreground_end()
                _g["_last_ai_reply"] = ai_reply[:500]
                _db.submit("self_critique", payload={"last_reply": ai_reply[:400], "user_input": _inp[:200]})
        except Exception:
            pass

        _vroute = isinstance(visual, dict) and visual.get("turn_route")
        print(f"[run_ava] step: finalize_ava_turn route={_vroute or 'llm'} path={'fast' if use_fast_path else 'deep'} (t={time.time()-_t_start:.2f}s)")
        _trace(f"re.run_ava.return path={'fast' if use_fast_path else 'deep'} ms={int((time.time()-_t_start)*1000)}")  # TRACE-PHASE1
        return finalize_ava_turn(
            user_input, ai_reply, visual, active_profile, actions, turn_route=_vroute or "llm"
        )

    except Exception as e:
        import traceback
        print(f"[run_ava] exception (fallback turn): {e!r}\n{traceback.format_exc()}")
        try:
            if _db is not None:
                _db.mark_foreground_end()
        except Exception:
            pass
        try:
            ap = _av.load_profile_by_id(active_person_id)
        except Exception:
            try:
                _av.ensure_owner_profile()
                ap = _av.load_profile_by_id(OWNER_PERSON_ID)
            except Exception:
                ap = {
                    "person_id": active_person_id, "name": active_person_id,
                    "relationship_to_zeke": "unknown", "allowed_to_use_computer": False,
                    "relationship_score": 0.3, "notes": [], "likes": [], "ava_impressions": [],
                }
        vs = default_visual_payload(
            face_status="Pipeline error — vision not applied", recognition_status="—",
            expression_status="—", memory_preview="", turn_route="error",
            visual_truth_trusted=False, vision_status="error",
        )
        vs["error_detail"] = str(e)[:500]
        vs["error_type"] = type(e).__name__
        fallback = "Something went wrong on my side; I'm still here. Could you try that again?"
        print(f"[run_ava] exit route=error reply=fallback (no finalize)")
        return fallback, vs, ap, ["run_ava_error"], {"error": str(e), "error_type": type(e).__name__}
    finally:
        # Always clear thinking flag — UI relies on this to stop the thinking pulse
        _g["_ava_thinking"] = False
