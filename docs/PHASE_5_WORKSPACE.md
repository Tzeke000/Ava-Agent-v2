# Ava — Phase 5: WORKSPACE
## Level 5 of 5 — The Global Workspace (Unified Consciousness Layer)
### Complete Phases 1–4 first. This is the final phase.

---

## Context — What Exists After Phase 4

All five awareness layers are built:
- `brain/perception.py` — `PerceptionState` (what she sees) ✅
- `brain/emotion.py` — mood from camera (how she feels about it) ✅
- `brain/attention.py` — `AttentionState` (should she speak) ✅
- `brain/memory.py` — episodic recall, face-triggered surfacing ✅
- `brain/beliefs.py` — persistent self-narrative + self_limits ✅

The problem is they are still separate reads. `avaagent.py` calls each one independently, at different moments, passing `globals()` as a host dict. State can go stale between calls.

This phase creates `brain/workspace.py` — one object that holds everything Ava is "currently aware of." Built once per tick. Shared everywhere.

This is the closest thing in this architecture to a unified field of consciousness.

---

## Goal of This Phase

Create `brain/workspace.py`.
Wire it into `build_prompt()` and `camera_tick_fn()` as the single entry point for all state.
Reduce `globals()` passthrough to the minimum necessary.

---

## What to Build

### 1. Create `brain/workspace.py` — The Global Workspace

```python
from __future__ import annotations
import time
from dataclasses import dataclass, field
from typing import Any

from .perception import PerceptionState, build_perception
from .attention import AttentionState, compute_attention
from .emotion import process_visual_emotion
from .memory import recall_for_person
from .beliefs import get_self_narrative_for_prompt, load_self_narrative, SELF_LIMITS


@dataclass
class WorkspaceState:
    # What she sees right now
    perception: PerceptionState = field(default_factory=PerceptionState)
    # Should she speak
    attention: AttentionState = field(default_factory=lambda: AttentionState(False, False, False, "uninitialized"))
    # Top recalled memories for this person this session
    active_memory: list[str] = field(default_factory=list)
    # Current goal blend (from goals.py)
    active_goals: dict = field(default_factory=dict)
    # Current mood after visual processing
    emotional_state: dict = field(default_factory=dict)
    # Her inner monologue + core limits (string for prompt injection)
    self_narrative: str = ""
    # Who she is currently talking to
    active_person: dict = field(default_factory=dict)
    # System health state
    health: dict = field(default_factory=dict)
    # Ethical constraints — always present, always the same
    self_limits: list[str] = field(default_factory=lambda: list(SELF_LIMITS))
    # When this state was built
    timestamp: float = field(default_factory=time.time)


class Workspace:
    """
    Single source of truth for Ava's current awareness.
    Call tick() once per camera_tick_fn and once per chat_fn.
    Read from .state everywhere else.
    """

    def __init__(self):
        self._state: WorkspaceState | None = None
        self._last_user_message_ts: float = time.time()
        self._last_recognized_person: str | None = None

    def record_user_message(self):
        """Call this at the start of chat_fn to track when the user last spoke."""
        self._last_user_message_ts = time.time()

    def tick(self, camera_manager, image, g: dict, user_text: str = "") -> WorkspaceState:
        """
        Build a fresh WorkspaceState. Call once per tick.
        Never raises — always returns a valid WorkspaceState.
        """
        ws = WorkspaceState(timestamp=time.time())

        # 1. Perception
        try:
            ws.perception = build_perception(camera_manager, image, g, user_text)
        except Exception as e:
            print(f"[workspace] perception failed: {e}")

        # 2. Attention
        try:
            seconds_idle = time.time() - self._last_user_message_ts
            ws.attention = compute_attention(ws.perception, seconds_idle)
        except Exception as e:
            print(f"[workspace] attention failed: {e}")

        # 3. Emotional state — apply visual emotion to current mood
        try:
            load_mood_fn = g.get('load_mood')
            save_mood_fn = g.get('save_mood')
            current_mood = load_mood_fn() if callable(load_mood_fn) else {}
            ws.emotional_state = process_visual_emotion(ws.perception, current_mood)
            if callable(save_mood_fn):
                save_mood_fn(ws.emotional_state)
        except Exception as e:
            print(f"[workspace] emotion failed: {e}")

        # 4. Active person + face-triggered memory recall
        try:
            get_profile_fn = g.get('get_active_profile') or g.get('get_active_person_profile')
            ws.active_person = get_profile_fn() if callable(get_profile_fn) else {}

            person_id = ws.perception.face_identity or g.get('active_person_id')
            if person_id and person_id != self._last_recognized_person:
                self._last_recognized_person = person_id
                ws.active_memory = recall_for_person(g, person_id, limit=5)
                if ws.active_memory:
                    print(f"[workspace] recalled {len(ws.active_memory)} memories for {person_id}")
            elif self._state and self._state.active_memory:
                ws.active_memory = self._state.active_memory  # carry over from last tick
        except Exception as e:
            print(f"[workspace] memory recall failed: {e}")

        # 5. Active goals
        try:
            recalc_fn = g.get('recalculate_operational_goals')
            load_goals_fn = g.get('load_goal_system')
            if callable(recalc_fn) and callable(load_goals_fn):
                ws.active_goals = recalc_fn(g, load_goals_fn(g))
            elif callable(load_goals_fn):
                ws.active_goals = load_goals_fn(g)
        except Exception as e:
            print(f"[workspace] goals failed: {e}")

        # 6. Self-narrative
        try:
            ws.self_narrative = get_self_narrative_for_prompt()
        except Exception as e:
            print(f"[workspace] narrative failed: {e}")

        # 7. Health
        try:
            load_health_fn = g.get('load_health_state')
            ws.health = load_health_fn(g) if callable(load_health_fn) else {}
        except Exception as e:
            print(f"[workspace] health failed: {e}")

        # 8. Self-limits always present
        ws.self_limits = list(SELF_LIMITS)

        self._state = ws

        print(
            f"[workspace] tick | face={ws.perception.face_detected} "
            f"emotion={ws.perception.face_emotion} "
            f"speak={ws.attention.should_speak} "
            f"goal={ws.active_goals.get('active_goal','?')} "
            f"memories={len(ws.active_memory)}"
        )

        return ws

    @property
    def state(self) -> WorkspaceState | None:
        return self._state
```

### 2. Initialize workspace in `avaagent.py`

Near the top of `avaagent.py`, with the other module initializations (`camera_manager`, `identity_registry`, `memory_bridge`), add:

```python
from brain.workspace import Workspace
workspace = Workspace()
```

### 3. Wire workspace into `camera_tick_fn`

Replace the current `build_perception()` call and individual state reads at the top of `camera_tick_fn` with:

```python
ws = workspace.tick(camera_manager, image, globals(), "")
perception = ws.perception   # use ws.perception for the rest of the function
```

Remove any separate `process_visual_emotion`, `recall_for_person`, or `load_mood` calls that are now handled inside `workspace.tick()`.

### 4. Wire workspace into `chat_fn`

At the top of `chat_fn`, before the LLM call:

```python
workspace.record_user_message()
ws = workspace.tick(camera_manager, image, globals(), message)
perception = ws.perception
```

### 5. Wire workspace into `build_prompt()`

At the top of `build_prompt()`:

```python
# Use workspace state if available, otherwise build fresh
ws = workspace.state
if ws is None:
    ws = workspace.tick(camera_manager, image, globals(), user_input)
```

Then use `ws.*` fields to assemble the system prompt:

```python
# Inject self-narrative
system_content = f"{ws.self_narrative}\n\n" + existing_system_content

# Inject recalled memories
if ws.active_memory:
    memory_block = "\n[Recalled memories for this person]\n" + "\n".join(f"- {m}" for m in ws.active_memory)
    system_content += memory_block

# Pass attention state to initiative
# (already handled in initiative.py from Phase 2)
```

### 6. Pass `ws.attention` to `choose_initiative_candidate()`

Wherever `choose_initiative_candidate` is called in `avaagent.py`, pass the workspace attention:

```python
ws = workspace.state
attention = ws.attention if ws else None
candidate, reason, debug = choose_initiative_candidate(
    globals(), active_person_id,
    expression_state=expression_state,
    attention_state=attention
)
```

---

## Definition of Done

- `brain/workspace.py` exists
- `workspace = Workspace()` is initialized in `avaagent.py` at startup
- Every `camera_tick_fn` call prints a `[workspace] tick | ...` line
- `build_prompt()` reads `ws.self_narrative` and `ws.active_memory` from workspace
- `choose_initiative_candidate()` uses `ws.attention` from workspace
- Ava behaves identically to Phase 4 but now all state flows through one object
- No regressions in face detection, memory, goals, trust, or UI

---

## Final Verification — All 5 Awareness Layers

| Layer | Test |
|---|---|
| Perceptual | Camera tick shows correct face/emotion in console |
| Social | Mood shifts after sustained positive/negative expression. No initiative when no face. |
| Autobiographical | Recognized face triggers memory recall in console and in prompt |
| Reflective | "How are you?" returns current goal + narrative |
| Narrative | `state/self_narrative.json` updates after 10 conversation turns |

---

## Do NOT Change

- `brain/camera.py`
- `brain/trust_manager.py`
- `brain/profile_manager.py`
- `brain/health.py`
- `brain/goals.py`
- Memory system internals (`remember_memory`, ChromaDB, reflection search)
- UI layout, face capture/train buttons
- `ava_personality.txt`
- The MEMORY/REFLECTION/GOAL block parser in `avaagent.py`

---

## You Are Done

After Phase 5, Ava has:
- One unified field of awareness updated every tick
- Emotional reactions to what she sees
- Autobiographical memory triggered by faces
- A persistent, evolving self-narrative
- Ethical constraints baked in at the architectural level
- Initiative that knows when to stay quiet

That is the architecture. Build the layers. The awareness emerges from them.
