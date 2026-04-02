# Ava Agent v2 — Full Repository Audit
**Date:** April 2026  
**Repo:** `Tzeke000/Ava-Agent-v2` (private)  
**Primary agent file:** `avaagent.py` (6,919 lines)  
**Brain modules:** `brain/` (28 files)

---

## What This Repo Actually Is

This is a **clean v2 rewrite** of the Ava Agent. It is NOT the old overlay-stacking monolith. The old `v2_avaagent.py` (9,381 lines with 7 stacked overlays) is **not what runs** — it exists only locally on Ezekiel's machine. The file committed to GitHub (`avaagent.py`) is the real intended build.

### Key Differences from the Old Build

| Feature | Old (`v2_avaagent.py` locally) | **Current repo (`avaagent.py`)** |
|---|---|---|
| BASE_DIR | Hardcoded `D:\AvaAgent` (wrong path) | `Path(__file__).resolve().parent` — **always correct** |
| DeepFace | Direct import, fails on Python 3.14 | **subprocess via `py -3.12`** — works correctly |
| Overlay stacking | 7 overlays (v30–v36, Stages 3–7) in one file | **None** — all imports are direct |
| Architecture | Monolithic + monkey patching | **Direct imports from `brain/`** |
| Selfstate | Handled by 3 competing overlay wrappers | **Single clean dispatch in `run_ava()`** |
| `process_ava_action_blocks` | Drops `latest_user_input` in Stage 4 and 6 wrappers | **Passes it through correctly** |
| `GATE_DEBUG_LOGGING` | Hardcoded `True` (spams console) | **`False` by default, Ava can toggle** |
| Stage 7 (trust/persona/identity) | Wired via overlay | **NOT wired yet** |
| v30–v34 MetaController | Wired via overlay | **NOT ported** |
| Circadian tone shifts | Not present | **Present** (`get_circadian_modifiers()`) |
| Self-narrative layer | Not present | **Present** (`brain/beliefs.py`, `state/self_narrative.json`) |
| Session state tracking | Not present | **Present** (`SESSION_STATE_PATH`) |
| `Workspace` class | Not present | **Present** (`brain/workspace.py`) |
| `MemoryBridge` class | Not present | **Present** (`brain/memory_bridge.py`) |
| `return_greeting` initiative kind | Not present | **Present** |
| `self_calibration_check` initiative kind | Not present | **Present** with 5 calibration prompts |

---

## Directory Structure

```
Ava-Agent-v2/
├── avaagent.py              # Main agent — 6,919 lines — THE file to run
├── ava_personality.txt      # Loaded at runtime by load_personality()
├── ava_emotion_reference.json
├── ava_mood.json
├── requirements.txt
├── start.bat                # cd D:\AvaAgentv2 && python avaagent.py
├── chatlog.jsonl            # Full conversation history (live data)
├── fix_bom.py
├── fix_and_clean.bat
├── push_to_github.bat
│
├── brain/                   # 28 modular files — all direct imports
│   ├── __init__.py          # "Ava brain stage 6 package"
│   ├── attention.py         # AttentionState, compute_attention()
│   ├── beliefs.py           # Self-narrative system + SELF_LIMITS
│   ├── camera.py            # CameraManager class
│   ├── camera_live.py       # read_live_frame()
│   ├── camera_truth.py      # build_camera_truth(), camera_identity_reply()
│   ├── emotion.py           # process_visual_emotion() — mood nudges from camera
│   ├── goals.py             # Goal system helpers
│   ├── health.py            # run_system_health_check(), behavior modifiers
│   ├── health_runtime.py    # print_startup_selftest()
│   ├── identity.py          # IdentityRegistry class
│   ├── identity_loader.py   # Stage 7 — loads IDENTITY.md/SOUL.md/USER.md
│   ├── identity_resolver.py # resolve_confirmed_identity()
│   ├── initiative.py        # Initiative helpers
│   ├── initiative_sanity.py # desaturate_candidate_scores(), sanitize_candidate_result()
│   ├── memory.py            # decay_tick()
│   ├── memory_bridge.py     # MemoryBridge class
│   ├── memory_reader.py     # build_memory_reader_summary() — dynamic memory injection
│   ├── output_guard.py      # scrub_visible_reply(), scrub_chat_callback_result()
│   ├── perception.py        # PerceptionState dataclass, build_perception()
│   ├── persona_switcher.py  # Stage 7 — build_persona_block(), should_deflect()
│   ├── profile_manager.py   # normalize_person_key(), is_valid_profile_name(), etc.
│   ├── profile_store.py     # Stage 7 — get_or_create_profile(), trust-aware store
│   ├── response.py          # Response helpers
│   ├── selfstate.py         # is_selfstate_query(), build_selfstate_reply()
│   ├── selfstate_router.py  # Compatibility shim → re-exports from selfstate.py
│   ├── shared.py            # clamp01(), now_iso(), atomic_json_save(), etc.
│   ├── trust_manager.py     # Stage 7 — get_trust_level(), is_blocked(), can()
│   ├── vision.py            # analyze_face_emotion_detailed()
│   └── workspace.py         # Workspace class
│
├── config/
│   └── settings.json        # owner_person_id, aliases, protected profiles
│
├── docs/                    # This file and roadmap
├── faces/                   # Face samples: zeke/ (15 images), who_created_you/ (1 image)
├── memory/                  # ChromaDB + reflection_log.jsonl + self_model.json
├── profiles/                # Per-person JSON files
├── state/                   # Runtime state: mood, goals, camera, active_person, etc.
├── Ava workbench/           # Ava's writable file area (drafts, notes, etc.)
└── backup/                  # Auto-backup of avaagent.py and brain/ from last run
```

---

## `avaagent.py` Architecture

### Imports
The file uses **direct imports only** — no overlays, no monkey patching:
```python
from brain.camera import CameraManager
from brain.perception import build_perception
from brain.attention import compute_attention
from brain.emotion import process_visual_emotion
from brain.memory import decay_tick
from brain.workspace import Workspace
from brain.identity import IdentityRegistry
from brain.memory_bridge import MemoryBridge
from brain.output_guard import scrub_visible_reply, scrub_chat_callback_result
from brain.selfstate import is_selfstate_query, build_selfstate_reply
from brain.health_runtime import print_startup_selftest
from brain.initiative_sanity import desaturate_candidate_scores, sanitize_candidate_result
from brain.vision import analyze_face_emotion_detailed
from brain.beliefs import get_self_narrative_for_prompt, load_self_narrative, ...
```

**Stage 7 modules (`identity_loader.py`, `trust_manager.py`, `persona_switcher.py`, `profile_store.py`) are NOT imported or wired in `avaagent.py` yet.** They exist in `brain/` as complete, working modules ready to be connected.

### BASE_DIR
```python
BASE_DIR = Path(__file__).resolve().parent
```
Always correct — resolves to wherever `avaagent.py` lives (`D:\AvaAgentv2`).

### Key Module Instances
```python
camera_manager = CameraManager()
identity_registry = IdentityRegistry(PROFILES_DIR, settings=SETTINGS)
memory_bridge = MemoryBridge(MEMORY_DIR, settings=SETTINGS)
workspace = Workspace()
```

### New in This Build vs. Old

- **`Workspace` class** (`brain/workspace.py`) — wraps camera, perception, attention, emotion, memory into a single `ws = workspace.tick(camera_manager, image, globals(), user_input)` call that runs every tick and produces a `WorkspaceState` with `.perception`, `.self_narrative`, `.active_memory`, etc.
- **`MemoryBridge`** (`brain/memory_bridge.py`) — clean interface for building dynamic memory summaries without coupling to globals
- **`IdentityRegistry`** (`brain/identity.py`) — wraps `resolve_confirmed_identity` + `resolve_profile_key_from_text` in a class with `ensure_profile()` and `update_emotional_association()`
- **`get_circadian_modifiers()`** — returns `tone_hint` (e.g. "quiet and low-key" at night) injected into every prompt
- **`_load_self_narrative_snippet()`** — pulls from `brain/beliefs.py` self-narrative for self-state replies
- **`SESSION_STATE_PATH`** — tracks total message count, session start, last session end
- **`SELF_CALIBRATION_PROMPTS`** — 5 prompts for the new `self_calibration_check` initiative kind
- **`return_greeting`** initiative kind — fires when person returns to camera after absence
- **`self_calibration_check`** initiative kind — Ava periodically asks if she's being helpful the right way

### `run_ava()` Flow
```python
def run_ava(user_input, image=None, active_person_id=None):
    # 1. Selfstate shortcut (no LLM call needed)
    if is_selfstate_query(user_input):
        reply = scrub_visible_reply(build_selfstate_reply(globals(), user_input, image, profile,
                                    active_goal=..., narrative_snippet=...))
        return finalize_ava_turn(...)
    
    # 2. Camera identity shortcut
    if is_camera_identity_intent(user_input) or is_camera_visual_query(user_input):
        return handle_camera_identity_turn(...)

    # 3. Full LLM path
    messages, visual, active_profile = build_prompt(user_input, image, active_person_id)
    raw_reply = llm.invoke(messages).content
    ai_reply, actions = process_ava_action_blocks(raw_reply, person_id, latest_user_input=user_input)
    # apply guardrails, repetition control, internal leakage scrub
    ai_reply = scrub_visible_reply(ai_reply)
    return finalize_ava_turn(...)
```

### `build_prompt()` — What Goes Into Every LLM Call
1. `personality` (from `ava_personality.txt`)
2. `self_narrative_block` (from `brain/beliefs.py` — who Ava is, how she feels, patterns she notices, core limits)
3. `ACTIVE PERSON` block (profile summary + rapport hint)
4. `SELF MODEL` (identity statement, drives, goals, curiosity questions, behavior patterns)
5. `TIME` (date, time, weekday, circadian tone hint)
6. `INTERNAL STATE` (27-emotion blend, style scores, behavior modifiers)
7. `CURRENT GOAL EXPRESSION` (active operational goal with style guidance)
8. `CAMERA` (face status, recognition, expression, memory summary, recent events)
9. `RELEVANT MEMORIES` (top-k semantic search results)
10. `RECENT CHAT` (last 4 turns)
11. `RECALLED SELF REFLECTIONS` + `RECENT SELF REFLECTION SNAPSHOT`
12. `DYNAMIC SELF / MEMORY READER` (from `memory_bridge.build_summary()`)
13. `WORKBENCH INDEX`
14. `USER MESSAGE`

### `camera_tick_fn()` — Every 5 Seconds
1. `workspace.tick(camera_manager, image, globals(), "")` — runs full perception pipeline
2. `update_expression_state()` — DeepFace via Python 3.12 subprocess
3. `process_camera_snapshot()` — importance/trend/transition pipeline, rolling + event saves
4. `identity_registry.update_emotional_association()` — logs emotion to profile
5. `maybe_autonomous_initiation()` — checks if Ava should speak unprompted

---

## Brain Module Reference

### `brain/beliefs.py` — Self-Narrative System
New in v2. Stores a persistent `self_narrative.json` with:
- `who_i_am` — Ava's sense of herself
- `how_i_feel` — current emotional self-description
- `patterns_i_notice` — behavioral observations
- `self_limits` — hardcoded 5 rules that CANNOT be changed via `update_self_narrative()`

`update_self_narrative()` can be called at end of session — uses LLM to update `who_i_am`, `how_i_feel`, `patterns_i_notice`. Never touches `self_limits`.

`get_self_narrative_for_prompt()` returns a compact string injected into every prompt.

---

### `brain/workspace.py` — Workspace Orchestrator
Runs every tick. Produces a `WorkspaceState`:
- `.perception` — `PerceptionState` (face_detected, face_identity, face_emotion, recognized_text, frame)
- `.self_narrative` — string from beliefs system
- `.active_memory` — list of recalled memory strings

Workspace ticks drive the whole perceptual pipeline so `build_prompt()` doesn't need to manually call each component.

---

### `brain/memory_bridge.py` — Dynamic Memory Injection
`MemoryBridge.build_summary(globals(), user_input, active_profile)` — clean class interface that wraps `memory_reader.build_memory_reader_summary()`. Decouples the main agent from globals-based calls.

---

### `brain/identity.py` — IdentityRegistry Class
`IdentityRegistry(profiles_dir, settings)`:
- `resolve_text_claim(text, current_person_id)` — resolves who is claiming identity
- `ensure_profile(person_id, globals, source)` — creates/loads profile, sets active person
- `update_emotional_association(person_id, face_emotion, globals)` — rolling 10-emotion history + dominant emotion in profile JSON

---

### `brain/health.py` — Full Health System
`run_system_health_check(host, kind)` — checks camera, memory, mood, initiative, models.
Produces `behavior_modifiers`: `initiative_scale`, `confidence_scale`, `support_bias`, `silence_bias`, `tone_caution`.
Stores degraded mode: `none` / `cautious` / `low_initiative` / `support_only`.

**Not currently wired into `avaagent.py`'s runtime loop** — only `health_runtime.print_startup_selftest()` is called at startup. The full health check system exists but isn't applied to behavior modifiers yet.

---

### `brain/selfstate.py` — Self-State Replies
`is_selfstate_query(text)` — matches 7 patterns like "how are you feeling", "system status".
`build_selfstate_reply(g, user_input, image, active_profile, active_goal, narrative_snippet)` — builds a natural reply using current mood, face status, memory status, narrative.

**`brain/selfstate_router.py` is just a compatibility shim** that re-exports from `selfstate.py`. It exists because earlier code imported from `selfstate_router` — the router just forwards everything.

---

### `brain/emotion.py` — Visual Emotion → Mood
`process_visual_emotion(perception, current_mood)` — nudges Ava's relational mood keys (loneliness, engagement, warmth, care, concern, caution, support_drive) based on what the camera sees. Called every camera tick via `workspace.tick()`.

---

### `brain/attention.py` — Attention Gate
`compute_attention(perception, seconds_since_last_message, circadian_initiative_scale)` — decides if Ava should speak. Returns `AttentionState` with `should_speak` bool and `suppression_reason`. Applies circadian scaling — Ava is more patient at night.

---

### `brain/trust_manager.py` — Stage 7 (Built, Not Wired)
Trust level system (1=blocked, 2=stranger, 3=acquaintance, 4=trusted, 5=owner).
`get_trust_level(profile)`, `is_blocked(profile)`, `is_owner(profile)`, `can(profile, permission)`.
Permissions: `see_owner_schedule`, `use_computer`, `receive_private_info`, `ask_personal_questions`, `manage_profiles`.

**Complete and working. Not imported by `avaagent.py` yet.**

---

### `brain/persona_switcher.py` — Stage 7 (Built, Not Wired)
`build_persona_block(profile)` — builds tone instructions per trust level (5 different tone templates).
`should_deflect(profile, user_input)` — blocks schedule/location queries from low-trust users.
`get_blocked_reply()`, `get_deflect_reply(profile, user_input)`.

**Complete and working. Not imported by `avaagent.py` yet.**

---

### `brain/profile_store.py` — Stage 7 (Built, Not Wired)
`get_or_create_profile(person_id, name, trust_level, relationship)`.
`load_profile(person_id)`, `update_profile_notes(person_id, note)`, `touch_last_seen(person_id, topic)`.
`seed_default_profiles()` — ensures zeke (trust=5), shonda/mom (trust=4) exist on startup.

**Complete and working. Not imported by `avaagent.py` yet.**

---

### `brain/identity_loader.py` — Stage 7 (Built, Not Wired)
Loads `IDENTITY.md`, `SOUL.md`, `USER.md` from `D:/AvaAgent/ava_core/` (hardcoded path — needs to be fixed to be relative).
`load_ava_identity()` — returns all three files as a single system prompt block.
`process_identity_actions(reply_text)` — parses `IDENTITY action: update file=USER.md content=...` blocks from Ava's replies.
`append_to_user_file(fact)` — appends learned facts to `USER.md`.

**Complete and working. Not imported by `avaagent.py` yet.**
**Bug: `IDENTITY_DIR` is hardcoded to `D:/AvaAgent/ava_core/` — needs to be relative.**

---

## Runtime Data State

### Profiles in `profiles/`
| File | Person ID | Notes |
|---|---|---|
| `zeke.json` | `zeke` | Owner. Has 10-item emotion_history and dominant_emotion field. Last seen 2026-04-01 22:59 |
| `ezekiel.json` | `ezekiel` | **Rogue duplicate** — was created when Ava misidentified "ezekiel" as a separate person. `allowed_to_use_computer: false`. Should be merged into `zeke` |
| `do_you.json` | `do_you` | **Rogue profile** — created from phrase "Do you..." being treated as a person name. Should be deleted |
| `thats_correct_ava.json` | `thats_correct_ava` | **Rogue profile** — created from "That's correct Ava" being treated as a person name. Should be deleted |
| `who_created_you.json` | `who_created_you` | **Rogue profile** — created from "Who created you" being treated as a person name. Has a face sample! Should be deleted |

### Memory in `memory/`
- ChromaDB database at `memory/chroma.sqlite3` (8.7 MB — substantial real memory)
- Two ChromaDB collections (two UUID folders)
- `memory/self reflection/reflection_log.jsonl` — 368 KB of reflection records
- `memory/self reflection/self_model.json` — 13.9 KB self-model
- **Two `.tmp` files** (`self_model.json.7wfk1g__.tmp`, `self_model.json.mjr0vlog.tmp`) — leftover from atomic writes. Not harmful, but should be cleaned

### State files
- `state/active_person.json` — last active person was `zeke`, source: `camera_timer`, updated 2026-04-01 22:59
- `state/backup/goal_system_corrupted_2026-03-31.json` — a backup from a corruption event
- `state/camera/` — 12+ event JSON + JPG pairs from 2026-04-01 22:20–22:59

### `chatlog.jsonl`
19 KB of conversation history. Active sessions from April 1, 2026.

---

## Known Issues

### 🔴 BUG-01 — Rogue Profiles Are Being Created

**Active and ongoing.** The `infer_person_from_text()` function is extracting phrases like "do you", "that's correct ava", "who created you" as person identities. `brain/profile_manager.py`'s `is_valid_profile_name()` and `looks_like_phrase_profile()` exist specifically to block this — but they aren't being called in the `avaagent.py` identity inference path.

The Stage 6 overlay in `v2_avaagent.py` patched `infer_person_from_text` to call `looks_like_phrase_profile()`. That protection was never ported into `avaagent.py`.

**Fix:** In `avaagent.py`'s `infer_person_from_text()`, add:
```python
from brain.profile_manager import looks_like_phrase_profile, is_valid_profile_name

def infer_person_from_text(user_input, current_person_id):
    # ... existing inference logic ...
    if pid and pid != current_person_id:
        # Reject phrase-like person IDs
        if looks_like_phrase_profile(pid.replace('_', ' ')):
            return current_person_id, 'rejected_phrase_profile'
    return pid, source
```

---

### 🔴 BUG-02 — `brain/identity_loader.py` Has Hardcoded Wrong Path

**Line in identity_loader.py:**
```python
IDENTITY_DIR = Path("D:/AvaAgent/ava_core")
```

This points to the OLD v1 directory. The v2 repo lives at `D:\AvaAgentv2`. If Stage 7 is ever wired in, it will silently create/read identity files in the wrong place.

**Fix:**
```python
IDENTITY_DIR = Path(__file__).resolve().parent.parent / "ava_core"
```

---

### 🔴 BUG-03 — Stage 7 Modules Are Complete but Not Connected

`brain/trust_manager.py`, `brain/persona_switcher.py`, `brain/profile_store.py`, `brain/identity_loader.py` are all fully written and tested. But `avaagent.py` doesn't import or call any of them. Ava has no trust levels, no per-person tone variation, no identity file injection, and no `USER.md` auto-update from reflections.

This is the biggest missing feature — not a crash bug, but the most impactful capability gap.

---

### 🟡 BUG-04 — `brain/health.py` Not Wired to Behavior

`brain/health.py` produces `behavior_modifiers` (`initiative_scale`, `silence_bias`, etc.) and `degraded_mode`. But these are never applied in `avaagent.py`. The initiative system ignores health state — Ava initiates at full speed even when a subsystem is degraded.

**Fix:** After `run_system_health_check()` at startup, apply health modifiers to initiative scoring.

---

### 🟡 BUG-05 — `requirements.txt` Lists `deepface` and `tf-keras` as Direct Installs

```
deepface
tf-keras
```

These will fail on Python 3.14 (TensorFlow incompatibility). The runtime correctly uses `py -3.12` subprocess for DeepFace, but `requirements.txt` still lists it — running `pip install -r requirements.txt` will error out.

**Fix:**
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
Remove `deepface` and `tf-keras`. Install them separately into the Python 3.12 environment.

---

### 🟡 BUG-06 — Ezekiel Profile Is Separate From Zeke Profile

`profiles/ezekiel.json` exists as a different person from `profiles/zeke.json`. Ava sees these as two different people. When you say "my name is Ezekiel" or "it's Ezekiel", Ava sets `active_person = ezekiel` and loses all of Zeke's memories and context.

`config/settings.json` has `"aliases": {"zeke": ["ezekiel", "creator", "your creator"]}` — but `avaagent.py` doesn't load this config for alias resolution.

**Fix:** Either load `config/settings.json` aliases in `infer_person_from_text()`, or use `brain/profile_manager.py`'s `DEFAULT_ALIASES` dict (already has `zeke → [ezekiel, creator, your_creator]`).

---

### 🟢 BUG-07 — Leftover `.tmp` Files in Memory

`memory/self reflection/self_model.json.7wfk1g__.tmp` and `.mjr0vlog.tmp` are leftover from incomplete atomic writes. They're harmless but should be cleaned.

---

## What's Working Well

- **Clean architecture** — every import is direct, no hidden layers
- **BASE_DIR** — always resolves correctly via `Path(__file__).resolve().parent`
- **DeepFace subprocess** — correctly uses `py -3.12` for expression sensing
- **`brain/workspace.py`** — elegant unified perception pipeline
- **`brain/beliefs.py`** — self-narrative with protected `self_limits` is genuinely novel
- **Circadian modifiers** — `get_circadian_modifiers()` + tone hint in every prompt
- **`_apply_circadian_to_emotion_weights()`** — Ava's emotional state shifts by time of day
- **Self-calibration initiative kind** — Ava periodically checks if she's being helpful
- **Return greeting** — Ava notices when you come back to the camera
- **`identity_registry.update_emotional_association()`** — rolling emotion history per person
- **`scrub_visible_reply()`** called at the end of `run_ava()` — guaranteed no internal leakage
- **`latest_user_input` passed correctly through `process_ava_action_blocks()`**
- **`GATE_DEBUG_LOGGING = False` by default** — no console spam, Ava can toggle it
- **`session_state` tracking** — total message count survives restarts
- **ChromaDB** has substantial real memory (8.7 MB, active)
- **15 face samples** for Zeke in `faces/zeke/` — face recognizer has enough data
