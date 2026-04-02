# Ava v2 — Human Brain Architecture Plan (Updated)
## For Cursor AI — Based on Actual Codebase Audit

---

## What Ava Already Has (Don't Touch)

These are working and solid. Do NOT rewrite them:

| Module | What It Does | Status |
|---|---|---|
| `brain/camera.py` | Full camera pipeline — detect, capture, train, recognize faces via OpenCV LBPH | ✅ Solid |
| `brain/trust_manager.py` | Full trust level system per person — owner, trusted, stranger, blocked | ✅ Solid |
| `brain/profile_manager.py` | Profile CRUD, alias resolution, merging, normalization | ✅ Solid |
| `brain/identity.py` + `identity_resolver.py` | Text-based identity claim resolution + profile lookup | ✅ Solid |
| `brain/health.py` | System health checks, behavior modifiers (initiative_scale, confidence_scale) | ✅ Solid |
| `brain/goals.py` | Dynamic goal blending (7 goal types) driven by mood + camera + health | ✅ Solid |
| `brain/initiative.py` | Candidate selection using belief state + goals + health | ✅ Solid |
| `brain/output_guard.py` | Scrubs bad output from replies and history | ✅ Solid |
| `brain/shared.py` | Utility functions (clamp, timestamps, JSON, text extraction) | ✅ Solid |
| `brain/memory_bridge.py` | Bridges memory context into build_prompt | ✅ Solid |
| `brain/selfstate.py` | Self-state query detection and reply generation | ✅ Solid |
| `avaagent.py` | **Overlays are fully removed.** Direct imports. 6,397 lines. | ✅ Clean |

---

## What Exists But Is Shallow (Needs Depth)

These modules exist but are thin wrappers or stubs right now:

| Module | Problem | What It Should Become |
|---|---|---|
| `brain/beliefs.py` | Only 32 lines. Just keyword matching on last user message. No self-model. | Full self-narrative + inner monologue (see Phase 3) |
| `brain/memory.py` | 17 lines. Just a bridge delegate — no actual logic. | Episodic memory with emotional tagging + face-triggered recall (see Phase 2) |
| `brain/perception.py` | 24 lines. Just a bridge wrapper around old camera state functions. | Real perception aggregator — the Thalamus (see Phase 1) |
| `brain/response.py` | 28 lines. Thin wrapper around scrub + generate_autonomous_message. | Can stay thin, but `generate_autonomous_message` needs visual context injected |

---

## What's Missing Entirely (New Modules to Build)

| Missing | Human Brain Equivalent | Priority |
|---|---|---|
| `brain/workspace.py` | Global Workspace / Consciousness | 🔴 High — ties everything together |
| `brain/emotion.py` | Amygdala — emotional reaction to what camera sees | 🟡 Medium |
| Face emotion detection | Visual Cortex upgrade — what expression is the user making | 🟡 Medium |
| `brain/attention.py` | Reticular Formation — is user looking? should Ava speak? | 🟡 Medium |
| Self-narrative persistence | Default Mode Network — Ava's rolling sense of self | 🟡 Medium |

---

## The Core Problem to Solve First

Right now `avaagent.py` passes `globals()` as `g` or `host` into every brain module. This means:
- Every module reaches into a 6,000-line global namespace
- There's no single source of truth for "what is Ava currently aware of"
- Camera, mood, goals, and memory are all separate reads that can go stale mid-conversation

The fix is `brain/workspace.py` — a lightweight state object that gets built once per tick and passed everywhere.

---

## Step-by-Step Plan

---

### PHASE 1 — Upgrade `perception.py` (The Thalamus)
**Goal:** One function that reads camera + user text and returns a clean unified snapshot.

**Tell Cursor:**

Replace the current 24-line bridge in `brain/perception.py` with a real `PerceptionState` dataclass:

```python
@dataclass
class PerceptionState:
    frame: Any                    # raw camera frame
    face_detected: bool           # is a face in frame
    face_identity: str | None     # recognized person_id
    face_emotion: str | None      # "happy", "neutral", "angry", "surprised", etc.
    gaze_present: bool            # is user looking toward camera
    person_count: int             # how many faces detected
    user_text: str                # latest message text
    salience: float               # 0.0–1.0 how much attention this deserves
    timestamp: float
```

Add `build_perception(camera_manager, image, g, user_text) -> PerceptionState` function.

For `face_emotion`: use `deepface` library — `DeepFace.analyze(frame, actions=['emotion'], enforce_detection=False)`. Catch all exceptions and default to `"neutral"`.

For `person_count`: run the existing cascade `detectMultiScale` and return `len(faces)`.

For `salience`: high if face detected + user just spoke, low if no face or user is idle.

---

### PHASE 2 — Upgrade `memory.py` (The Hippocampus)
**Goal:** Memory isn't just a delegate — it tags memories with emotion and can be triggered by a face.

**Tell Cursor:**

Expand `brain/memory.py` with these functions (they call the existing `remember_memory` / `search_reflections` from `avaagent.py` via host):

1. `remember_with_context(host, text, person_id, perception: PerceptionState)` 
   - Calls existing `remember_memory` but automatically appends:
     - `emotional_valence`: derived from `perception.face_emotion` ("positive" / "negative" / "neutral")
     - `visual_context`: `f"face={'yes' if perception.face_detected else 'no'}, emotion={perception.face_emotion}"`
     - `tags`: include `["visual_context"]` if face was detected

2. `recall_for_person(host, person_id: str, limit=5) -> list[str]`
   - Calls existing `search_reflections` with the person's name as query
   - Returns the top `limit` results as plain strings
   - **This gets called automatically when a face is recognized — surface that person's memories into context**

3. `decay_tick(host)` — lower importance score of memories not accessed in 30+ days (call this once on startup)

---

### PHASE 3 — Upgrade `beliefs.py` (The Default Mode Network / Self-Awareness)
**Goal:** Ava has a persistent inner monologue — a rolling self-narrative she updates after each conversation.

**Tell Cursor:**

Rewrite `brain/beliefs.py` to have two layers:

**Layer 1 — Keep existing keyword belief detection** (it works, just keep it)

**Layer 2 — Add persistent self-narrative:**

```python
SELF_NARRATIVE_PATH = "state/self_narrative.json"

def load_self_narrative() -> dict:
    # Returns: { "who_i_am": str, "how_i_feel": str, "patterns_i_notice": str, "updated_at": str }

def update_self_narrative(host, conversation_summary: str, mood: dict, perception: PerceptionState):
    # After each conversation ends, call the LLM with a short prompt:
    # "Based on this conversation, update Ava's self-narrative in 1-2 sentences per field."
    # Save result to SELF_NARRATIVE_PATH

def get_self_narrative_for_prompt() -> str:
    # Returns formatted string injected into system prompt as "Ava's inner monologue"
    narrative = load_self_narrative()
    return f"[Inner monologue] {narrative['who_i_am']} {narrative['how_i_feel']} {narrative['patterns_i_notice']}"
```

Wire `get_self_narrative_for_prompt()` into `build_prompt()` in `avaagent.py` — add it to the system message.

---

### PHASE 4 — Add `emotion.py` (The Amygdala)
**Goal:** Camera visuals affect Ava's mood weights, not just her words.

**Tell Cursor:**

Create `brain/emotion.py`:

```python
def process_visual_emotion(perception: PerceptionState, current_mood: dict) -> dict:
    """
    Takes what the camera sees and nudges Ava's mood weights.
    Returns updated mood dict.
    """
    mood = dict(current_mood)
    
    if not perception.face_detected:
        # No face — was there one before? Raise loneliness/alertness slightly
        mood['loneliness'] = min(1.0, mood.get('loneliness', 0.0) + 0.05)
        mood['engagement'] = max(0.0, mood.get('engagement', 0.5) - 0.08)
    else:
        mood['loneliness'] = max(0.0, mood.get('loneliness', 0.0) - 0.05)
        mood['engagement'] = min(1.0, mood.get('engagement', 0.5) + 0.06)
        
        if perception.face_emotion in ('happy', 'surprise'):
            mood['warmth'] = min(1.0, mood.get('warmth', 0.5) + 0.05)
            mood['care'] = min(1.0, mood.get('care', 0.5) + 0.03)
        elif perception.face_emotion in ('angry', 'fear', 'disgust'):
            mood['concern'] = min(1.0, mood.get('concern', 0.0) + 0.08)
            mood['caution'] = min(1.0, mood.get('caution', 0.0) + 0.06)
        elif perception.face_emotion == 'sad':
            mood['care'] = min(1.0, mood.get('care', 0.5) + 0.07)
            mood['support_drive'] = min(1.0, mood.get('support_drive', 0.0) + 0.08)
    
    return mood
```

Call `process_visual_emotion()` inside `camera_tick_fn` in `avaagent.py` after `camera_manager.analyze()`, and pass the result into the existing `save_mood()`.

---

### PHASE 5 — Add `attention.py` (The Reticular Formation)
**Goal:** Ava knows when the user is present and paying attention before she speaks.

**Tell Cursor:**

Create `brain/attention.py`:

```python
@dataclass 
class AttentionState:
    user_present: bool         # face detected
    user_engaged: bool         # face detected + recent message
    should_speak: bool         # whether Ava should initiate
    suppression_reason: str    # why she's being quiet if suppressed

def compute_attention(perception: PerceptionState, seconds_since_last_message: float) -> AttentionState:
    present = perception.face_detected
    engaged = present and seconds_since_last_message < 120  # 2 min window
    
    if not present:
        return AttentionState(False, False, False, "no_face_detected")
    if seconds_since_last_message > 300:  # 5 min silence
        return AttentionState(True, False, False, "user_idle_too_long")
    if perception.face_emotion in ('angry', 'disgust'):
        return AttentionState(True, engaged, False, "negative_expression_detected")
    
    return AttentionState(True, engaged, engaged, "clear")
```

In `choose_initiative_candidate()` in `brain/initiative.py`, add an early return:
```python
attention = compute_attention(perception_state, seconds_since_last_message)
if not attention.should_speak:
    return None, attention.suppression_reason, debug
```

---

### PHASE 6 — Build `workspace.py` (Global Workspace — The Conscious Layer)
**Goal:** One object that holds everything Ava is "currently aware of." All modules read from it instead of doing their own stale reads.

**Tell Cursor:**

Create `brain/workspace.py`:

```python
@dataclass
class WorkspaceState:
    perception: PerceptionState
    attention: AttentionState
    active_memory: list[str]       # top recalled memories for this moment
    active_goals: dict             # current goal blend from goals.py
    emotional_state: dict          # current mood dict
    self_narrative: str            # from beliefs.py
    active_person: dict            # current profile
    health: dict                   # from health.py
    timestamp: float

class Workspace:
    def __init__(self):
        self._state: WorkspaceState | None = None

    def tick(self, camera_manager, image, g, user_text: str) -> WorkspaceState:
        """Call this once per chat_fn / camera_tick_fn. Builds fresh state."""
        perception = build_perception(camera_manager, image, g, user_text)
        attention = compute_attention(perception, ...)
        active_memory = recall_for_person(g, g.get('active_person_id'), limit=5)
        active_goals = recalculate_operational_goals(g)
        emotional_state = process_visual_emotion(perception, load_mood(g))
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
            timestamp=time.time()
        )
        return self._state

    @property
    def state(self) -> WorkspaceState | None:
        return self._state
```

In `avaagent.py`:
- Create `workspace = Workspace()` near the top with the other module inits
- In `build_prompt()`: replace the 5 separate state reads with `ws = workspace.tick(...)`
- In `camera_tick_fn()`: call `workspace.tick()` at the top, use `ws.perception` everywhere
- Pass `ws` into `choose_initiative_candidate()` so it uses attention gating

---

## Priority Order for Cursor

Do these in exact order — each phase depends on the previous:

1. **Phase 1** — `perception.py` upgrade (PerceptionState dataclass + DeepFace emotion)
2. **Phase 4** — `emotion.py` (amygdala) — needs PerceptionState
3. **Phase 5** — `attention.py` — needs PerceptionState  
4. **Phase 2** — `memory.py` upgrade — wire face recognition to auto-recall
5. **Phase 3** — `beliefs.py` upgrade — self-narrative persistence
6. **Phase 6** — `workspace.py` — tie it all together, replace globals() passthrough in build_prompt + camera_tick_fn

---

## What Changes in `avaagent.py`

Minimal changes — only these 4 things:

1. Add `from brain.workspace import Workspace` and `workspace = Workspace()` near top
2. In `build_prompt()` — add `ws = workspace.tick(...)` at top, inject `ws.self_narrative` into system prompt
3. In `camera_tick_fn()` — add `ws = workspace.tick(...)` at top, call `process_visual_emotion` and save mood
4. In `choose_initiative_candidate()` call — pass `perception_state` so attention gating works

**Do NOT touch:** memory system, profile system, trust system, goals/initiative logic, health system, UI, or the MEMORY block parser. These all work.

---

## Recommended Library Addition

Add to `requirements.txt`:
```
deepface
```

DeepFace wraps multiple backends (OpenCV, dlib, VGG-Face). It adds facial emotion detection in one line:
```python
result = DeepFace.analyze(frame, actions=['emotion'], enforce_detection=False)
face_emotion = result[0]['dominant_emotion']  # "happy", "sad", "angry", "neutral", etc.
```

---

## End Result — What Makes Ava Feel Human

After all phases:
- **She reacts to your face before you say a word** — mood shifts based on your expression
- **She knows when not to talk** — suppresses initiative if you look angry or haven't been present
- **She remembers you specifically** — seeing your face surfaces your memories automatically
- **She has an inner life** — persistent self-narrative that evolves conversation by conversation
- **All her modules share one brain state** — no more stale reads, no more globals() scatter
