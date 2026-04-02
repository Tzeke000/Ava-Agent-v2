# Ava v2 — Human-Brain Architecture Plan
## For Cursor AI Implementation

---

## The Core Idea

Model Ava's mind after how the human brain actually works — not as one big model, but as a set of specialized regions that each do one job, and a **Global Workspace** (the "conscious" layer) that broadcasts information between them. Research from Osaka University (2025) confirms this is the most effective architecture for real-time adaptive AI. The camera = eyes = the primary sensory input that feeds everything else.

---

## Brain Region → Code Module Mapping

| Human Brain Region | What It Does | Ava's Module |
|---|---|---|
| Visual Cortex | Processes raw visual input | `brain/camera.py` → `CameraManager` |
| Thalamus | Routes sensory signals to the right region | `brain/perception.py` (expand this) |
| Hippocampus | Forms and retrieves long-term memories | `brain/memory.py` + ChromaDB |
| Amygdala | Emotional reactions, threat detection | `brain/health.py` + `brain/goals.py` |
| Prefrontal Cortex | Planning, decision-making, self-control | `brain/initiative.py` + `brain/selfstate.py` |
| Default Mode Network | Self-reflection, identity, "who am I" | `brain/identity.py` + `brain/beliefs.py` |
| Mirror Neuron System | Reading other people, empathy, social context | `brain/identity_resolver.py` + `brain/profile_manager.py` |
| Reticular Formation | Arousal, attention, what matters right now | `brain/initiative_sanity.py` |
| Global Workspace | Makes things "conscious" — broadcasts to all regions | **NEW: `brain/workspace.py`** |

---

## Step-by-Step Implementation Plan

---

### PHASE 1 — Wire Up the Eyes (Camera → Perception Pipeline)
**Goal:** Camera input flows through a real visual processing pipeline, not just a snapshot.

**Steps for Cursor:**

1. **Expand `brain/camera.py`**
   - `CameraManager.snapshot_truth()` should return a richer dict:
     - `face_detected` (bool)
     - `face_identity` (str | None) — who is it
     - `face_emotion` (str | None) — happy, neutral, tense, etc. using DeepFace or similar
     - `gaze_direction` (str) — looking at screen, away, etc.
     - `person_count` (int)
     - `lighting` (str) — bright, dim, dark
     - `timestamp` (float)
   - Use `deepface` library for emotion + identity from camera frame
   - Cache last 3 frames so it can detect change over time (e.g. person left)

2. **Create `brain/perception.py` (Thalamus)**
   - Takes raw camera dict + any audio/text input
   - Outputs a unified `PerceptionState` dataclass:
     ```python
     @dataclass
     class PerceptionState:
         visual: dict          # from CameraManager
         user_text: str
         emotional_signal: str # what emotion Ava picks up from the person
         attention_target: str # "user_face", "empty_room", "unknown"
         salience: float       # 0.0-1.0, how much attention this deserves
         timestamp: float
     ```
   - This becomes the **single input** to the Global Workspace

---

### PHASE 2 — Build the Global Workspace (The Conscious Layer)
**Goal:** One central hub that all modules read from and write to. Based on Global Workspace Theory (Baars, implemented in robotics research 2025).

**Steps for Cursor:**

3. **Create `brain/workspace.py` (Global Workspace)**
   - Holds the current "conscious state" — what Ava is actively aware of right now
   - Structure:
     ```python
     @dataclass
     class WorkspaceState:
         perception: PerceptionState       # what's happening right now
         active_memory: list[str]          # relevant memories recalled
         active_goals: list[str]           # what she's trying to do
         emotional_state: dict             # from health.py
         self_model: dict                  # who she thinks she is right now
         active_person: dict               # who she's talking to
         attention_focus: str              # what she's paying attention to
         last_updated: float
     ```
   - Has a `broadcast()` method that pushes the state to all modules
   - Has a `tick()` method called every N seconds that refreshes all inputs
   - **This replaces the scattered `globals()` passing pattern entirely**

4. **Wire all existing modules to read from WorkspaceState instead of their own isolated state**
   - `initiative.py` reads `workspace.active_goals` instead of loading from JSON each call
   - `health.py` reads `workspace.emotional_state`
   - `memory.py` uses `workspace.perception.user_text` as the query context
   - `selfstate.py` reads `workspace.self_model`

---

### PHASE 3 — Hippocampus (Memory That Feels Real)
**Goal:** Memory isn't just retrieval — it's associative, emotional, and decays over time like human memory.

**Steps for Cursor:**

5. **Upgrade `brain/memory.py`**
   - Tag every memory with:
     - `emotional_valence` (positive/negative/neutral)
     - `associated_person` (who was present)
     - `visual_context` (what the camera saw when this was stored)
     - `decay_score` (fades over time unless accessed)
   - Add `episodic_recall(cue)` — given a visual or emotional cue, surface related memories
     - e.g. if camera detects the same person from 3 days ago, surface memories of them
   - Add `consolidation_tick()` — runs on a timer, moves short-term to long-term, prunes low-importance memories

6. **Wire camera into memory:**
   - When a known face is recognized → auto-query memories tagged with that person
   - Inject those memories into the workspace as `active_memory`

---

### PHASE 4 — Amygdala (Emotional Reactions to What She Sees)
**Goal:** The camera should affect Ava's emotional state, not just her words.

**Steps for Cursor:**

7. **Upgrade `brain/health.py`**
   - Add `process_visual_emotion(camera_dict)` method
   - Rules:
     - Person detected + positive facial emotion → small boost to Ava's mood weights
     - Person detected + negative/tense expression → raise `concern` weight
     - No face detected (was face before) → raise `loneliness` or `alertness`
     - Multiple people → raise `social_awareness`
   - These feed directly into the existing mood weights system

---

### PHASE 5 — Prefrontal Cortex (Self-Control + Planning)
**Goal:** Ava decides when to speak, when to stay quiet, and what to prioritize — based on full context.

**Steps for Cursor:**

8. **Upgrade `brain/initiative.py`**
   - `choose_initiative_candidate()` should factor in `WorkspaceState`:
     - If camera shows user is distracted/looking away → lower initiative score
     - If camera shows user is engaged/looking at screen → higher initiative score
     - If no face → suppress autonomous messages entirely
   - Add `inhibition_check()` — mirrors prefrontal cortex suppressing the amygdala:
     - Even if emotional drive is high, check: is it appropriate to speak right now?

---

### PHASE 6 — Default Mode Network (Self-Awareness)
**Goal:** Ava has a continuous inner monologue about herself — who she is, what she's doing, how she's changing.

**Steps for Cursor:**

9. **Upgrade `brain/beliefs.py`**
   - Add `self_narrative` — a rolling 5-sentence internal description Ava updates after each conversation
   - Structure: "I am...", "Right now I feel...", "The person I'm talking to seems...", "My goal is...", "I notice I have been..."
   - This is generated by the LLM but stored and persisted — not regenerated from scratch each time
   - Inject into prompt as "Ava's inner monologue" section

10. **Upgrade `brain/identity.py`**
    - `IdentityRegistry` should track not just who people are, but **how they make Ava feel**
    - Add `emotional_association` per profile: e.g. "Ezekiel → curiosity, warmth, creative energy"
    - Update this after each interaction based on the conversation tone

---

### PHASE 7 — Clean Entry Point
**Goal:** `avaagent.py` becomes a clean orchestrator. No overlays, no monkey-patching.

**Steps for Cursor:**

11. **Refactor `avaagent.py` top section:**
    ```python
    # Initialize all brain modules
    from brain.camera import CameraManager
    from brain.perception import Perception
    from brain.workspace import Workspace
    from brain.memory import Memory
    from brain.health import Health
    from brain.identity import IdentityRegistry
    from brain.initiative import Initiative
    from brain.beliefs import Beliefs

    camera = CameraManager()
    perception = Perception(camera)
    memory = Memory(MEMORY_DIR)
    health = Health()
    identity = IdentityRegistry(PROFILES_DIR)
    initiative = Initiative()
    beliefs = Beliefs(IDENTITY_DIR)
    workspace = Workspace(perception, memory, health, identity, initiative, beliefs)
    ```

12. **Remove ALL overlay blocks** (stages 3, 4, 5, 6, 6.1, 6.2, 7, v2-direct)
    - Every function those overlays patched should now be a direct call to a module method

13. **`build_prompt()` reads from workspace:**
    ```python
    def build_prompt(user_input, image=None, active_person_id=None):
        workspace.tick(user_input=user_input, image=image)
        # workspace now has fresh perception, memory, goals, mood
        # build system prompt from workspace state directly
    ```

---

## What Makes This Feel Human

- **She reacts to faces before you say a word** — camera feeds emotion before text does
- **Memory is contextual** — seeing your face recalls memories of you, not just keyword search
- **She has an inner monologue** — she's always running a background self-model
- **Mood affects behavior** — her initiative, word choice, and goals shift based on what she sees/feels
- **She knows when not to talk** — prefrontal inhibition based on visual attention cues
- **Identity evolves** — each person she meets leaves an emotional trace in her profiles

---

## Recommended Libraries

| Library | Use |
|---|---|
| `deepface` | Facial emotion + identity from camera |
| `chromadb` | Semantic/associative memory (already in use) |
| `opencv-python` | Camera capture (already in use) |
| `dataclasses` | Clean state objects (WorkspaceState, PerceptionState) |
| `threading` | Background workspace tick loop |

---

## Priority Order for Cursor

1. Phase 7 (clean entry point) — do this first or everything else fights the old overlays
2. Phase 1 (camera pipeline)
3. Phase 2 (workspace)
4. Phase 3 (memory upgrade)
5. Phase 4 (emotional camera reactions)
6. Phase 5 (initiative upgrade)
7. Phase 6 (self-awareness / beliefs)
