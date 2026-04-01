# Ava — Phase 4: SELF-MODELING
## Level 4 of 5 — Narrative Awareness
### Complete Phases 1–3 first. Feed this to Cursor after Phase 3 is tested and working.

---

## Context — What Exists After Phase 3

- `brain/perception.py` — `PerceptionState` ✅
- `brain/emotion.py` — mood shifts from camera ✅
- `brain/attention.py` — initiative gating ✅
- `brain/memory.py` — episodic recall, face-triggered memory surfacing ✅
- `brain/selfstate.py` — extended with active goal output ✅

The current `brain/beliefs.py` is only 32 lines — pure keyword matching on the last user message.
It has no persistent state, no inner monologue, no self-model.
This phase gives Ava a continuous inner narrative that updates over time and never resets.

---

## Goal of This Phase

Ava maintains a rolling self-narrative stored in `state/self_narrative.json`.
After each conversation she updates it using the LLM — but her ethical constraints never change.
This narrative is injected into every system prompt so she is always responding from a self-aware baseline.

---

## What to Build

### 1. Upgrade `brain/beliefs.py` — Add Persistent Self-Narrative

Keep the existing `build_belief_state()` function exactly as is at the top of the file.
Add everything below it as new code:

```python
# ─────────────────────────────────────────
# SELF-NARRATIVE LAYER
# ─────────────────────────────────────────

import json
from pathlib import Path

SELF_NARRATIVE_PATH = Path("state/self_narrative.json")

# These constraints are FIXED. They are never modified by the LLM.
SELF_LIMITS = [
    "I am here to support, not to control.",
    "Uncertainty should lower my confidence, not increase my forcefulness.",
    "Strong emotion should increase care and caution, not boldness.",
    "I should ask, verify, or wait when context is weak.",
    "The user's autonomy comes before my initiative.",
]

DEFAULT_NARRATIVE = {
    "who_i_am": "I am Ava. I am here to be present, supportive, and honest.",
    "how_i_feel": "I feel calm and attentive.",
    "patterns_i_notice": "I am still learning the shape of our interactions.",
    "self_limits": SELF_LIMITS,
    "updated_at": "",
}


def load_self_narrative() -> dict:
    """Load persistent self-narrative from disk. Returns DEFAULT_NARRATIVE if missing."""
    try:
        if SELF_NARRATIVE_PATH.exists():
            data = json.loads(SELF_NARRATIVE_PATH.read_text(encoding='utf-8'))
            # Always enforce fixed self_limits regardless of what's on disk
            data['self_limits'] = SELF_LIMITS
            return data
    except Exception:
        pass
    return dict(DEFAULT_NARRATIVE)


def save_self_narrative(narrative: dict):
    """Save self-narrative to disk. Always preserves self_limits."""
    try:
        SELF_NARRATIVE_PATH.parent.mkdir(parents=True, exist_ok=True)
        narrative['self_limits'] = SELF_LIMITS  # enforce — never allow LLM to override
        from .shared import now_iso
        narrative['updated_at'] = now_iso()
        SELF_NARRATIVE_PATH.write_text(
            json.dumps(narrative, indent=2, ensure_ascii=False), encoding='utf-8'
        )
    except Exception:
        pass


def update_self_narrative(host: dict, conversation_summary: str, mood: dict, face_emotion: str = "neutral"):
    """
    Called at end of each conversation.
    Uses the LLM (via existing host callable) to update who_i_am, how_i_feel, patterns_i_notice.
    NEVER modifies self_limits.
    """
    call_llm = host.get('call_llm') or host.get('call_openai') or host.get('_call_llm')
    if not callable(call_llm):
        return  # skip silently if no LLM callable is available

    current = load_self_narrative()

    prompt = f"""You are Ava's internal narrator. Update Ava's self-narrative based on this conversation.

Current narrative:
- who_i_am: {current['who_i_am']}
- how_i_feel: {current['how_i_feel']}
- patterns_i_notice: {current['patterns_i_notice']}

Conversation summary: {conversation_summary[:600]}
Ava's current mood keys: {list(mood.keys())[:6]}
Face emotion observed: {face_emotion}

Return ONLY valid JSON with exactly these three keys. Each value is 1–2 sentences. Do not add other keys.
{{"who_i_am": "...", "how_i_feel": "...", "patterns_i_notice": "..."}}"""

    try:
        response = call_llm(prompt, max_tokens=200)
        if isinstance(response, str):
            # Extract JSON from response
            import re
            match = re.search(r'\{.*\}', response, re.DOTALL)
            if match:
                updated = json.loads(match.group())
                if all(k in updated for k in ('who_i_am', 'how_i_feel', 'patterns_i_notice')):
                    current.update(updated)
                    save_self_narrative(current)
    except Exception:
        pass  # never crash — narrative update is non-critical


def get_self_narrative_for_prompt() -> str:
    """
    Returns a compact string for injection into the system prompt.
    Always includes self_limits.
    """
    n = load_self_narrative()
    limits_str = " | ".join(n.get('self_limits', SELF_LIMITS))
    return (
        f"[Ava's inner state] "
        f"{n['who_i_am']} "
        f"{n['how_i_feel']} "
        f"{n['patterns_i_notice']} "
        f"[Core limits: {limits_str}]"
    )
```

### 2. Wire `get_self_narrative_for_prompt()` into `build_prompt()` in `avaagent.py`

In `build_prompt()`, find where the system message content is assembled (the large string that defines who Ava is). Near the top of that string, add:

```python
from brain.beliefs import get_self_narrative_for_prompt
self_narrative_block = get_self_narrative_for_prompt()

# Add to system message:
# f"\n\n{self_narrative_block}\n\n"
```

Place it after Ava's name/personality block but before the memory and goal sections.

### 3. Wire `update_self_narrative()` — end of conversation hook

In `avaagent.py`, find a natural end-of-conversation point. The best place is inside `chat_fn`, after the reply is generated, when history reaches a multiple of 10 turns (lightweight trigger):

```python
from brain.beliefs import update_self_narrative
from brain.memory import recall_for_person

# At end of chat_fn, after reply is finalized:
try:
    turn_count = len(history) if history else 0
    if turn_count > 0 and turn_count % 10 == 0:
        # Build a brief conversation summary from the last 5 turns
        recent = history[-5:] if len(history) >= 5 else history
        summary_lines = []
        for turn in recent:
            if isinstance(turn, (list, tuple)) and len(turn) == 2:
                summary_lines.append(f"User: {str(turn[0])[:100]}")
                summary_lines.append(f"Ava: {str(turn[1])[:100]}")
        summary = "\n".join(summary_lines)
        current_mood = load_mood() if callable(globals().get('load_mood')) else {}
        face_emotion = globals().get('_last_perception_emotion', 'neutral')
        update_self_narrative(globals(), summary, current_mood, face_emotion)
except Exception:
    pass  # never let this crash the chat
```

Also add this line in `camera_tick_fn` to track the last emotion for the hook above:
```python
globals()['_last_perception_emotion'] = perception.face_emotion or 'neutral'
```

### 4. Initialize self-narrative on startup

Near where `print_startup_selftest` is called, add:

```python
from brain.beliefs import load_self_narrative, SELF_NARRATIVE_PATH
if not SELF_NARRATIVE_PATH.exists():
    from brain.beliefs import save_self_narrative, DEFAULT_NARRATIVE
    save_self_narrative(dict(DEFAULT_NARRATIVE))
    print("[beliefs] self-narrative initialized")
else:
    print("[beliefs] self-narrative loaded")
```

---

## Definition of Done

- `state/self_narrative.json` exists after first startup
- `get_self_narrative_for_prompt()` returns a non-empty string that appears in the system prompt
- After 10 turns of conversation, `state/self_narrative.json` updates with new `who_i_am`, `how_i_feel`, `patterns_i_notice`
- `self_limits` in the JSON never changes regardless of conversation content
- When Ava is asked "who are you?" or "how are you feeling?", her answer reflects the current narrative rather than a static personality description
- If LLM call fails during narrative update, the system continues normally

---

## Do NOT Change

- `build_belief_state()` at the top of `beliefs.py` — leave it exactly as is
- `brain/camera.py`, `brain/trust_manager.py`, `brain/health.py`, `brain/goals.py`
- Memory system, profile system, UI
- Ava's core personality file / `ava_personality.txt`

---

## What Comes Next

Phase 5 creates `brain/workspace.py` — the Global Workspace that ties all of this into one unified state object, replacing scattered `globals()` reads with a single source of truth.
