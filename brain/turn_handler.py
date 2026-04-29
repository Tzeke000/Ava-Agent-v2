"""
brain/turn_handler.py — Post-reply turn finalization.

finalize_ava_turn extracted from avaagent.py.
Handles logging, memory, episodic memory, TTS, self-critique, concept graph,
relationship update, and all other post-reply hooks.
"""
from __future__ import annotations

import re
import time
from typing import Any


def finalize_ava_turn(
    user_input: str,
    ai_reply: str,
    visual: dict,
    active_profile: dict,
    actions: list[str],
    *,
    turn_route: str | None = None,
) -> tuple[str, dict, dict, list[str], dict]:
    import avaagent as _av
    _g = vars(_av)
    from brain.turn_visual import normalize_visual_payload

    person_id = active_profile["person_id"]

    try:
        from brain.person_cadence import update_cadence_on_visit
        prof = dict(_av.load_profile_by_id(person_id))
        prof = update_cadence_on_visit(prof)
        _av.save_profile(prof)
        active_profile["cadence"] = prof.get("cadence")
        active_profile["last_activity_at"] = prof.get("last_activity_at")
        active_profile["threads"] = prof.get("threads", [])
    except Exception as e:
        print(f"[cadence] update failed: {e}")

    try:
        from brain.profile_store import touch_last_seen
        touch_last_seen(person_id, topic=user_input)
    except Exception:
        pass

    _av.log_chat("user", user_input, {"person_id": person_id, "person_name": active_profile["name"]})
    _av.log_chat("assistant", ai_reply, {"person_id": person_id, "person_name": active_profile["name"], "actions": actions})
    _av.maybe_autoremember(user_input, ai_reply, person_id)

    try:
        from brain.event_extractor import maybe_extract_prospective_events
        st = _av.load_session_state()
        turn = int(st.get("total_message_count", 0) or 0) + 1
        maybe_extract_prospective_events(user_input, person_id, _g, source_turn=turn)
    except Exception as e:
        print(f"[prospective] extract failed: {e}")

    reflection = _av.reflect_on_last_reply(user_input, ai_reply, person_id, actions=actions)
    OWNER_PERSON_ID = _av.OWNER_PERSON_ID
    if person_id == OWNER_PERSON_ID:
        summary = (reflection or {}).get("summary") or ""
        importance = float((reflection or {}).get("importance", 0.0))
        if summary and importance >= 0.72:
            try:
                from brain.identity_loader import append_to_user_file
                append_to_user_file(summary)
            except Exception:
                pass

    canon = list(_av._get_canonical_history())
    canon.append({"role": "assistant", "content": ai_reply})
    _av._set_canonical_history(canon)
    _av._maybe_update_relationship_on_turn(active_profile)

    try:
        _av.refresh_self_model_pending_threads(person_id)
    except Exception:
        pass

    try:
        sess = _av.load_session_state()
        n = int(sess.get("total_message_count", 0) or 0) + 1
        if n > 0 and n % 10 == 0:
            _av._trigger_narrative_update_async()
    except Exception:
        pass

    try:
        _av._update_concept_graph_from_turn(user_input, ai_reply)
    except Exception:
        pass

    # Phase 64: episodic memory
    try:
        BASE_DIR = _av.BASE_DIR
        _ep_importance = float((reflection or {}).get("importance", 0.4))
        _ep_topic = _av._extract_simple_topic(user_input) or "conversation"
        _ep_summary = f"Zeke: {user_input[:150]} | Ava: {ai_reply[:200]}"
        _ep_emotion = str(_av.load_mood().get("current_mood") or "neutral")
        from brain.episodic_memory import get_episodic_memory
        get_episodic_memory(BASE_DIR).store_episode(
            topic=_ep_topic,
            summary=_ep_summary,
            emotional_context=_ep_emotion,
            importance=_ep_importance,
            people_present=[person_id],
            novelty=0.5,
        )
    except Exception:
        pass

    try:
        from brain.deep_self import update_mind_model_async
        update_mind_model_async(user_input, ai_reply[:1200], _g)
    except Exception:
        pass

    try:
        from brain.deep_self import self_critique_async
        self_critique_async(ai_reply, user_input, str(actions), _g)
    except Exception:
        pass

    try:
        from brain.deep_self import check_repair_needed
        global _last_repair_check_ts
        now = time.time()
        if now - float(_g.get("_last_repair_check_ts") or 0.0) >= 2 * 3600:
            _g["_last_repair_check_ts"] = now
            check_repair_needed(_g)
    except Exception:
        pass

    visual_out = normalize_visual_payload(visual, turn_route=turn_route)
    try:
        _fs = str(visual_out.get("face_status", ""))[:80]
        print(
            f"[run_ava] finalize route={visual_out.get('turn_route')} "
            f"reply_len={len(ai_reply or '')} actions={len(actions)} face_line={_fs!r}"
        )
    except Exception:
        pass

    # TTS speak
    try:
        _tts = _g.get("tts_engine")
        _tts_enabled = bool(_g.get("tts_enabled", False))
        if _tts_enabled and _tts is not None and callable(getattr(_tts, "is_available", None)) and _tts.is_available():
            _reply_text = str(ai_reply or "")
            _clean = re.sub(r"[*_`#\[\]()]", "", _reply_text)
            _clean = re.sub(r"\s+", " ", _clean).strip()
            if len(_clean) > 300:
                _clean = _clean[:300].rstrip()
            if _clean and re.search(r"[A-Za-z0-9]", _clean):
                _tts.speak(_clean, blocking=False)
    except Exception:
        pass

    return ai_reply, visual_out, active_profile, actions, reflection
