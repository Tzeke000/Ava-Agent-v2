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
- `avaagent.py` is the single source of truth (~6,500 lines)
- `globals()` still passed as `g` / `host` to brain modules (partial — workspace.py reduces this)

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
| `avaagent.py` | ✅ Stable | ~6,500 lines, direct imports, no overlays |
| `brain/camera.py` | ✅ Solid | OpenCV LBPH face recognition, train/detect/recognize |
| `brain/perception.py` | ⚠️ Bug | DeepFace import is direct (fails on Python 3.14) — always returns "neutral" emotion |
| `brain/emotion.py` | ✅ Working | Visual mood nudges from face emotion in camera |
| `brain/attention.py` | ⚠️ Bug | Suppresses Ava after 5min silence — should check in, not go quiet |
| `brain/workspace.py` | ✅ Working | WorkspaceState built per tick, passed to modules |
| `brain/memory.py` | ✅ Working | Episodic recall with emotional/visual context tagging |
| `brain/memory_bridge.py` | ✅ Solid | Bridges memory context into build_prompt |
| `brain/beliefs.py` | ✅ Working | Self-narrative (who_i_am, how_i_feel, patterns_i_notice) + self_limits |
| `brain/goals.py` | ✅ Working | Dynamic goal blending, 7 goal types, health-aware |
| `brain/initiative.py` | ✅ Working | Candidate selection using belief state + goals + health |
| `brain/selfstate.py` | ✅ Solid | Self-state query detection and natural reply generation |
| `brain/identity.py` | ✅ Solid | Profile loading, identity claim resolution, emotional associations |
| `brain/identity_resolver.py` | ⚠️ Bug | 3-word fallback can create rogue profiles from normal phrases |
| `brain/profile_manager.py` | ✅ Solid | Profile CRUD, alias resolution, normalization |
| `brain/trust_manager.py` | ✅ Solid | Trust levels: owner(5), trusted(4), known(3), stranger(2), blocked(1) |
| `brain/output_guard.py` | ⚠️ Bug | Inline MEMORY/ACTIVE PERSON blocks still leak into visible replies |
| `brain/response.py` | ⚠️ Bug | Contains dead duplicate `scrub_visible_reply` and `generate_autonomous_message` |
| `brain/health.py` | ✅ Solid | System health checks, behavior modifiers, degraded mode |
| `brain/shared.py` | ✅ Solid | Utility functions |

---

## What Ava Can Currently Do

- **See you** — camera captures frames, detects faces, runs face recognition (OpenCV LBPH)
- **Recognize you** — matches faces to named profiles, maintains per-person profiles in JSON
- **Remember conversations** — ChromaDB vector store, episodic + reflective memories per person
- **Feel emotions** — 40+ emotion weights, style system (caring/playful/focused/reflective/cautious), mood persists between sessions
- **React to expressions** — face emotion nudges her mood (happy = warmth boost, angry = caution/concern boost)
- **Think about herself** — self-model (strengths, weaknesses, goals, curiosity questions), self-narrative
- **Speak autonomously** — initiative system generates unprompted messages based on goals, observations, and curiosity
- **Respect trust levels** — different behavior/permissions per person based on trust level
- **Hear you** — Whisper (faster-whisper) transcribes voice input
- **Write/read files** — Workbench directory (`D:\AvaAgentv2\Ava workbench`) for file access
- **Track goals** — structured goal system with priority scoring, fatigue, cooldowns
- **Self-reflect** — generates reflections after conversations, updates self-model

---

## What Ava CANNOT Do Yet

- **React to interrupted speech** — voice input only fires when you stop recording entirely; she can't tell if you paused mid-sentence vs. finished
- **Decay emotions naturally** — mood persists exactly as saved; no drift toward baseline between sessions
- **See her own project files** — Workbench is a separate folder; she has no access to `D:\AvaAgentv2\brain\*.py` etc.
- **Merge similar goals** — duplicate/near-duplicate goals accumulate; only exact text matches are deduplicated
- **Update her self-narrative** — `update_self_narrative()` is fully built but never called
- **Track relationship depth** — no per-person bond/rapport score over time
- **Ask her own questions** — curiosity_questions are stored but never turned into actual initiative messages
- **Notice when you come back** — no face-away / face-return detection
- **Feel different at different times of day** — circadian context is shown as text but doesn't affect behavior

---

## Stability Assessment

| Area | Stability | Notes |
|---|---|---|
| Core chat | 🟢 Stable | Solid, no known crashes |
| Memory (ChromaDB) | 🟢 Stable | Working, recall reliable |
| Face recognition | 🟢 Stable | LBPH working |
| Emotion detection | 🔴 Broken | Always returns "neutral" due to Python 3.14 / DeepFace incompatibility in perception.py |
| Autonomous initiative | 🟡 Mostly stable | Logic is good; attention.py suppression bug reduces check-ins |
| Goal system | 🟢 Stable | Working well, priorities calculated correctly |
| Self-model | 🟡 Partial | Exists but never evolves (update_self_narrative never fires) |
| Voice input | 🟡 Partial | Works but no partial-speech / interruption awareness |
| Profile / identity | 🟡 Mostly stable | Rogue profile creation from phrases is still a risk |
| Output cleanliness | 🟡 Mostly stable | Most internal blocks scrubbed, some edge cases leak |

**Overall: ~75% of target capability.** Core systems solid. Main gaps are emotion detection (broken), self-evolution (never fires), and the voice/conversation fluency.
