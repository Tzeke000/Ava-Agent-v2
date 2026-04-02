# Ava Agent — Project History & Definitive Codebase State
**Last Updated:** April 2026 — Full audit of v2_avaagent.py (9,381 lines) + all brain modules
**Primary file:** `v2_avaagent.py` — this is the real current build

---

## CRITICAL: There Are Three Different Files in This Repo

| File | Lines | What it is |
|---|---|---|
| `github_avaagent.py` | 6,509 | **Partially cleaned v2 rewrite** — no overlay stacking, uses subprocess for DeepFace, targets `D:\AvaAgentv2`. This is what was committed to GitHub and thought to be the latest |
| `v2_avaagent.py` | 9,381 | **The real full build** — monolithic file with ALL overlays still stacked (v30 through Stage 7). Targets `D:\AvaAgent` (original directory). Has direct DeepFace import |
| `avaagent_full.py` | 6,565 | Intermediate version, not the primary |

**The file you are actually running is `v2_avaagent.py`.** The GitHub repo has `github_avaagent.py` as the committed version which diverges significantly.

---

## Architecture: The Overlay Onion

`v2_avaagent.py` is NOT a clean rewrite. It is the original monolithic agent with **7 overlay layers** applied sequentially on top of the base code, all in the same file. Each layer captures the previous version of a function with `_orig_*`, then redefines it.

### Layer Stack (in order, bottom to top)

| Layer | Line Range | What It Adds |
|---|---|---|
| **Base** | 1 – 6,500 | Core agent: emotions, memory, camera, initiative, self-model, reflection, prompt building, UI |
| **v30** | 6,505 – 7,020 | State model (7 user states), conflict engine, outcome learning, distribution tracking |
| **v31** | 7,020 – 7,303 | MetaController adaptive regulation — adds meta_control dict to goal system |
| **v32** | 7,303 – 7,722 | Meta authority — persistent mode control (balanced/low_initiative/supportive/etc.), meta_state/meta_feedback tables |
| **v33** | 7,722 – 8,012 | Meta mode refinement — long-window feedback, mode confidence decay, `register_autonomous_message` now records meta outcomes |
| **v34** | 8,012 – 8,469 | META_MODE action block (Ava can define custom modes via ```META_MODE``` in replies), sanitized profiles, per-person feedback |
| **v35** | 8,469 – 8,582 | Stability fix — atomic `iso_to_ts`, guarded `load_self_model` / `load_goal_system` with recursion protection |
| **v36** | 8,582 – 8,667 | History normalization — `_set_canonical_history`, `_get_canonical_history`, `_sync_canonical_history`, `_merge_histories` |
| **Stage 3 overlay** | 8,667 – 8,785 | Wraps `chat_fn`, `generate_autonomous_message`, `camera_tick_fn` with `scrub_visible_reply`. Has its own `startup_health_banner`. Imports `brain.selfstate` |
| **Stage 4 overlay** | 8,789 – 8,890 | Re-wraps `run_ava`, `process_ava_action_blocks`, `chat_fn`, `voice_fn`, `detect_face`, `recognize_face`, `choose_initiative_candidate` using `brain.selfstate_router`, `brain.output_guard`, `brain.initiative_sanity`, `brain.camera_truth`, `brain.health_runtime` |
| **Stage 5 overlay** | 8,890 – 8,955 | Adds `brain.profile_manager`, `brain.identity_resolver`, `brain.camera_truth`, `brain.output_guard` to profile safety and identity claim resolution |
| **Stage 6 overlay** | 8,955 – 9,154 | Re-wraps `create_or_get_profile`, `infer_person_from_text`, `set_active_person`, `choose_initiative_candidate`, `process_ava_action_blocks`, `build_prompt` (adds dynamic memory reader), `run_ava` (adds live frame), `chat_fn`, `camera_tick_fn` (face-gone detection) |
| **Stage 6.1 overlay** | 9,154 – 9,201 | Re-wraps `choose_initiative_candidate` (pre-selection desaturation) and `build_prompt` (smarter memory reader injection) |
| **Stage 7 overlay** | 9,201 – 9,381 | Trust gate + persona system. Re-wraps `create_or_get_profile`, `build_prompt` (Ava identity block + trust note injected into system message), `run_ava` (blocked/deflect check), `reflect_on_last_reply` (auto-save learned facts + USER.md update), `infer_person_from_text` (auto-create stranger profiles) |

**What actually executes when you say something:** Stage 7's `run_ava` → Stage 6's `run_ava` → Stage 4's `run_ava` → base `run_ava`. Each layer adds/modifies behavior then calls the previous version.

---

## Key Differences From `github_avaagent.py`

| Feature | `github_avaagent.py` (GitHub) | `v2_avaagent.py` (real build) |
|---|---|---|
| DeepFace | Subprocess via `py -3.12` | Direct import (fails on Python 3.14) |
| BASE_DIR | `D:\AvaAgentv2` | `D:\AvaAgent` (original) |
| Self-state dispatch | `is_selfstate_query` + `build_selfstate_reply(globals(), input, image, profile, ...)` | No direct dispatch in base `run_ava` — handled by Stage 3, 4, and 6 overlays |
| Overlay architecture | None — all-in-one clean file | Full overlay stack (v30–v36 + Stages 3–7) |
| Meta modes | Not present | Full META_MODE system (balanced, low_initiative, supportive, observational, exploratory + custom) |
| User state model | Not present | 7-state model (focused/stressed/relaxed/fatigued/drifting/socially_open/socially_closed) |
| Trust system | Not wired | Stage 7: `trust_manager.py` fully wired |
| Persona system | Not wired | Stage 7: `persona_switcher.py` fully wired |
| Identity files | Not used | Stage 7: `identity_loader.py` loads IDENTITY.md/SOUL.md/USER.md into system prompt |
| Outcome learning | Not present | v30: per-kind, per-goal, per-state outcome tables |
| MetaController | Not present | v31–v34: full meta state with decay, mode strength, feedback loops |
| Face-gone detection | Not present | Stage 6: fires autonomous message when face disappears |

---

## The Brain Modules — What Actually Runs in v2_avaagent.py

These are imported by the overlays (not the base code):

| Module | Overlay | What it does | Status |
|---|---|---|---|
| `brain.selfstate` | Stage 3 | `is_selfstate_query`, `build_selfstate_reply(health, mood, tendency)`, `startup_health_banner` | ✅ Active |
| `brain.selfstate_router` | Stage 4, 6 | Same functions but patched for new signature `build_selfstate_reply(globals(), input, image, profile)` | ✅ Active (overrides Stage 3) |
| `brain.output_guard` | Stage 4, 5, 6 | `scrub_visible_reply`, `scrub_chat_callback_result` | ✅ Active |
| `brain.initiative_sanity` | Stage 4, 5, 6, 6.1 | `sanitize_candidate_result`, `desaturate_candidate_scores`, `maybe_desaturate_args` | ✅ Active |
| `brain.camera_truth` | Stage 4, 5, 6 | `build_camera_truth`, `camera_identity_reply`, `read_live_frame` | ✅ Active |
| `brain.health_runtime` | Stage 4, 6 | `print_startup_selftest` | ✅ Active |
| `brain.profile_manager` | Stage 5, 6, 7 | `is_valid_profile_name`, `normalize_person_key`, `looks_like_phrase_profile`, `ensure_aliases_in_profile`, `resolve_profile_key_from_text` | ✅ Active |
| `brain.identity_resolver` | Stage 5, 6 | `resolve_confirmed_identity` | ✅ Active |
| `brain.memory_reader` | Stage 6, 6.1 | `build_memory_reader_summary` | ✅ Active |
| `brain.camera_live` | Stage 6 | `read_live_frame` | ✅ Active |
| `brain.trust_manager` | Stage 7 | `is_blocked`, `is_owner`, `get_trust_level`, `build_trust_context_note` | ✅ Active |
| `brain.persona_switcher` | Stage 7 | `build_persona_block`, `should_deflect`, `get_blocked_reply`, `get_deflect_reply` | ✅ Active |
| `brain.profile_store` | Stage 7 | `seed_default_profiles`, `load_profile`, `get_or_create_profile`, `touch_last_seen`, `update_profile_notes` | ✅ Active |
| `brain.identity_loader` | Stage 7 | `ensure_identity_files`, `load_ava_identity`, `process_identity_actions`, `append_to_user_file` | ✅ Active |

---

## Core Bug Inventory (Full v2_avaagent.py Audit)

### 🔴 BUG-01 CRITICAL — BASE_DIR Wrong Path

**Line 32:** `BASE_DIR = Path(r"D:\AvaAgent")`

This points to the old v1 directory, not `D:\AvaAgentv2`. Every file path (MEMORY_DIR, PROFILES_DIR, CHAT_LOG_PATH, etc.) is derived from this. The agent reads/writes to the v1 folder, not the intended v2 folder. If `D:\AvaAgent` has old data, Ava is operating on stale/wrong memory.

---

### 🔴 BUG-02 CRITICAL — Direct DeepFace Import Fails on Python 3.14

**Lines 23–26:**
```python
try:
    from deepface import DeepFace
    DEEPFACE_AVAILABLE = True
except Exception:
    DeepFace = None
    DEEPFACE_AVAILABLE = False
```

DeepFace requires TensorFlow which is incompatible with Python 3.14. This silently sets `DEEPFACE_AVAILABLE = False`, then all expression sensing returns `"unknown"` forever.

**And then line 2347 calls `DeepFace.analyze(...)` directly.** Even if the import somehow succeeded, this is not the subprocess pattern. Unlike `github_avaagent.py` which uses `_deepface_via_py312()`, this file has no subprocess fallback.

---

### 🔴 BUG-03 HIGH — `build_selfstate_reply` Called with 3 Different Signatures

**Stage 3 (line 8710):** `build_selfstate_reply(health, mood, tendency="balanced")`
**Stage 4 (line 8821):** `build_selfstate_reply(globals(), user_input, image, active_profile)`
**Stage 6 (line 9090):** `build_selfstate_reply(globals(), user_input, live_image, active_profile)`

Stage 3 imports from `brain.selfstate` (old signature). Stages 4 and 6 import from `brain.selfstate_router` (new signature). Stage 6 overlay overwrites Stage 4, so the final active version uses Stage 6. But Stage 3 is still sitting on the call stack because `chat_fn` is wrapped by Stage 3 first. If Stage 3's `selfstate` module is present and `brain.selfstate_router` is absent, the signature mismatch crashes.

---

### 🔴 BUG-04 HIGH — `process_ava_action_blocks` Signature Drift Across Overlay Layers

The base `process_ava_action_blocks` signature is `(reply_text, person_id, latest_user_input="")` (3 params).

Stage 4 wraps it as: `_orig_process_ava_action_blocks_stage4(reply_text, person_id)` — **drops `latest_user_input`**.
Stage 6 wraps it as: `_orig_process_ava_action_blocks_stage6(reply_text, person_id)` — **also drops it**.
Stage 7 calls through Stage 6, so the `save_latest_user_message` MEMORY action can never work — `latest_user_input` is always `""` by the time the base function receives it.

---

### 🔴 BUG-05 HIGH — Stage 3 Overlay Uses Wrong `selfstate` Module

**Lines 8669, 8710:** Stage 3 imports `from brain.selfstate import is_selfstate_query, build_selfstate_reply, startup_health_banner` and calls `build_selfstate_reply(health, mood, tendency="balanced")`.

If `brain.selfstate` is the old monolithic version (3-param signature) but `brain.selfstate_router` is the updated version (globals-based signature), Stage 3 and Stage 4 are running conflicting implementations. Stage 3 fires first in the `chat_fn` chain.

---

### 🟡 BUG-06 MEDIUM — Stage 7 `reflect_on_last_reply` Looks for `"learned_fact"` Key That Doesn't Exist

**Line 9339:** `learned = reflection.get("learned_fact") or reflection.get("new_fact")`

The base `build_reflection_record()` (around line 1980–2020) doesn't store a `"learned_fact"` key — it stores `"summary"`, `"tags"`, `"strengths"`, `"improvements"`. Stage 7's auto-profile-learning never fires because neither key exists.

---

### 🟡 BUG-07 MEDIUM — Stage 7 `identity_loader.append_to_user_file` Writes to Wrong Path

`brain.identity_loader` was designed to update `USER.md` inside `D:\AvaAgentv2\ava_identity\`. But `BASE_DIR` is `D:\AvaAgent`, so if `append_to_user_file()` derives its path from `BASE_DIR`, it writes to the old directory.

---

### 🟡 BUG-08 MEDIUM — Duplicate `camera_tick_fn` Wrapping in Stages 3, 4, 6

`camera_tick_fn` is wrapped three times:
- Stage 3: wraps it with scrub + live frame refresh
- Stage 4: wraps `detect_face` and `recognize_face` to use live frame
- Stage 6: wraps `camera_tick_fn` again with face-gone detection

All three wrappers try to call `read_live_frame()` independently from different imports (`brain.selfstate`'s private import, `brain.camera_truth`, `brain.camera_live`). If any one fails, it falls through silently — but they all try to write to `result[0]` (the history), meaning a face-gone event could get written twice.

---

### 🟡 BUG-09 MEDIUM — v30 Outcome Learning `_record_outcome_learning` Never Called on Failure

The `_record_outcome_learning` and `_record_distribution_win` functions are defined and wired in v30, but looking at Stage 7's `run_ava` wrapper — when a user is `is_blocked()` or `should_deflect()`, it returns early without recording any outcome. Refused interactions never contribute to the learning tables, so blocked users stay at the same trust pattern indefinitely.

---

### 🟢 BUG-10 LOW — `GATE_DEBUG_LOGGING = True` Hardcoded at Line ~241

In the base file, `GATE_DEBUG_LOGGING` is set to `True`, meaning verbose gate scoring logs are always printing to console. This creates log spam and was intended to be turned off after debugging.

---

## What's Actually Working Well

- **Full overlay chain loads cleanly** — every `try/except` block around overlays means if one module is missing, it prints a warning and continues
- **Stage 7 trust gate** — `is_blocked()` and `should_deflect()` are wired and functional if `brain.trust_manager` and `brain.persona_switcher` load
- **Stage 7 identity injection** — Ava's IDENTITY.md/SOUL.md/USER.md is loaded at startup and prepended to every system message
- **v30 state model** — 7-state user classification runs on every `recalculate_operational_goals` call
- **v31–v34 MetaController** — adaptive meta mode selection with decay, time-in-mode tracking, per-mode drive multipliers
- **v34 custom META_MODE blocks** — Ava can define her own behavioral modes at runtime
- **Stage 6 face-gone detection** — fires autonomous "Did you step away?" message when face disappears
- **Stage 6.1 pre-selection desaturation** — prevents score inflation in initiative pipeline
- **Stage 6 dynamic memory reader** — injected into every prompt via `build_memory_reader_summary`
- **27-emotion system + 7-style blend** — fully operational
- **Goal system with v30 conflict engine + outcome learning** — sophisticated multi-goal prioritization

---

## Summary of What v2_avaagent.py IS

This is not "v2" in the sense of a rewrite. It is the **fully-evolved v1 monolith** with every stage from Stage 3 through Stage 7 still applied via live overlay stacking inside the file. It is substantially more sophisticated than `github_avaagent.py` but harder to debug and maintain.

The `github_avaagent.py` file is what Ezekiel intended `v2` to become — clean, direct imports, no overlay stacking — but it's missing all the v30–v34 meta intelligence, the Stage 7 trust/persona/identity system, and the user state model. It's a cleaner but less capable build.
