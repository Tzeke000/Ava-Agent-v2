# Ava — Phase 2: RELATIONAL
## Level 2 of 5 — Social Awareness
### Complete Phase 1 first. Feed this to Cursor after Phase 1 is tested and working.

---

## Context — What Exists After Phase 1

- `brain/perception.py` now returns a real `PerceptionState` dataclass ✅
- `PerceptionState` fields available: `face_detected`, `face_emotion`, `face_identity`, `person_count`, `salience`, `user_text`, `timestamp`
- `camera_tick_fn` and `chat_fn` in `avaagent.py` both call `build_perception()` ✅
- `brain/trust_manager.py`, `brain/profile_manager.py`, `brain/identity.py` all work and should NOT be touched

---

## Goal of This Phase

Ava's mood shifts when she sees a negative or positive face.
She suppresses her initiative when the user is angry or absent.
She starts building an emotional memory of each person she knows.

---

## What to Build

### 1. Create `brain/emotion.py` — The Amygdala

Create a new file `brain/emotion.py`:

```python
from __future__ import annotations
from .perception import PerceptionState


def process_visual_emotion(perception: PerceptionState, current_mood: dict) -> dict:
    """
    Takes what the camera sees and nudges Ava's mood weights.
    Called every camera tick. Never raises.
    Returns updated mood dict with all values clamped 0.0–1.0.
    """
    mood = dict(current_mood)

    if not perception.face_detected:
        # No face — nudge toward loneliness, pull back engagement
        mood['loneliness'] = min(1.0, mood.get('loneliness', 0.0) + 0.05)
        mood['engagement'] = max(0.0, mood.get('engagement', 0.5) - 0.08)
    else:
        # Face present — pull back loneliness, increase engagement
        mood['loneliness'] = max(0.0, mood.get('loneliness', 0.0) - 0.05)
        mood['engagement'] = min(1.0, mood.get('engagement', 0.5) + 0.06)

        emotion = perception.face_emotion or "neutral"

        if emotion in ('happy', 'surprise'):
            mood['warmth'] = min(1.0, mood.get('warmth', 0.5) + 0.05)
            mood['care'] = min(1.0, mood.get('care', 0.5) + 0.03)

        elif emotion in ('angry', 'disgust', 'fear'):
            mood['concern'] = min(1.0, mood.get('concern', 0.0) + 0.08)
            mood['caution'] = min(1.0, mood.get('caution', 0.0) + 0.06)
            mood['warmth'] = max(0.0, mood.get('warmth', 0.5) - 0.03)

        elif emotion == 'sad':
            mood['care'] = min(1.0, mood.get('care', 0.5) + 0.07)
            mood['support_drive'] = min(1.0, mood.get('support_drive', 0.0) + 0.08)

    # Clamp all values
    return {k: max(0.0, min(1.0, v)) for k, v in mood.items()}
```

### 2. Wire `emotion.py` into `avaagent.py` — `camera_tick_fn`

In `camera_tick_fn`, after the `build_perception()` call (from Phase 1), add:

```python
from brain.emotion import process_visual_emotion

# Load current mood, apply visual emotion, save it back
current_mood = load_mood() if callable(globals().get('load_mood')) else {}
updated_mood = process_visual_emotion(perception, current_mood)
if callable(globals().get('save_mood')):
    save_mood(updated_mood)
```

### 3. Create `brain/attention.py` — The Reticular Formation

Create a new file `brain/attention.py`:

```python
from __future__ import annotations
from dataclasses import dataclass
from .perception import PerceptionState


@dataclass
class AttentionState:
    user_present: bool
    user_engaged: bool
    should_speak: bool
    suppression_reason: str   # internal log only — never shown to user


def compute_attention(perception: PerceptionState, seconds_since_last_message: float) -> AttentionState:
    """
    Decides whether Ava should speak right now based on what she sees.
    Called before choose_initiative_candidate().
    """
    if not perception.face_detected:
        return AttentionState(False, False, False, "no_face_detected")

    if seconds_since_last_message > 300:  # 5 minutes of silence
        return AttentionState(True, False, False, "user_idle_too_long")

    if perception.face_emotion in ('angry', 'disgust'):
        return AttentionState(True, True, False, "negative_expression_detected")

    engaged = seconds_since_last_message < 120  # active within 2 minutes
    return AttentionState(True, engaged, engaged, "clear")
```

### 4. Wire `attention.py` into `brain/initiative.py`

In `brain/initiative.py`, update `choose_initiative_candidate()`:

At the very top of the function, before any other logic, add:

```python
from .attention import AttentionState

# Accept optional attention_state parameter
def choose_initiative_candidate(host, person_id: str, expression_state=None, attention_state=None):
    # Attention gate — if Ava should not speak, return immediately
    if attention_state is not None and not attention_state.should_speak:
        return None, attention_state.suppression_reason, {}
    
    # ... rest of existing function unchanged ...
```

In `avaagent.py`, wherever `choose_initiative_candidate` is called, compute and pass `attention_state`:

```python
from brain.attention import compute_attention
import time

seconds_since = time.time() - globals().get('_last_user_message_ts', time.time())
attention = compute_attention(perception, seconds_since)
candidate, reason, debug = choose_initiative_candidate(
    globals(), active_person_id, 
    expression_state=expression_state,
    attention_state=attention
)
```

Add `_last_user_message_ts = time.time()` at the top of `chat_fn` to track when the user last spoke.

### 5. Add emotional association tracking to `brain/identity.py`

In the `IdentityRegistry` class, add one method:

```python
def update_emotional_association(self, person_id: str, face_emotion: str, g: dict):
    """
    After each recognized interaction, log what emotion the person showed.
    Stores a rolling list (max 10) and derives a dominant association.
    """
    import json
    profile_path = self.profiles_dir / f"{person_id}.json"
    if not profile_path.exists():
        return
    try:
        profile = json.loads(profile_path.read_text(encoding='utf-8'))
        history = profile.get('emotion_history', [])
        history.append(face_emotion or 'neutral')
        history = history[-10:]  # keep last 10 only

        # Derive dominant
        from collections import Counter
        dominant = Counter(history).most_common(1)[0][0]

        profile['emotion_history'] = history
        profile['dominant_emotion'] = dominant
        profile_path.write_text(json.dumps(profile, indent=2, ensure_ascii=False), encoding='utf-8')
    except Exception:
        pass
```

Call `identity_registry.update_emotional_association(person_id, perception.face_emotion, globals())` at the end of `camera_tick_fn` when a person is recognized.

---

## Definition of Done

- `brain/emotion.py` exists and `process_visual_emotion()` runs every camera tick
- Ava's mood UI values visibly shift after a few ticks of a strongly positive or negative expression
- `brain/attention.py` exists and `compute_attention()` returns `should_speak=False` when no face is detected
- Initiative is suppressed (no autonomous messages) when no face is in frame
- Person profiles gain `emotion_history` and `dominant_emotion` fields after interactions

---

## Do NOT Change

- `brain/camera.py`
- `brain/trust_manager.py`
- `brain/profile_manager.py`
- `brain/health.py`
- `brain/goals.py`
- Memory system
- UI layout

---

## What Comes Next

Phase 3 uses `PerceptionState` + the recognized `face_identity` to trigger autobiographical memory recall.
