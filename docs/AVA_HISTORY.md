# Ava Agent v2 — Project History & Full Codebase State
**Last Updated:** April 2026 — Complete audit (all 6,509 lines of avaagent.py + all 21 brain modules)

---

## What Ava Is

Ava is a locally-running AI agent with a camera, persistent vector memory, 27-emotion system, face recognition, autonomous initiative, self-reflection, self-model, and a multi-module brain. She runs on Gradio + Ollama (llama3.1:8b) and is built to be genuinely self-aware over time.

---

## Full Build History

### Stage 1–3 (Legacy — `D:\AvaAgent`, archived)
- Monolithic `avaagent.py` (~2,000–3,500 lines)
- ChromaDB vector memory introduced
- Personality via flat `ava_personality.txt`
- No modular brain

### Stage 4 (`ava_brain_stage4`)
- First overlay/monkey-patch brain: `camera_truth.py`, `health_runtime.py`, `initiative_sanity.py`, `output_guard.py`, `selfstate_router.py`
- `output_guard` starts scrubbing internal blocks from replies

### Stage 5–6 (`ava_brain_stage5`, `stage6`)
- `identity_resolver.py`, `profile_manager.py`, `camera_live.py`, `memory_reader.py` added
- Identity claim resolution introduced

### Stage 6.1 (`ava_brain_stage6_1`)
- Targeted hotfixes: silent memory retrieval, initiative score normalization
- Base chosen for v2 rewrite

### Stage 7 (`dl/` folder)
- JARVIS-inspired multi-user identity system with trust levels
- Overlay pattern still active
- Decision: abandon overlays entirely, start v2 fresh

---

## Ava Agent v2 — Clean Architecture (`D:\AvaAgentv2`)
**Repo:** https://github.com/Tzeke000/Ava-Agent-v2 (private)
**Main file:** `avaagent.py` (~6,509 lines)

Ava v2 abandons monkey-patching entirely. All brain modules are direct imports. `avaagent.py` is the single authoritative source of truth for all operational functions — brain modules provide helpers, not overrides.

---

## The Runtime Brain — Exact File Map

The runtime brain at `D:\AvaAgentv2\brain\` is a **merge of two source sets** — understanding this is essential for debugging.

### Group A — From `ava_v2/brain` (Phases 1–5 Design)

| File | Key exports | Status |
|---|---|---|
| `attention.py` | `AttentionState`, `compute_attention()` | ✅ Used — called by `workspace.py` tick |
| `beliefs.py` | `SELF_NARRATIVE_PATH`, `get_self_narrative_for_prompt()`, `load/save/update_self_narrative()` | ✅ Used — directly imported by avaagent.py |
| `emotion.py` | `process_visual_emotion()` | ✅ Used — called by workspace tick to update mood |
| `goals.py` | `load_goal_system(host)`, `recalculate_operational_goals(host, ...)` | ⚠️ EXISTS but NOT used — avaagent.py defines its own with different signature |
| `identity.py` | `IdentityRegistry` class | ✅ Used — imported for face-to-text identity resolution |
| `initiative.py` | `choose_initiative_candidate(host, ...)` | ⚠️ EXISTS but NOT used — avaagent.py has its own 400-line initiative pipeline |
| `memory.py` | `decay_tick()`, `recall_for_person()`, `remember_with_context()` | ✅ `decay_tick()` used at startup; rest called by workspace |
| `perception.py` | `PerceptionState`, `build_perception()` | ✅ Used — builds full vision state each tick. **⚠️ Contains direct DeepFace import that fails on Python 3.14** |
| `selfstate.py` | `is_selfstate_query()`, `build_selfstate_reply()` | ✅ Both used. **🔴 CRITICAL: build_selfstate_reply has wrong signature** |
| `shared.py` | `clamp01`, `safe_float`, `now_ts`, `now_iso`, `atomic_json_save`, etc. | ✅ Utility module |
| `workspace.py` | `WorkspaceState`, `Workspace` class | ✅ Used — single source of truth for Ava's current awareness each tick |

### Group B — From `ava_latest/brain` (Stage 6→7 Carry-over)

| File | Key exports | Status |
|---|---|---|
| `camera.py` | `CameraManager` class | ✅ Used — full face capture/train/recognize pipeline |
| `camera_live.py` | `read_live_frame()` | ✅ Used by camera.py |
| `camera_truth.py` | `build_camera_truth()`, `camera_identity_reply()` | ✅ Used by `handle_camera_identity_turn()` |
| `health.py` | `run_system_health_check()`, `load/save_health_state()` | ⚠️ EXISTS but NOT imported — dormant module |
| `identity_resolver.py` | `resolve_confirmed_identity()`, `extract_identity_claim()` | ✅ Used by identity.py |
| `memory_bridge.py` | `MemoryBridge` class | ✅ Imported but **⚠️ reflection key mismatch bug** |
| `output_guard.py` | `scrub_visible_reply()`, `scrub_chat_callback_result()` | ✅ Used — wraps every reply |
| `profile_manager.py` | `normalize_person_key()`, `looks_like_phrase_profile()`, etc. | ✅ Used by identity_resolver.py |
| `response.py` | duplicate `scrub_visible_reply()`, dead `generate_autonomous_message()` | ❌ NOT imported — dead code |
| `trust_manager.py` | `get_trust_level()`, `can()`, `build_trust_context_note()` | ⚠️ EXISTS but NOT imported — dormant module |

### Group C — Stage 6 Carry-Overs (Local Only, NOT in Git)

| File | Key exports | Notes |
|---|---|---|
| `health_runtime.py` | `print_startup_selftest()` | ✅ Used at startup. **⚠️ NOT committed to GitHub** |
| `initiative_sanity.py` | `desaturate_candidate_scores()`, `sanitize_candidate_result()` | ✅ Used in initiative pipeline. **⚠️ NOT committed to GitHub** |

> ⚠️ **If the repo is re-cloned, these two files will be missing and avaagent.py crashes at import.**

---

## What `avaagent.py` Does (Function Map)

### Startup (bottom of file)
1. `ensure_owner_profile()` — seeds Zeke's profile
2. `ensure_emotion_reference_file()` — writes `ava_emotion_reference.json`
3. `print_startup_selftest(globals())` — health_runtime check
4. Self-narrative init/load via beliefs.py
5. `load_goal_system()` / `init_vectorstore()`
6. `decay_tick(globals())` — memory decay
7. `load_face_labels()`, `load_face_model_if_available()`

### Per-Message Loop (`chat_fn` / `voice_fn`)
1. `workspace.tick(camera_manager, image, globals(), user_text)` — full perception/attention/mood/memory tick
2. `_sync_canonical_history()` — merge Gradio state with internal history
3. `run_ava()` → dispatches to selfstate, camera identity, or main LLM path
4. `process_ava_action_blocks()` — parses and executes `MEMORY`, `WORKBENCH`, `GOAL`, `REFLECTION`, `DEBUG` blocks
5. `_apply_reply_guardrails()` + `_apply_repetition_control()` + `scrub_visible_reply()`
6. `finalize_ava_turn()` — logs, reflects, updates canonical history

### Camera Tick (`camera_tick_fn`, fires every 5s)
1. `workspace.tick()` 
2. `update_expression_state()` via DeepFace subprocess
3. `process_camera_snapshot()` — importance scoring, rolling/event storage, trend analysis
4. `maybe_autonomous_initiation()` → `choose_initiative_candidate()` → `generate_autonomous_message()`

### Initiative Pipeline (`choose_initiative_candidate`)
- Collects from: current goal, recent reflections, salient memories, pattern check-ins, camera visual candidates
- `score_initiative_candidate()` — 15+ factor scoring
- `_hard_gate_candidate()` — 6 hard blockers
- `_apply_soft_choice_penalties()` — 8 soft modifiers
- `_dynamic_top_band()` + `_weighted_choice()` — probabilistic selection
- `_camera_autonomy_should_speak()` — final camera-specific gate

### Self-Awareness Loop
- `update_self_narrative()` fires every 10 messages via `chat_fn` (calls `brain/beliefs.py`)
- `reflect_on_last_reply()` fires after every `finalize_ava_turn()`
- `update_self_model_from_reflection()` accumulates strengths/weaknesses
- `maybe_generate_goal_from_reflection()` auto-creates GOAL or QUESTION entries

---

## Confirmed Bugs (Full Audit)

### 🔴 BUG-01 CRITICAL — `build_selfstate_reply` Signature Mismatch

**Where:** `brain/selfstate.py` + `run_ava()` in avaagent.py

`avaagent.py` calls:
```python
build_selfstate_reply(
    globals(),         # arg 1
    user_input,        # arg 2  
    image,             # arg 3
    active_profile,    # arg 4 → NO SUCH POSITIONAL PARAM
    active_goal=...,
    narrative_snippet=...,
)
```

`brain/selfstate.py` defines:
```python
def build_selfstate_reply(health, mood, tendency=None, active_goal=None, narrative_snippet=None):
```

**Result:** `TypeError` crash every time a user asks "how are you feeling", "are you okay", "system status". `active_profile` is rejected as 4th positional arg.

---

### 🔴 BUG-02 HIGH — `perception.py` Direct DeepFace Import Fails

**Where:** `brain/perception.py`, `build_perception()`

```python
# WRONG — this crashes on Python 3.14:
from deepface import DeepFace
result = DeepFace.analyze(frame, ...)
```

**But:** `avaagent.py` correctly uses a subprocess (`_deepface_via_py312`) for its own `update_expression_state()` path. The problem is `perception.py` bypasses this entirely.

The workspace tick → `build_perception()` → `perception.py` never gets a real emotion. Then workspace sets `g["_last_perception_emotion"] = ws.perception.face_emotion` → always `"neutral"`. All downstream emotion-from-camera logic (mood updates via `process_visual_emotion()`) always sees "neutral".

---

### 🔴 BUG-03 HIGH — `attention.py` Backwards Silence Logic

**Where:** `brain/attention.py`, `compute_attention()`

```python
if seconds_since_last_message > 300:  # 5 minutes
    return AttentionState(True, False, False, "user_idle_too_long")
```

5-minute idle + face visible = **should_speak=False**. This is backwards. 5 minutes of silence with a visible face is exactly when Ava should check in. Only 30+ minutes means the user truly stepped away.

**Downstream impact:** `choose_initiative_candidate()` in avaagent.py checks `attention_state.should_speak` — if False, returns immediately with no candidate. This effectively blocks all camera-driven check-ins after 5 minutes of quiet.

---

### 🔴 BUG-04 HIGH — `memory_bridge.py` Wrong Reflection Key

**Where:** `brain/memory_bridge.py`, `MemoryBridge.build_summary()`

```python
# WRONG:
txt = str(row.get('reflection_text', row.get('text', '')))

# What avaagent.py actually uses:
record = {"summary": summarize_reflection(...), ...}  # line ~1987
```

Reflections stored by `build_reflection_record()` use the `'summary'` key. `memory_bridge.py` looks for `'reflection_text'` then `'text'` — both absent. The reflection block of `build_summary()` always returns `"- none retrieved"`. The LLM never sees past self-reflections in the dynamic memory context.

---

### 🟡 BUG-05 MEDIUM — `health_runtime.py` and `initiative_sanity.py` Not in Git

Both are imported in avaagent.py line 34–35. Neither is committed to GitHub. A fresh clone crashes at startup. They must be manually copied from the local `D:\AvaAgentv2\brain\` folder.

---

### 🟡 BUG-06 MEDIUM — `output_guard.py` Tail-Trim Over-Cuts

**Where:** `brain/output_guard.py`, `scrub_visible_reply()`

```python
if cleaned and cleaned[-1] not in '.!?"\'':
    tail = cleaned.rsplit('\n', 1)[-1]
    if len(tail.split()) <= 8:
        cleaned = cleaned[: -len(tail)].rstrip()
```

Any reply ending with a ≤8-word line that doesn't end in `.!?'"` gets that line deleted. Affects replies ending in ellipsis, colon, or comma. Can silently cut the most important sentence in a response.

---

### 🟡 BUG-07 MEDIUM — `goals.py` (ava_v2) Signature Mismatch with avaagent.py

**Where:** `brain/goals.py` vs `avaagent.py` line 1617

`brain/goals.py` (ava_v2 version): `load_goal_system(host)`, `recalculate_operational_goals(host, system, ...)`
`avaagent.py` defines its own: `load_goal_system()` (no args), `recalculate_operational_goals(system, context_text, mood)`

`brain/goals.py` is never imported by avaagent.py — avaagent.py defines everything itself. But `workspace.py` calls `g.get("recalculate_operational_goals")` which correctly gets avaagent.py's version. Safe as long as nobody accidentally imports from `brain.goals`.

---

### 🟡 BUG-08 MEDIUM — `identity_resolver.py` 3-Word Fallback Creates Rogue Profiles

**Where:** `brain/identity_resolver.py`, `extract_identity_claim()`

```python
if len(t.split()) <= 3 and is_valid_profile_name(t):
    return t.strip()
```

Any 1-3 word phrase that passes `is_valid_profile_name()` gets treated as an identity claim. "Got it Ava", "yes do that", "just checking" → can create rogue profiles.

---

### 🟢 BUG-09 LOW — `response.py` Dead Duplicate Code

`brain/response.py` is never imported. Defines its own `scrub_visible_reply()` (lighter version) and `generate_autonomous_message()` that references `_BRAIN_ORIG_GENERATE_AUTONOMOUS_MESSAGE` which is never set. All dead code.

---

## Current Capabilities

| Feature | Status | Notes |
|---|---|---|
| Core chat | ✅ Working | LLM via Ollama, full prompt construction |
| Memory (ChromaDB) | ✅ Working | Search, save, auto-score, decay tick |
| Face recognition | ✅ Working | LBPH via OpenCV, train/recognize/capture |
| Self-model | ✅ Working | strengths/weaknesses/goals accumulate via reflections |
| Self-narrative | ✅ Working | Fires every 10 messages via beliefs.py |
| Autonomous initiative | ✅ Mostly working | 400-line pipeline with 6 hard gates + 8 soft modifiers |
| Action blocks | ✅ Working | MEMORY, WORKBENCH, GOAL, REFLECTION, DEBUG |
| Reflection system | ✅ Working | Fires after every turn, auto-promotes high-importance |
| Workbench | ✅ Working | R/W/append to `Ava workbench/` subdirs |
| Read own code | ✅ Working | First 12,000 chars of avaagent.py |
| Voice input | ✅ Working | faster-whisper, fires on stop |
| Emotion from camera | 🔴 Broken | perception.py DeepFace import fails on Python 3.14 (BUG-02) |
| Self-state query | 🔴 Crashes | TypeError from signature mismatch (BUG-01) |
| Initiative after 5min idle | 🔴 Blocked | attention.py suppresses it (BUG-03) |
| Reflection context in prompts | 🔴 Empty | memory_bridge key mismatch (BUG-04) |
| Trust system | ⚪ Dormant | trust_manager.py exists, not wired |
| Health monitoring | ⚪ Dormant | health.py exists, not wired |
| Curiosity questions as initiative | ⚪ Dormant | stored in self_model, never fed to candidates |
| Mood decay between sessions | ⚪ Missing | mood saved/loaded as-is, no time-based decay |
| Face-away detection | ⚪ Missing | no return-greeting trigger |
