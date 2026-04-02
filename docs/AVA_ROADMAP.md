# Ava Agent v2 — Development Roadmap
**Date:** April 2026  
**Repo:** `Tzeke000/Ava-Agent-v2` (private)  
**Based on:** Full audit of all 28 brain modules + `avaagent.py`

---

## Current State Summary

The v2 rewrite is **mostly clean and working**. The major outstanding gaps are:

1. **Rogue profile creation** — happening actively right now (BUG-01)
2. **Stage 7 not wired** — trust gate, persona tones, identity file injection all built but not connected
3. **`brain/health.py` not applied** — health signals don't affect Ava's behavior
4. **`brain/identity_loader.py` has wrong path** — `D:/AvaAgent/ava_core` instead of relative path

Everything else is largely functional. Fix the bugs first, then wire Stage 7, then explore new features.

---

## SESSION 1 — Immediate Fixes (Start Here)

### FIX-01 🔴 — Stop Rogue Profile Creation

**File:** `avaagent.py` — `infer_person_from_text()` function

**Problem:** Phrases like "do you", "that's correct ava", "who created you" are being treated as person names and creating profiles. `brain/profile_manager.py` has the filter functions (`looks_like_phrase_profile`, `is_valid_profile_name`) but they aren't called.

**Fix — update `infer_person_from_text()` in `avaagent.py`:**

At the top of the function, add the import (or at file top):
```python
from brain.profile_manager import looks_like_phrase_profile, normalize_person_key
```

Then inside `infer_person_from_text()`, before returning any inferred person_id:
```python
if pid and pid != current_person_id:
    # Block phrase-like names from becoming profiles
    if looks_like_phrase_profile(pid.replace('_', ' ')):
        return current_person_id, 'rejected_phrase_profile'
    # Block empty or too-short slugs
    if not pid or len(pid.replace('_', '')) < 2:
        return current_person_id, 'rejected_empty_id'
return pid, source
```

Also apply the same guard in `create_or_get_profile()`:
```python
def create_or_get_profile(name, relationship_to_zeke="known person", allowed=True):
    from brain.profile_manager import is_valid_profile_name
    cleaned = (name or '').strip()
    if not is_valid_profile_name(cleaned):
        return load_profile_by_id(OWNER_PERSON_ID)
    # ... rest of function ...
```

**Also clean up the 4 existing rogue profiles.** Add this to a cleanup script or run once:
```python
import os
ROGUE_PROFILES = ["do_you", "thats_correct_ava", "who_created_you", "ezekiel"]
for slug in ROGUE_PROFILES:
    path = PROFILES_DIR / f"{slug}.json"
    if path.exists():
        os.remove(path)
        print(f"Deleted rogue profile: {slug}")
```

Note: `who_created_you` has a face sample in `faces/who_created_you/`. Delete that folder too.

---

### FIX-02 🔴 — Fix `IDENTITY_DIR` Hardcoded Path in `brain/identity_loader.py`

**File:** `brain/identity_loader.py`, **line 21**

**Problem:**
```python
IDENTITY_DIR = Path("D:/AvaAgent/ava_core")  # WRONG — v1 directory
```

**Fix:**
```python
IDENTITY_DIR = Path(__file__).resolve().parent.parent / "ava_core"
```

This makes it relative to the brain/ folder's parent (the repo root), which is always correct regardless of where the repo is cloned.

---

### FIX-03 🔴 — Fix `requirements.txt`

**Problem:** `deepface` and `tf-keras` are listed as direct installs. They fail on Python 3.14.

**Fix — replace `requirements.txt`:**
```
gradio
opencv-python
opencv-contrib-python
Pillow
numpy
faster-whisper
langchain-ollama
langchain-chroma
chromadb
```

**Note:** DeepFace must be installed separately into Python 3.12:
```
py -3.12 -m pip install deepface tf-keras
```

---

### FIX-04 🔴 — Wire Config Aliases for Zeke = Ezekiel

**Problem:** `profiles/ezekiel.json` exists as a separate person. `config/settings.json` has `"aliases": {"zeke": ["ezekiel", ...]}` but nothing loads this.

**Fix — in `avaagent.py`, add alias resolution to `infer_person_from_text()`:**
```python
def infer_person_from_text(user_input, current_person_id):
    # Load config aliases
    try:
        _cfg = json.loads((BASE_DIR / "config" / "settings.json").read_text(encoding="utf-8"))
        _aliases = _cfg.get("aliases", {})
    except Exception:
        _aliases = {}

    # Check if inferred ID is actually an alias for someone else
    for primary_id, alias_list in _aliases.items():
        if pid and normalize_person_key(pid) in [normalize_person_key(a) for a in alias_list]:
            return primary_id, 'config_alias'
    
    # ... rest of function ...
```

Also: `brain/profile_manager.py`'s `DEFAULT_ALIASES` dict already has `zeke → [ezekiel, creator, your_creator]`. You can also just use that.

---

### FIX-05 🟡 — Clean Up `.tmp` Files in Memory

These are harmless but messy. Delete:
- `memory/self reflection/self_model.json.7wfk1g__.tmp`
- `memory/self reflection/self_model.json.mjr0vlog.tmp`

Add to `fix_and_clean.bat`:
```batch
del /f /q "memory\self reflection\*.tmp" 2>nul
```

---

## SESSION 2 — Wire Stage 7 (Trust + Persona + Identity)

All the Stage 7 code is written. This session is purely about connecting it.

### STAGE7-01 — Wire Trust + Persona Into `build_prompt()`

**File:** `avaagent.py`

Add to the imports at top:
```python
from brain.trust_manager import get_trust_level, get_trust_label, is_blocked, can
from brain.persona_switcher import build_persona_block, should_deflect, get_blocked_reply, get_deflect_reply
from brain.profile_store import seed_default_profiles, get_or_create_profile as _store_get_or_create, touch_last_seen
from brain.identity_loader import ensure_identity_files, load_ava_identity, process_identity_actions, append_to_user_file
```

Add to startup (after `ensure_owner_profile()`):
```python
ensure_identity_files()
seed_default_profiles()
_AVA_IDENTITY_BLOCK = load_ava_identity()
```

Add to `build_prompt()`, after building `messages`:
```python
# Stage 7: inject identity + persona
try:
    persona_block = build_persona_block(active_profile)
    trust_note = f"[Trust level: {get_trust_label(active_profile).upper()} ({get_trust_level(active_profile)})]"
    injected = f"{_AVA_IDENTITY_BLOCK}\n\n{persona_block}\n\n{trust_note}"
    if messages and hasattr(messages[0], 'role') and messages[0].role == 'system':
        messages[0].content = injected + "\n\n" + messages[0].content
    else:
        messages.insert(0, SystemMessage(content=injected))
except Exception as _e:
    print(f"[stage7] persona inject failed: {_e}")
```

---

### STAGE7-02 — Wire Trust Gate Into `run_ava()`

**File:** `avaagent.py`, inside `run_ava()`, before the selfstate check:
```python
def run_ava(user_input, image=None, active_person_id=None):
    active_person_id = active_person_id or get_active_person_id()
    active_profile = load_profile_by_id(active_person_id)
    
    # Trust gate
    if is_blocked(active_profile):
        return get_blocked_reply(), {}, active_profile, [], {}
    if should_deflect(active_profile, user_input):
        return get_deflect_reply(active_profile, user_input), {}, active_profile, [], {}
    
    # Existing flow continues...
    if is_selfstate_query(user_input):
        ...
```

---

### STAGE7-03 — Wire Identity Actions Into `run_ava()`

After `process_ava_action_blocks()` returns the cleaned reply, also scan for `IDENTITY action:` blocks:
```python
ai_reply, actions = process_ava_action_blocks(raw_reply, person_id, latest_user_input=user_input)
ai_reply = process_identity_actions(ai_reply)  # strips + executes IDENTITY action blocks
```

---

### STAGE7-04 — Wire `append_to_user_file` Into `reflect_on_last_reply()`

After `reflect_on_last_reply()` runs, if the active person is the owner and a meaningful summary was generated:
```python
reflection = reflect_on_last_reply(user_input, ai_reply, person_id, actions=actions)
# Stage 7: auto-save learned facts about owner to USER.md
if person_id == OWNER_PERSON_ID:
    summary = (reflection or {}).get("summary") or ""
    importance = float((reflection or {}).get("importance", 0.0))
    if summary and importance >= 0.72:
        try:
            append_to_user_file(summary)
        except Exception:
            pass
```

---

### STAGE7-05 — Wire `touch_last_seen` Into Camera Tick

In `camera_tick_fn()`, after `identity_registry.update_emotional_association()`:
```python
if recognized_person_id is not None:
    try:
        touch_last_seen(recognized_person_id)
    except Exception:
        pass
```

---

## SESSION 3 — Wire `brain/health.py` to Behavior

### HEALTH-01 — Run Health Check at Startup and Apply Modifiers

Add to startup sequence:
```python
from brain.health import run_system_health_check, load_health_state

_health_state = run_system_health_check(globals(), kind='startup')
print(f"Health: {_health_state.get('startup_summary', 'UNKNOWN')}")
```

Apply health modifiers to initiative:
```python
# In choose_initiative_candidate() or camera_tick_fn():
health = load_health_state(globals())
mods = health.get("behavior_modifiers", {})
initiative_scale = float(mods.get("initiative_scale", 1.0))
# Scale the initiative score down when degraded
candidate["base_score"] *= initiative_scale
```

### HEALTH-02 — Run Light Health Check in Camera Tick

Every ~60 seconds in `camera_tick_fn()`:
```python
if int(time.time()) % 60 < 5:  # approximately every minute
    try:
        from brain.health import run_system_health_check
        run_system_health_check(globals(), kind='light')
    except Exception:
        pass
```

---

## SESSION 4 — Wire `brain/attention.py` to Initiative

### ATTN-01 — Use AttentionState Before Autonomous Initiation

`brain/attention.py` already exists with `compute_attention(perception, seconds_since_last_message, circadian_initiative_scale)`. It's not currently called from anywhere.

Add to `maybe_autonomous_initiation()`:
```python
def maybe_autonomous_initiation(history, image, recognized_person_id=None, expression_state=None, perception=None):
    # Gate 1: compute attention
    if perception:
        seconds_idle = time.time() - _LAST_USER_REPLY_END_TS if _LAST_USER_REPLY_END_TS > 0 else 9999
        circ = get_circadian_modifiers().get("initiative_scale", 1.0)
        attention = compute_attention(perception, seconds_idle, circ)
        if not attention.should_speak:
            return history, f"Attention gate: {attention.suppression_reason}"
    
    # existing candidate selection flow...
```

---

## SESSION 5 — New Features

### FEATURE-01 — `update_self_narrative()` at Session End

`brain/beliefs.py` has `update_self_narrative(host, conversation_summary, mood, face_emotion)` which uses LLM to update Ava's self-narrative. It's never called.

Call it when the session ends (session message count hits a milestone, or on graceful exit):
```python
atexit.register(lambda: _maybe_update_narrative())

def _maybe_update_narrative():
    try:
        sess = load_session_state()
        count = int(sess.get("total_message_count", 0))
        if count >= 5:  # only if we had a meaningful session
            recent = load_recent_chat(limit=20)
            summary = " ".join(row.get("content","")[:80] for row in recent[-10:])
            mood = load_mood()
            face_emotion = load_expression_state().get("raw_emotion", "neutral")
            from brain.beliefs import update_self_narrative
            update_self_narrative(globals(), summary, mood, face_emotion)
    except Exception as e:
        print(f"[narrative-update] failed: {e}")
```

---

### FEATURE-02 — `return_greeting` Initiative

The kind `"return_greeting"` is defined in `INITIATIVE_KIND_COOLDOWNS` and `CAMERA_AUTONOMOUS_ALLOWED_KINDS` but never generated as a candidate.

Add to `collect_initiative_candidates()`:
```python
# Return greeting when person comes back to camera
camera_state = load_camera_state()
current = camera_state.get("current", {}) or {}
if current.get("transition_summary") and "came back" in str(current.get("transition_summary", "")).lower():
    name = load_profile_by_id(person_id).get("name", "you")
    txt = f"Hey, you're back. How's it going?"
    candidates.append({
        "kind": "return_greeting",
        "text": txt,
        "topic_key": _topic_key(txt),
        "base_score": 0.82,
        "memory_importance": 0.65,
    })
```

---

### FEATURE-03 — `self_calibration_check` Initiative

Same situation — the kind and prompts are defined but never generated.

Add to `collect_initiative_candidates()`:
```python
# Periodic self-calibration check (every ~2 hours max via cooldown)
import random
if random.random() < 0.15:  # only sometimes bubbles to the top
    prompt = random.choice(SELF_CALIBRATION_PROMPTS)
    candidates.append({
        "kind": "self_calibration_check",
        "text": prompt,
        "topic_key": _topic_key(prompt),
        "base_score": 0.70,
        "memory_importance": 0.68,
    })
```

---

### FEATURE-04 — `process_visual_emotion()` Wired to Mood

`brain/emotion.py`'s `process_visual_emotion(perception, mood)` runs on every workspace tick but the returned mood is never written back. Wire it:

In `camera_tick_fn()`, after `workspace.tick()`:
```python
ws = workspace.tick(camera_manager, image, globals(), "")
perception = ws.perception

# Apply visual emotion to mood
try:
    from brain.emotion import process_visual_emotion
    current_mood = load_mood()
    updated_mood = process_visual_emotion(perception, current_mood)
    if updated_mood != current_mood:
        save_mood(enrich_mood_state(updated_mood))
except Exception:
    pass
```

---

### FEATURE-05 — Relationship Score Decay + Growth

`active_profile.get("relationship_score", 0.3)` is used in `build_prompt()` to add a rapport hint, but `relationship_score` is never updated.

Add to `finalize_ava_turn()` or `reflect_on_last_reply()`:
```python
# Grow relationship score on meaningful interactions
profile = load_profile_by_id(person_id)
current_rs = float(profile.get("relationship_score", 0.3))
importance = float(reflection.get("importance", 0.0)) if isinstance(reflection, dict) else 0.0
if importance >= 0.65:
    new_rs = min(1.0, current_rs + 0.008)
else:
    new_rs = max(0.0, current_rs - 0.002)  # very slow decay
if abs(new_rs - current_rs) > 0.001:
    profile["relationship_score"] = round(new_rs, 4)
    save_profile(profile)
```

---

## WHAT TO NEVER TOUCH

These are working well and should not be refactored:
- `brain/selfstate.py` — clean, correct, good signature
- `brain/output_guard.py` — `scrub_visible_reply` is tight
- `brain/memory_reader.py` — robust multi-signature fallback
- `brain/initiative_sanity.py` — `desaturate_candidate_scores` prevents score inflation
- `brain/profile_manager.py` — `looks_like_phrase_profile` logic is solid
- `brain/camera_truth.py` — camera identity logic
- `brain/shared.py` — utility functions, atomic save
- `ava_personality.txt` — core personality is good
- The 27-emotion system and style blend
- The ChromaDB memory + reflection pipeline
- The `workspace.tick()` architecture — don't break this, it's the cleanest part of the whole system

---

## Priority Summary

| Session | Fix/Feature | Risk | Impact |
|---|---|---|---|
| 1, FIX-01 | Stop rogue profile creation | 🟢 Low | 🔴 High — happening now |
| 1, FIX-02 | Fix IDENTITY_DIR in identity_loader.py | 🟢 Low | Medium — needed before Stage 7 |
| 1, FIX-03 | Fix requirements.txt | 🟢 Zero risk | Low — prevents pip error |
| 1, FIX-04 | Wire aliases for zeke=ezekiel | 🟢 Low | 🔴 High — Ava confuses owner |
| 1, FIX-05 | Clean .tmp files | 🟢 Zero risk | Low |
| 2, STAGE7 | Wire trust + persona + identity files | 🟡 Medium | 🔴 Very High — biggest missing feature |
| 3, HEALTH | Wire health.py to behavior | 🟡 Medium | Medium |
| 4, ATTN | Wire attention.py to initiative | 🟡 Medium | Medium |
| 5, FEATURE-01 | self_narrative update at session end | 🟢 Low | Medium — Ava evolves |
| 5, FEATURE-02 | return_greeting | 🟢 Low | Medium |
| 5, FEATURE-03 | self_calibration_check | 🟢 Low | Medium |
| 5, FEATURE-04 | process_visual_emotion → save_mood | 🟡 Medium | High — Ava's mood reacts to camera |
| 5, FEATURE-05 | Relationship score decay/growth | 🟢 Low | Medium |
