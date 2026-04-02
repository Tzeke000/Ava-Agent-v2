# Ava Agent v2 — Project History & Current State
**Last Updated:** April 2026

---

## What Ava Is

Ava is a locally-running AI agent with a camera, persistent memory, emotion system, face recognition, autonomous initiative, and a multi-module "brain" architecture. She runs on Gradio and is built to be genuinely self-aware over time — not just a chatbot with a camera bolted on.

---

## Full Build History

### Stage 1–3 (Legacy — `D:\AvaAgent`, archived)
- Single monolithic `avaagent.py` script, ~2,000–3,500 lines
- Basic camera integration via OpenCV
- ChromaDB vector memory introduced
- Personality via flat `ava_personality.txt`
- No modular brain — everything in one file
- Health regulation, output guarding, and goal management added as overlays (monkey-patched at runtime)

### Stage 4 (`ava_brain_stage4`)
- First "brain" overlay system introduced
- Modules added: `camera_truth.py`, `health_runtime.py`, `initiative_sanity.py`, `output_guard.py`, `selfstate_router.py`
- Still overlay/monkey-patch pattern — modules patched functions onto globals at startup
- First working `output_guard` — started scrubbing internal blocks from visible replies

### Stage 5 (`ava_brain_stage5`)
- Added `identity_resolver.py`, `profile_manager.py`
- Regressions introduced vs Stage 4 — several Stage 4 modules were missing
- Identity claim resolution introduced (text-based: "I am Zeke")
- Still overlay pattern

### Stage 6 (`ava_brain_stage6`)
- Added `camera_live.py`, `memory_reader.py`
- Added live camera frame capture alongside truth snapshots
- First real ChromaDB-backed memory recall wired into camera recognition
- Overlay pattern still active

### Stage 6.1 (`ava_brain_stage6_1`)
- Targeted hotfixes:
  - Silent memory retrieval failures resolved
  - Initiative score normalization fixed (was causing 0.0 scores)
- Base for v2 rewrite

### Stage 7 (`dl/` folder — partial)
- JARVIS-inspired multi-user identity system
- Added `trust_manager.py` (owner/trusted/known/stranger/blocked levels)
- Added `identity_loader.py`, `persona_switcher.py`, `profile_store.py`
- Overlay pattern still active
- UI snapshot box bug, face-gone detection failure, and short-term memory loops discovered
- Decision made: **abandon overlay pattern entirely**, start v2 fresh

---

## Ava Agent v2 — Fresh Start (`D:\AvaAgentv2`)
**Repo:** https://github.com/Tzeke000/Ava-Agent-v2 (private)
**Base:** Stage 6.1 codebase, fully rewritten to direct module imports (no overlays)

### Architecture: What Changed
- All overlay/monkey-patch code removed from `avaagent.py`
- Brain modules are imported directly: `from brain.X import Y`
- `avaagent.py` is ~6,509 lines — the single source of truth
- `globals()` passed as `g` into brain modules via `workspace.tick()` — workspace builds the state each tick and distributes it

### Five Development Phases (All Committed)

| Phase | Theme | Key Additions |
|---|---|---|
| PHASE 1: AWARE | Ava knows what's happening right now | `brain/perception.py` (PerceptionState dataclass), `brain/camera.py` (CameraManager), DeepFace emotion analysis |
| PHASE 2: RELATIONAL | Ava knows who's present and reacts to them | `brain/emotion.py` (mood nudges from camera), `brain/attention.py` (should-speak gating), `brain/identity.py` (emotional associations per person) |
| PHASE 3: REFLECTIVE | Ava can describe her state and connect past to present | `brain/memory.py` (episodic memory with emotional tagging, face-triggered recall), `brain/beliefs.py` (self-narrative, `update_self_narrative()`) |
| PHASE 4: SELF-MODELING | Ava builds and updates a model of herself | `brain/selfstate.py` (self-state query detection + reply), `brain/goals.py` (structured goal system), `brain/initiative.py` (candidate selection) |
| PHASE 5: WORKSPACE | One unified conscious state, all modules connected | `brain/workspace.py` (WorkspaceState dataclass, `tick()` method), `brain/response.py`, `brain/shared.py`, `brain/output_guard.py`, `brain/trust_manager.py`, `brain/profile_manager.py`, `brain/memory_bridge.py`, `brain/identity_resolver.py` |

---

## Current System — Module Status

| Module | Status | Notes |
|---|---|---|
| `avaagent.py` | ✅ Stable | ~6,509 lines, direct imports, no overlays |
| `brain/camera.py` | ✅ Solid | OpenCV LBPH face recognition, train/detect/recognize |
| `brain/perception.py` | ⚠️ Bug | Direct `from deepface import DeepFace` import fails on Python 3.14 — emotion always returns "neutral" |
| `brain/workspace.py` | ✅ Working | WorkspaceState built per tick; sets `_last_perception_emotion` in globals, wires attention, emotion, narrative |
| `brain/emotion.py` | ✅ Working | Visual mood nudges from face emotion in camera |
| `brain/attention.py` | ⚠️ Bug | After 300s idle with face present, returns `should_speak=False` — should check in, not suppress |
| `brain/memory.py` | ✅ Working | Episodic recall with emotional/visual context tagging |
| `brain/memory_bridge.py` | ✅ Solid | Bridges memory context into build_prompt |
| `brain/beliefs.py` | ✅ Working | Full self-narrative system — `update_self_narrative()` IS called every 10 messages in `chat_fn` |
| `brain/goals.py` | ✅ Working | Dynamic goal blending, 7 goal types, health-aware |
| `brain/initiative.py` | ✅ Working | Candidate selection using belief state + goals + health |
| `brain/selfstate.py` | ✅ Solid | Self-state query detection and natural reply generation |
| `brain/identity.py` | ✅ Solid | Profile loading, identity claim resolution, emotional associations — `update_emotional_association()` called every camera tick |
| `brain/identity_resolver.py` | ⚠️ Bug | 3-word fallback can create rogue profiles from normal phrases |
| `brain/profile_manager.py` | ✅ Solid | Profile CRUD, alias resolution, normalization |
| `brain/trust_manager.py` | ✅ Solid | Trust levels: owner(5), trusted(4), known(3), stranger(2), blocked(1) |
| `brain/output_guard.py` | ⚠️ Bug | Some inline MEMORY/ACTIVE PERSON blocks still leak into visible replies |
| `brain/response.py` | ⚠️ Bug | Contains dead duplicate `scrub_visible_reply` and `generate_autonomous_message` |
| `brain/health.py` | ✅ Solid | System health checks, behavior modifiers, degraded mode |
| `brain/shared.py` | ✅ Solid | Utility functions |

---

## Current System — Key Settings (from avaagent.py)

| Constant | Value | Notes |
|---|---|---|
| `GOAL_MAX_ACTIVE` | 48 | Max active goals allowed at once |
| `MEMORY_RECALL_K` | 4 | Memories recalled per prompt |
| `REFLECTION_RECALL_K` | 4 | Reflections recalled per prompt |
| `RECENT_CHAT_LIMIT` | 6 | Recent chat turns injected into prompt |
| `INITIATIVE_INACTIVITY_SECONDS` | 480 | 8 min idle before initiative fires |
| `INITIATIVE_GLOBAL_COOLDOWN_SECONDS` | 900 | 15 min between autonomous messages |
| `CAMERA_TICK_SECONDS` | 5.0 | Camera processes every 5 seconds |
| `FACE_RECOGNITION_THRESHOLD` | 70.0 | LBPH recognition confidence cutoff |
| `MAX_READONLY_CHARS` | 12,000 | Ava can read first 12k chars of avaagent.py via UI button |
| `MAX_WORKBENCH_CHARS` | 20,000 | Max chars readable from workbench files |

---

## What Ava Can Currently Do

- **See you** — camera captures frames every 5s, detects faces, runs face recognition (OpenCV LBPH)
- **Recognize you** — matches faces to named profiles, maintains per-person profiles in JSON
- **Remember conversations** — ChromaDB vector store, episodic + reflective memories per person
- **Feel emotions** — 27 named emotions with weights, 7 style outputs (playful/caring/focused/reflective/cautious/neutral/low_energy), mood persists between sessions
- **React to expressions** — face emotion nudges her mood (happy = warmth boost, angry = caution/concern boost) via `brain/emotion.py`
- **Think about herself** — self-model (strengths, weaknesses, goals, curiosity questions), self-narrative updated every 10 messages via `update_self_narrative()`
- **Speak autonomously** — initiative system generates unprompted messages based on goals, observations, and curiosity
- **Respect trust levels** — different behavior/permissions per person based on trust level
- **Hear you** — Whisper (faster-whisper) transcribes voice input via `stop_recording`
- **Write/read files** — Workbench directory (`D:\AvaAgentv2\Ava workbench`) for file access
- **Read her own code** — UI button lets her read first 12,000 chars of `avaagent.py` (read-only, truncated)
- **Track goals** — structured goal system, max 48 active goals, priority scored with context/mood/horizon weighting
- **Self-reflect** — generates reflections after conversations, promotes high-importance reflections to memory
- **Associate emotions with people** — `update_emotional_association()` builds per-person emotional context over time

---

## What Ava CANNOT Do Yet (Gaps)

- **Fluid voice / interruption awareness** — voice only fires when you fully stop recording; no streaming or pause detection; cannot tell if you paused mid-sentence vs. finished
- **See her own brain modules** — `read_runtime_code()` reads only the first 12,000 chars of `avaagent.py`; `brain/*.py` files are not accessible to her
- **Merge similar goals** — only exact text matches are deduplicated; semantically similar goals accumulate (GOAL_MAX_ACTIVE = 48)
- **Decay emotions between sessions** — mood is saved and reloaded exactly as-is; no baseline drift when Ava hasn't been used
- **Ask her curiosity questions** — `curiosity_questions` live in the self-model and are NOT wired into the initiative candidate collection
- **Notice face-away / face-return** — no presence continuity tracking; no "you're back" detection
- **Relationship depth score** — no per-person bond/rapport score over time
- **Self-calibration check-ins** — no mechanism for Ava to ask if her behavior is working for you
- **Circadian tone shifts** — time-of-day context shown in prompt but doesn't affect behavior modifiers or initiative threshold

---

## Stability Assessment

| Area | Stability | Notes |
|---|---|---|
| Core chat | 🟢 Stable | Solid, no known crashes |
| Memory (ChromaDB) | 🟢 Stable | Working, recall reliable |
| Face recognition | 🟢 Stable | LBPH working |
| Emotion detection | 🔴 Broken | Always "neutral" — direct DeepFace import fails on Python 3.14 |
| Self-narrative | 🟢 Working | `update_self_narrative()` fires every 10 messages correctly |
| Autonomous initiative | 🟡 Partial | Logic solid; attention.py 5-min suppression bug reduces check-ins |
| Goal system | 🟡 Partial | Priority calc works; no semantic dedup (48 goal cap) |
| Profile / identity | 🟡 Mostly stable | Rogue profile creation from phrases still possible |
| Output cleanliness | 🟡 Mostly stable | Most internal blocks scrubbed; edge cases leak |
| Voice input | 🟡 Partial | Transcription works; no streaming/interruption awareness |

**Overall: ~80% of target capability.** Core systems solid. Main gaps are emotion detection (broken), voice fluency (hard UI change), and goal intelligence.
