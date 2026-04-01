# Ava — Phase 3: REFLECTIVE
## Level 3 of 5 — Autobiographical Awareness
### Complete Phases 1 and 2 first. Feed this to Cursor after Phase 2 is tested and working.

---

## Context — What Exists After Phase 2

- `brain/perception.py` — `PerceptionState` with face, emotion, identity, salience ✅
- `brain/emotion.py` — mood shifts from camera visuals ✅
- `brain/attention.py` — `AttentionState`, initiative suppression ✅
- `brain/identity.py` — `IdentityRegistry` now tracks `emotion_history` per person ✅
- `brain/initiative.py` — attention gate added ✅

The current `brain/memory.py` is only 17 lines — a thin delegate. It needs to become real.
The current `brain/selfstate.py` reports system status but nothing personal. It needs extending.

---

## Goal of This Phase

When Ava sees a familiar face, she surfaces memories of that person automatically.
Those memories flow into the next prompt so she is already thinking about them before they say a word.
When asked how she is, she can describe her current goal and what she has been thinking about.

---

## What to Build

### 1. Upgrade `brain/memory.py` — The Hippocampus

Replace the current 17-line file with this:

```python
from __future__ import annotations
from .shared import extract_text, now_iso
from .perception import PerceptionState


def remember_with_context(host: dict, text: str, person_id: str, perception: PerceptionState) -> str | None:
    """
    Store a memory with visual and emotional context attached.
    Wraps the existing remember_memory() function in avaagent.py.
    """
    remember_fn = host.get('remember_memory')
    if not callable(remember_fn):
        return None

    # Derive emotional valence from face emotion
    positive = {'happy', 'surprise'}
    negative = {'angry', 'disgust', 'fear', 'sad'}
    emotion = perception.face_emotion or 'neutral'
    if emotion in positive:
        valence = 'positive'
    elif emotion in negative:
        valence = 'negative'
    else:
        valence = 'neutral'

    visual_context = f"face={'yes' if perception.face_detected else 'no'}, emotion={emotion}"

    extra_tags = ['visual_context'] if perception.face_detected else []

    try:
        return remember_fn(
            text,
            person_id=person_id,
            category='episodic',
            importance=0.6,
            source='ava_perception',
            tags=['perception', valence] + extra_tags,
            extra={'visual_context': visual_context, 'emotional_valence': valence}
        )
    except Exception:
        # Fallback: call with minimal args if the signature differs
        try:
            return remember_fn(text, person_id=person_id, category='episodic', importance=0.6)
        except Exception:
            return None


def recall_for_person(host: dict, person_id: str | None, limit: int = 5) -> list[str]:
    """
    Surface memories for a recognized person.
    Called automatically when a face is identified.
    Returns a list of plain strings ready for prompt injection.
    """
    if not person_id:
        return []

    search_fn = host.get('_BRAIN_ORIG_SEARCH_REFLECTIONS') or host.get('search_reflections')
    if not callable(search_fn):
        return []

    try:
        results = search_fn(person_id, limit=limit)
        if not results:
            return []
        out = []
        for r in results[:limit]:
            if isinstance(r, dict):
                txt = r.get('text') or r.get('content') or str(r)
            else:
                txt = str(r)
            if txt.strip():
                out.append(txt.strip()[:300])
        return out
    except Exception:
        return []


def decay_tick(host: dict):
    """
    On startup: lightly reduce importance of memories not accessed in 30+ days.
    Never deletes — only reduces salience.
    """
    import time
    thirty_days = 30 * 24 * 3600
    now = time.time()

    list_fn = host.get('list_memories') or host.get('get_all_memories')
    update_fn = host.get('set_memory_importance')
    if not callable(list_fn) or not callable(update_fn):
        return

    try:
        memories = list_fn()
        for m in (memories or []):
            if not isinstance(m, dict):
                continue
            last_accessed = m.get('last_accessed_ts') or m.get('created_ts', now)
            if (now - last_accessed) > thirty_days:
                current_importance = float(m.get('importance', 0.5))
                new_importance = max(0.1, current_importance - 0.05)
                mem_id = m.get('memory_id') or m.get('id')
                if mem_id:
                    try:
                        update_fn(mem_id, new_importance, reason='decay_tick')
                    except Exception:
                        pass
    except Exception:
        pass


def describe_memory_integrity(host: dict) -> str:
    """Status string for the UI — unchanged behavior."""
    fn = host.get('get_memory_status')
    if callable(fn):
        try:
            return str(fn())
        except Exception as e:
            return f'error: {e}'
    return 'memory status unavailable'
```

### 2. Wire face recognition → memory recall in `avaagent.py`

In `camera_tick_fn`, after `build_perception()` resolves a `face_identity`:

```python
from brain.memory import recall_for_person

# When a face is newly recognized, surface their memories
prev_person = globals().get('_last_recognized_person_id')
if perception.face_identity and perception.face_identity != prev_person:
    globals()['_last_recognized_person_id'] = perception.face_identity
    globals()['_active_person_memories'] = recall_for_person(globals(), perception.face_identity, limit=5)
    if globals()['_active_person_memories']:
        print(f"[memory] recalled {len(globals()['_active_person_memories'])} memories for {perception.face_identity}")
```

### 3. Inject recalled memories into `build_prompt()`

In `build_prompt()` in `avaagent.py`, find where the system prompt is assembled. Add the recalled memories as a section:

```python
active_memories = globals().get('_active_person_memories', [])
if active_memories:
    memory_block = "\n\n[Recalled memories for this person]\n" + "\n".join(f"- {m}" for m in active_memories)
    # Append to system message content
```

Place this near the existing `dynamic_memory_summary` injection — add it as a separate labeled block so Ava knows these are face-triggered recalls vs. semantic search results.

### 4. Call `decay_tick` on startup in `avaagent.py`

Near the bottom of the startup section (where `print_startup_selftest` is called), add:

```python
from brain.memory import decay_tick
try:
    decay_tick(globals())
    print("[memory] decay tick complete")
except Exception as e:
    print(f"[memory] decay tick failed: {e}")
```

### 5. Extend `brain/selfstate.py` — richer self-description

In `build_selfstate_reply()`, after the existing status output, add two optional lines if data is available:

```python
def build_selfstate_reply(health, mood, tendency=None, active_goal=None, narrative_snippet=None):
    # ... existing logic ...
    
    # Add goal awareness
    if active_goal:
        reply += f"\nRight now my focus is: {active_goal}."
    
    # Add narrative snippet
    if narrative_snippet:
        reply += f"\nI've been thinking: {narrative_snippet}"
    
    return reply
```

In `avaagent.py`, wherever `build_selfstate_reply` is called, pass:
- `active_goal=` from the loaded goal system's `active_goal` field
- `narrative_snippet=` from `state/self_narrative.json` if it exists (Phase 4 creates this — skip for now if not ready)

---

## Definition of Done

- `brain/memory.py` has `remember_with_context()`, `recall_for_person()`, `decay_tick()`
- When a recognized face appears for the first time in a session, console prints: `[memory] recalled N memories for person_id`
- Those memories appear in the system prompt as a labeled `[Recalled memories]` block
- `decay_tick` runs on startup without crashing
- `build_selfstate_reply()` mentions Ava's current active goal when asked how she is

---

## Do NOT Change

- The existing `remember_memory()` function in `avaagent.py` — only wrap it
- The existing ChromaDB / reflection search system — only call it via host
- `brain/camera.py`, `brain/trust_manager.py`, `brain/profile_manager.py`
- Memory UI (search, delete, add, update) — leave all of it intact

---

## What Comes Next

Phase 4 gives Ava a persistent self-narrative that evolves after each conversation.
