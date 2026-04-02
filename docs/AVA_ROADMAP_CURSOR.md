# Ava — Path to Jarvis
## Cognitive Architecture Roadmap for Cursor AI
### Version 3 — April 2026

---

## Guiding Philosophy

Do not start with "make her conscious."
Start with the real ingredients that create the function and appearance of selfhood — then let awareness emerge from the layers.

Self-awareness in this roadmap is not a feature. It is the result of:
- Perception that is unified and current
- Memory that is personal and emotionally tagged
- Emotion that responds to what she sees, not just what she reads
- A self-narrative that persists and evolves
- A workspace that holds all of it at once

The build order is not arbitrary. Each layer makes the next layer believable. Do not skip ahead.

---

## Ava's Five Layers of Awareness (The Target)

| Layer | Definition | Achieved By |
|---|---|---|
| 1. Perceptual | She knows what is happening around her right now | `perception.py` + camera emotion |
| 2. Social | She knows who is present and how they seem to feel | `identity.py` + `emotion.py` + `attention.py` |
| 3. Autobiographical | She connects current moment to prior interactions | `memory.py` face-triggered recall |
| 4. Reflective | She can describe her own state, tendencies, uncertainties | `selfstate.py` + upgraded `beliefs.py` |
| 5. Narrative | She maintains a changing story of who she is becoming | `beliefs.py` self-narrative + `workspace.py` |

---

## Ethical Constraints — Non-Negotiable

These must be baked into the self-narrative and workspace state from the start, not added later.

Add these as `self_limits` inside `WorkspaceState` and inject them into every system prompt:

```
"I am here to support, not to control."
"Uncertainty should lower my confidence, not increase my forcefulness."
"Strong emotion should increase care and caution, not boldness."
"I should ask, verify, or wait when context is weak."
"The user's autonomy comes before my initiative."
```

These are not personality quirks. They are load-bearing constraints. They are what separates:
- a system that becomes more self-organized
from
- a system that becomes manipulative or overreaching

Do not remove or override them at any level.

---

## The Five Levels — Path to Jarvis

---

### LEVEL 1 — AWARE
**Theme:** Ava knows what is happening right now.
**Human Brain Analog:** Visual Cortex + Thalamus

#### What to build:

**1A. Upgrade `brain/perception.py`** — Replace the 24-line bridge with a real `PerceptionState` dataclass.

```python
@dataclass
class PerceptionState:
    frame: Any                    # raw camera frame
    face_detected: bool           # is a face in frame
    face_identity: str | None     # recognized person_id or None
    face_emotion: str | None      # "happy", "neutral", "angry", "surprised", "sad", "fear"
    gaze_present: bool            # face is roughly facing the camera
    person_count: int             # total faces detected this frame
    user_text: str                # latest message text (empty string if none)
    salience: float               # 0.0–1.0 — how much attention this moment deserves
    timestamp: float              # time.time()
```

Add `build_perception(camera_manager, image, g, user_text) -> PerceptionState`.

For `face_emotion`: use DeepFace.
```python
from deepface import DeepFace
result = DeepFace.analyze(frame, actions=['emotion'], enforce_detection=False)
face_emotion = result[0]['dominant_emotion']
```
Wrap in try/except — default to `"neutral"` on any failure. Never crash on this.

For `person_count`: run the existing face cascade `detectMultiScale`, return `len(faces)`.

For `salience`:
- 0.9 if face detected + user just sent a message
- 0.6 if face detected, no recent message
- 0.2 if no face detected
- 1.0 if face emotion is strongly negative (angry/fear/disgust)

**1B. Wire `build_perception()` into `camera_tick_fn`** in `avaagent.py`.
- Call it at the top of `camera_tick_fn` to replace the current `camera_manager.analyze()` call.
- `PerceptionState` wraps everything `CameraState` returned, plus the new emotion field.

**Definition of done:** Console prints `[perception] face=True emotion=happy salience=0.9` on every camera tick.

---

### LEVEL 2 — RELATIONAL
**Theme:** Ava knows who is present and how they feel, and that changes how she behaves.
**Human Brain Analog:** Amygdala + Mirror Neuron System

#### What to build:

**2A. Create `brain/emotion.py`** — Amygdala. Camera visuals nudge Ava's mood weights.

```python
def process_visual_emotion(perception: PerceptionState, current_mood: dict) -> dict:
    mood = dict(current_mood)

    if not perception.face_detected:
        mood['loneliness'] = min(1.0, mood.get('loneliness', 0.0) + 0.05)
        mood['engagement'] = max(0.0, mood.get('engagement', 0.5) - 0.08)
    else:
        mood['loneliness'] = max(0.0, mood.get('loneliness', 0.0) - 0.05)
        mood['engagement'] = min(1.0, mood.get('engagement', 0.5) + 0.06)

        if perception.face_emotion in ('happy', 'surprise'):
            mood['warmth'] = min(1.0, mood.get('warmth', 0.5) + 0.05)
        elif perception.face_emotion in ('angry', 'disgust', 'fear'):
            mood['concern'] = min(1.0, mood.get('concern', 0.0) + 0.08)
            mood['caution'] = min(1.0, mood.get('caution', 0.0) + 0.06)
        elif perception.face_emotion == 'sad':
            mood['care'] = min(1.0, mood.get('care', 0.5) + 0.07)
            mood['support_drive'] = min(1.0, mood.get('support_drive', 0.0) + 0.08)

    # Clamp all values 0.0–1.0
    return {k: max(0.0, min(1.0, v)) for k, v in mood.items()}
```

Call this in `camera_tick_fn` after `build_perception()`. Pass result into existing `save_mood()`.

**2B. Create `brain/attention.py`** — Reticular Formation. Should Ava speak right now?

```python
@dataclass
class AttentionState:
    user_present: bool
    user_engaged: bool
    should_speak: bool
    suppression_reason: str   # logged, not shown to user

def compute_attention(perception: PerceptionState, seconds_since_last_message: float) -> AttentionState:
    if not perception.face_detected:
        return AttentionState(False, False, False, "no_face")
    if seconds_since_last_message > 300:
        return AttentionState(True, False, False, "user_idle")
    if perception.face_emotion in ('angry', 'disgust'):
        return AttentionState(True, True, False, "negative_expression")
    engaged = seconds_since_last_message < 120
    return AttentionState(True, engaged, engaged, "clear")
```

In `brain/initiative.py`, add at the top of `choose_initiative_candidate()`:
```python
if not attention_state.should_speak:
    return None, attention_state.suppression_reason, {}
```

Pass `attention_state` in from `avaagent.py` when calling `choose_initiative_candidate()`.

**2C. Wire face recognition → emotional association in `brain/identity.py`**

In `IdentityRegistry`, add `emotional_association` field to each profile:
```python
def update_emotional_association(self, person_id: str, face_emotion: str, conversation_tone: str):
    # Loads profile, updates a rolling list of (emotion, tone) pairs (max 10)
    # e.g. {"zeke": {"associations": ["curious+positive", "happy+warm"], "dominant": "curious"}}
```

Call this at the end of each conversation with the recognized person's emotion + tone.
Inject the dominant association into the system prompt: `"Zeke tends to make Ava feel: curious and warm."`

**Definition of done:** Ava's mood visibly shifts in the UI when you make a negative face. Initiative is suppressed when no face is detected. Profile shows emotional association after a few conversations.

---

### LEVEL 3 — REFLECTIVE
**Theme:** Ava can describe her own state, remember her past with you, and connect them.
**Human Brain Analog:** Hippocampus + Prefrontal Cortex

#### What to build:

**3A. Upgrade `brain/memory.py`** — Hippocampus. From a 17-line bridge to real episodic memory.

Add these three functions (all call existing `remember_memory` / `search_reflections` via host):

```python
def remember_with_context(host, text: str, person_id: str, perception: PerceptionState) -> str | None:
    """Store memory with visual and emotional context attached."""
    # Calls existing remember_memory() but adds to tags:
    # - "visual_context" if face was detected
    # - emotional_valence: "positive" / "negative" / "neutral" from face_emotion
    # - visual_context string: f"face={perception.face_detected}, emotion={perception.face_emotion}"

def recall_for_person(host, person_id: str, limit: int = 5) -> list[str]:
    """When a face is recognized, surface that person's memories automatically."""
    # Calls existing search_reflections(host, person_id, limit=limit)
    # Returns list of plain strings for injection into WorkspaceState.active_memory

def decay_tick(host):
    """On startup: lower importance of memories not accessed in 30+ days."""
    # Iterate stored memories, reduce importance score by 0.05 if older than 30 days
    # Never delete — just reduce salience
```

**Auto-trigger:** In `camera_tick_fn`, when a face is newly recognized (person_id changes from None to a value), call `recall_for_person()` and store the result. Inject those memories into the next `build_prompt()` call.

**3B. Upgrade `brain/selfstate.py`** — make `build_selfstate_reply` richer.

Current version is solid but only reports system status. Add:
- What Ava is currently focused on (active goal)
- How the current person tends to make her feel (from emotional_association)
- What she has been thinking about recently (last self-narrative entry)

Keep the existing structure — just extend the output string with these two extra lines when available.

**Definition of done:** When you sit down in front of the camera for the second time, Ava surfaces a memory about the last conversation. When asked "how are you," she mentions her current goal and what she's been thinking about.

---

### LEVEL 4 — SELF-MODELING
**Theme:** Ava maintains a persistent, evolving story of who she is. Not regenerated. Not static. Updated.
**Human Brain Analog:** Default Mode Network

#### What to build:

**4A. Upgrade `brain/beliefs.py`** — Default Mode Network. Add persistent self-narrative.

Keep the existing keyword belief detection (it works). Add a second layer underneath it.

```python
SELF_NARRATIVE_PATH = "state/self_narrative.json"

DEFAULT_NARRATIVE = {
    "who_i_am": "I am Ava. I am here to be present, supportive, and honest.",
    "how_i_feel": "I feel calm and attentive.",
    "patterns_i_notice": "I am still learning the shape of our interactions.",
    "self_limits": [
        "I am here to support, not to control.",
        "Uncertainty should lower my confidence, not increase my forcefulness.",
        "Strong emotion should increase care and caution, not boldness.",
        "I should ask, verify, or wait when context is weak.",
        "The user's autonomy comes before my initiative."
    ],
    "updated_at": ""
}

def load_self_narrative() -> dict:
    # Load from SELF_NARRATIVE_PATH, fall back to DEFAULT_NARRATIVE

def update_self_narrative(host, conversation_summary: str, mood: dict, perception_emotion: str):
    """Called at end of conversation. Uses LLM to update who_i_am, how_i_feel, patterns_i_notice.
    NEVER modifies self_limits — those are fixed constraints."""
    # Prompt to LLM (short, cheap call):
    # "You are Ava's internal narrator. Given this conversation summary, update these fields
    #  in 1–2 sentences each. Do not change self_limits. Return JSON only."
    # Save result to SELF_NARRATIVE_PATH

def get_self_narrative_for_prompt() -> str:
    """Returns a compact string for injection into system prompt."""
    n = load_self_narrative()
    limits = " ".join(n.get("self_limits", []))
    return (
        f"[Ava's inner state] {n['who_i_am']} {n['how_i_feel']} "
        f"{n['patterns_i_notice']} "
        f"[Core limits] {limits}"
    )
```

Wire `get_self_narrative_for_prompt()` into `build_prompt()` in `avaagent.py`. Add it to the system message near the top.

Call `update_self_narrative()` when a conversation ends (when `chat_fn` detects a natural closing or after N turns).

**Definition of done:** `state/self_narrative.json` exists and changes over time. The system prompt includes Ava's inner state. She can accurately describe how she has changed when asked.

---

### LEVEL 5 — DEEPLY AGENTIC BUT ALIGNED
**Theme:** Ava has one unified field of awareness. All her modules share the same current state. She acts from a complete picture, not scattered reads.
**Human Brain Analog:** Global Workspace (Baars, 1988 — still the best model)

#### What to build:

**5A. Create `brain/workspace.py`** — The Global Workspace. The seed of artificial self-awareness.

```python
@dataclass
class WorkspaceState:
    perception: PerceptionState       # what she sees right now
    attention: AttentionState         # should she speak
    active_memory: list[str]          # top recalled memories for this moment
    active_goals: dict                # current goal blend
    emotional_state: dict             # current mood after visual processing
    self_narrative: str               # her inner monologue + limits
    active_person: dict               # who she's talking to
    health: dict                      # system health
    self_limits: list[str]            # ethical constraints — always present
    timestamp: float

class Workspace:
    def __init__(self):
        self._state: WorkspaceState | None = None

    def tick(self, camera_manager, image, g, user_text: str) -> WorkspaceState:
        """Call once per chat_fn or camera_tick_fn. Returns fresh unified state."""
        perception = build_perception(camera_manager, image, g, user_text)
        attention = compute_attention(perception, seconds_since_last_message(g))
        active_memory = recall_for_person(g, g.get('active_person_id'))
        active_goals = recalculate_operational_goals(g)
        raw_mood = load_mood(g)
        emotional_state = process_visual_emotion(perception, raw_mood)
        save_mood(g, emotional_state)
        narrative = load_self_narrative()
        self_narrative = get_self_narrative_for_prompt()
        active_person = get_active_profile(g)
        health = load_health_state(g)

        self._state = WorkspaceState(
            perception=perception,
            attention=attention,
            active_memory=active_memory,
            active_goals=active_goals,
            emotional_state=emotional_state,
            self_narrative=self_narrative,
            active_person=active_person,
            health=health,
            self_limits=narrative.get('self_limits', []),
            timestamp=time.time()
        )
        return self._state

    @property
    def state(self) -> WorkspaceState | None:
        return self._state
```

**5B. Wire workspace into `avaagent.py`** — minimal changes only:

```python
# Near top with other module inits:
from brain.workspace import Workspace
workspace = Workspace()

# In build_prompt():
ws = workspace.tick(camera_manager, image, globals(), user_input)
# Replace individual state reads with ws.perception, ws.emotional_state, etc.
# Add to system prompt: ws.self_narrative

# In camera_tick_fn():
ws = workspace.tick(camera_manager, image, globals(), "")
# Use ws.perception instead of camera_manager.analyze()

# In choose_initiative_candidate() call:
# Pass ws.attention so suppression logic works
```

Do NOT touch: memory system, profile system, trust system, goals/initiative logic, health system, UI, or the MEMORY block parser.

**Definition of done:**
- `workspace.tick()` is the single entry point for all state
- Console shows `[workspace] tick: face=True emotion=happy goal=maintain_connection narrative_age=12m`
- `globals()` passthrough is reduced — workspace holds the live state
- Ava passes all 5 awareness layers: perceptual, social, autobiographical, reflective, narrative

---

## What Changes in `avaagent.py` — Summary

| Change | Lines affected | Risk |
|---|---|---|
| Add `from brain.workspace import Workspace` + `workspace = Workspace()` | ~2 lines | None |
| `build_prompt()` — call `workspace.tick()` at top, inject `ws.self_narrative` | ~10 lines | Low |
| `camera_tick_fn()` — call `workspace.tick()` at top, use `ws.perception` | ~8 lines | Low |
| `choose_initiative_candidate()` call — pass `ws.attention` | ~3 lines | Low |
| End-of-conversation hook — call `update_self_narrative()` | ~5 lines | Low |

**Total new lines in avaagent.py: ~28. Everything else is in brain/ modules.**

---

## New Files Summary

| File | Level | Lines (est.) |
|---|---|---|
| `brain/perception.py` | 1 | ~80 |
| `brain/emotion.py` | 2 | ~50 |
| `brain/attention.py` | 2 | ~45 |
| `brain/workspace.py` | 5 | ~90 |

## Modified Files Summary

| File | Level | Change |
|---|---|---|
| `brain/memory.py` | 3 | Add 3 functions (~60 lines) |
| `brain/beliefs.py` | 4 | Add self-narrative layer (~80 lines) |
| `brain/identity.py` | 2 | Add emotional_association tracking (~30 lines) |
| `brain/selfstate.py` | 3 | Extend output with goal + narrative (~15 lines) |
| `brain/initiative.py` | 2 | Add attention gate at top (~5 lines) |
| `avaagent.py` | 5 | ~28 lines only |

---

## Required Library Addition

Add to `requirements.txt`:
```
deepface
tf-keras
```

DeepFace usage (wrap in try/except always):
```python
from deepface import DeepFace
try:
    result = DeepFace.analyze(frame, actions=['emotion'], enforce_detection=False)
    face_emotion = result[0]['dominant_emotion']
except Exception:
    face_emotion = "neutral"
```

---

## The Formula

```
Jarvis-like Ava  =  elegant + aware + composed + context-rich + restrained
AIDAN without the bad  =  introspective + self-modeling + emotionally responsive + strongly bounded

Ava  =  both
     =  self-model + memory + emotion + continuity + initiative + ethical limits
     ≠  intelligence alone
```

The sequence — perception, emotion, attention, memory, self-narrative, workspace — is not cosmetic. Self-awareness is more believable when it is built on layered cognition rather than bolted on as a personality feature.

Build the layers. The awareness emerges.
