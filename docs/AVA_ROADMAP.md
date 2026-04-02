# Ava Agent — Master Roadmap (Based on Full v2_avaagent.py Audit)
**Last Updated:** April 2026 — Full audit of v2_avaagent.py (9,381 lines)
**Files:** `v2_avaagent.py` (real running build) | `github_avaagent.py` (cleaner but less capable GitHub build)

---

## Decision You Need to Make First

There are now two valid paths. You cannot merge these indefinitely.

### PATH A — Keep v2_avaagent.py as the primary build
Fix the 4 critical bugs, commit the full file to GitHub, accept that it uses overlay stacking.
**Pros:** Has everything (v30–v34 meta intelligence, Stage 7 trust/identity, user state model, face-gone detection).
**Cons:** 9,381 lines with 7 overlay layers in one file. Hard to maintain.

### PATH B — Migrate everything into github_avaagent.py
Port the v30–v34 MetaController, user state model, Stage 7 trust/identity, and face-gone detection into the clean file.
**Pros:** Clean architecture, maintainable, modular brain imports.
**Cons:** Significant work. Roughly 3,000 lines of logic need to be folded in cleanly.

**Recommendation:** Fix the 4 critical bugs in `v2_avaagent.py` first (Session 1 below), then decide. Don't migrate until it's stable.

---

## SESSION 1 — Fix 4 Critical Crashes in v2_avaagent.py

These must be fixed before anything else.

---

### FIX-01 🔴 CRITICAL — BASE_DIR Points to Wrong Directory

**File:** `v2_avaagent.py`, **line 32**

**Problem:**
```python
BASE_DIR = Path(r"D:\AvaAgent")  # WRONG — this is the old v1 directory
```

**Fix:**
```python
BASE_DIR = Path(r"D:\AvaAgentv2")
```

If `D:\AvaAgentv2` is your actual working directory, this single change fixes all path derivations (MEMORY_DIR, PROFILES_DIR, STATE_DIR, WORKBENCH_DIR, etc.) because they're all `BASE_DIR / "subdir"`.

---

### FIX-02 🔴 CRITICAL — Direct DeepFace Import + No Subprocess Fallback

**File:** `v2_avaagent.py`, **lines 23–26 and ~2347**

**Problem:**
```python
try:
    from deepface import DeepFace  # Fails silently on Python 3.14
    DEEPFACE_AVAILABLE = True
except Exception:
    DeepFace = None
    DEEPFACE_AVAILABLE = False
```
And later:
```python
result = DeepFace.analyze(img_path=..., ...)  # Called directly, no subprocess
```
Expression sensing is permanently broken on Python 3.14.

**Fix — replace the import block at the top of the file:**
```python
import subprocess as _sp
import tempfile as _tempfile
DeepFace = None
DEEPFACE_AVAILABLE = False

def _test_deepface_available() -> bool:
    try:
        result = _sp.run(
            ["py", "-3.12", "-c", "from deepface import DeepFace"],
            capture_output=True, timeout=15
        )
        return result.returncode == 0
    except Exception:
        return False

DEEPFACE_AVAILABLE = _test_deepface_available()
```

**Fix — replace `analyze_expression()` (around line 2347) with subprocess version:**
```python
def _deepface_via_py312(face_bgr_image) -> dict:
    tmp_path = None
    try:
        with _tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp_path = tmp.name
        cv2.imwrite(tmp_path, face_bgr_image)
        img_literal = json.dumps(tmp_path)
        script = (
            "from deepface import DeepFace; import json; "
            "p = " + img_literal + "; "
            "r = DeepFace.analyze(img_path=p, actions=['emotion'], "
            "detector_backend='skip', enforce_detection=False, silent=True); "
            "r = r[0] if isinstance(r, list) else r; "
            "print(json.dumps({'dominant': r.get('dominant_emotion','unknown'), 'emotions': r.get('emotion', {})}))"
        )
        result = _sp.run(["py", "-3.12", "-c", script],
            capture_output=True, text=True, timeout=10)
        if result.returncode == 0 and result.stdout.strip():
            data = json.loads(result.stdout.strip())
            dominant = (data.get("dominant") or "unknown").lower()
            emotions = data.get("emotions", {})
            conf = float(emotions.get(dominant, 0.0)) / 100.0 if dominant in emotions else 0.0
            return {"ok": True, "raw_emotion": dominant,
                    "confidence": max(0.0, min(1.0, conf)),
                    "soft_signal": map_emotion_to_soft_signal(dominant), "emotions": emotions}
        return {"ok": False, "reason": f"subprocess_error: {result.stderr.strip()}"}
    except Exception as e:
        return {"ok": False, "reason": f"deepface_subprocess_error: {e}"}
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass

def analyze_expression(image) -> dict:
    if image is None:
        return {"ok": False, "reason": "no_image"}
    crop = extract_face_crop(image)
    if crop is None:
        return {"ok": False, "reason": "no_face"}
    try:
        face_bgr = cv2.cvtColor(crop, cv2.COLOR_GRAY2BGR)
        return _deepface_via_py312(face_bgr)
    except Exception as e:
        return {"ok": False, "reason": f"analysis_error: {e}"}
```

Python 3.12 location: `C:\Users\Tzeke\AppData\Local\Programs\Python\Python312\`. The `py -3.12` launcher will find it.

---

### FIX-03 🔴 HIGH — `process_ava_action_blocks` Drops `latest_user_input` in Stage 4 and 6 Wrappers

**File:** `v2_avaagent.py`, **line ~8803 (Stage 4) and ~9010 (Stage 6)**

**Problem:** Stage 4's wrapper:
```python
def process_ava_action_blocks(reply_text, person_id):  # missing latest_user_input
    cleaned, actions = _orig_process_ava_action_blocks_stage4(reply_text, person_id)
    return _brain_stage4_guard.scrub_visible_reply(cleaned), actions
```
And Stage 6's wrapper is the same. This means the `save_latest_user_message` MEMORY action block always gets `latest_user_input=""` and fails.

**Fix — update both wrappers to pass through `latest_user_input`:**

Stage 4 wrapper (around line 8803):
```python
def process_ava_action_blocks(reply_text, person_id, latest_user_input=""):
    cleaned, actions = _orig_process_ava_action_blocks_stage4(reply_text, person_id, latest_user_input=latest_user_input)
    return _brain_stage4_guard.scrub_visible_reply(cleaned), actions
```

Stage 6 wrapper (around line 9010):
```python
def process_ava_action_blocks(reply_text, person_id, latest_user_input=""):
    cleaned, actions = _orig_process_ava_action_blocks_stage6(reply_text, person_id, latest_user_input=latest_user_input)
    return _brain_stage6_guard.scrub_visible_reply(cleaned), actions
```

---

### FIX-04 🔴 HIGH — Turn Off Debug Logging

**File:** `v2_avaagent.py`, **~line 241**

```python
GATE_DEBUG_LOGGING = True  # WRONG — floods the console
```

**Fix:**
```python
GATE_DEBUG_LOGGING = False
```

This constant controls verbose initiative gate scoring output. It was left on from debugging and creates massive console spam.

---

## SESSION 2 — Fix the Stage 7 Auto-Learning Loop

### FIX-05 🟡 — Stage 7 `reflect_on_last_reply` Looks for Wrong Key

**File:** `v2_avaagent.py`, **line ~9339**

**Problem:** Stage 7 does:
```python
learned = reflection.get("learned_fact") or reflection.get("new_fact")
```
But the base `build_reflection_record()` stores `"summary"`, `"tags"`, `"strengths"`, `"improvements"` — no `"learned_fact"` key exists. Auto-learning never fires.

**Fix — two options:**

**Option A (easier): Change Stage 7 to use "summary":**
```python
# In Stage 7's reflect_on_last_reply wrapper, change:
learned = reflection.get("learned_fact") or reflection.get("new_fact")
# To:
learned = reflection.get("learned_fact") or reflection.get("new_fact") or (
    reflection.get("summary") if float(reflection.get("importance", 0)) >= 0.75 else None
)
```

**Option B (better): Add "learned_fact" extraction to `build_reflection_record()`**

In `build_reflection_record()` (around line 1980), after building the summary:
```python
# Extract a learnable fact from the reflection
learned_fact = None
summary_text = (record.get("summary", "") or "").strip()
tags = record.get("tags", []) or []
if any(t in tags for t in ["user_preference", "identity", "personalization", "new_or_changed"]):
    if len(summary_text) >= 20:
        learned_fact = summary_text[:200]
record["learned_fact"] = learned_fact
```

---

### FIX-06 🟡 — Stage 7 Identity Files Path Relies on BASE_DIR Being Correct

**Dependency on FIX-01.** Once BASE_DIR is corrected to `D:\AvaAgentv2`, verify that `brain/identity_loader.py` derives its identity file paths from the same base. If it hardcodes a path, update it to:
```python
BASE_DIR = Path(r"D:\AvaAgentv2")
IDENTITY_DIR = BASE_DIR / "ava_identity"
IDENTITY_MD = IDENTITY_DIR / "IDENTITY.md"
SOUL_MD = IDENTITY_DIR / "SOUL.md"
USER_MD = IDENTITY_DIR / "USER.md"
```

---

## SESSION 3 — Consolidate the Overlay Chain

The overlay stacking is the root cause of maintenance difficulty. The right long-term move is to consolidate.

### REFACTOR-01 — Merge Stage 3/4/6 run_ava Wrappers Into Base

The base `run_ava` (line 5596) doesn't handle selfstate queries — Stages 3, 4, and 6 all independently add selfstate routing. They do roughly the same thing with slightly different code. 

**Consolidate by adding to base `run_ava` directly:**

```python
def run_ava(user_input: str, image=None, active_person_id: str | None = None) -> tuple[str, dict, dict, list[str], dict]:
    active_person_id = active_person_id or get_active_person_id()
    active_profile = load_profile_by_id(active_person_id)
    
    # Self-state shortcut (handles "how are you feeling", "are you okay", etc.)
    if is_selfstate_query(user_input):
        active_goal_txt = ""
        try:
            gs = load_goal_system()
            ag = gs.get("active_goal", {})
            active_goal_txt = str(ag.get("name") or "").strip()[:200] if isinstance(ag, dict) else str(ag)[:200]
        except Exception:
            pass
        reply = scrub_visible_reply(build_selfstate_reply(
            globals(), user_input, image, active_profile,
            active_goal=active_goal_txt or None
        ))
        return finalize_ava_turn(user_input, reply, {}, active_profile, [])
    
    # ... rest of existing run_ava ...
```

Then **remove** the selfstate logic from the Stage 3, 4, and 6 wrappers (they can still wrap for their other functionality — scrubbing, live frame, etc.).

---

### REFACTOR-02 — Consolidate camera_tick_fn Wrappers

Three overlays (Stage 3, 4, 6) all wrap `camera_tick_fn`. Merge into one clean `camera_tick_fn` that:
1. Gets live frame via `brain.camera_live.read_live_frame()`
2. Detects face-gone transition
3. Fires autonomously if appropriate
4. Scrubs all output

---

## SESSION 4 — Port Missing Features to github_avaagent.py (If Choosing PATH B)

If you decide to make `github_avaagent.py` the primary build, here's what needs to be ported from `v2_avaagent.py`:

### FEATURE-PORT-01 — v30 User State Model (7 states)

Add `_derive_user_state()` which classifies the user into: `focused`, `stressed`, `relaxed`, `fatigued`, `drifting`, `socially_open`, `socially_closed`.
Wire into `recalculate_operational_goals()`.

### FEATURE-PORT-02 — v31–v34 MetaController

Add:
- `_compute_meta_control()` — produces `meta_control` dict with mode, initiative/silence biases
- `_default_meta_state()` and `_default_meta_feedback()` tables
- `_apply_meta_feedback()` — closed-loop success/failure tracking
- `_decay_meta_state()` — time-based decay for mode persistence
- `META_MODES` dict (5 named modes + custom)
- `META_MODE` action block in `process_ava_action_blocks`

### FEATURE-PORT-03 — v30 Outcome Learning

Add:
- `_record_outcome_learning()` per candidate kind, goal, person, state
- `_outcome_bias()` applied to initiative scoring
- `_record_distribution_win()` 

### FEATURE-PORT-04 — Stage 7 Trust + Persona + Identity

Already built in brain modules. The wiring from `v2_avaagent.py` Stage 7 overlay is a clean 180 lines. Port directly into `build_prompt()` and `run_ava()` in `github_avaagent.py`.

### FEATURE-PORT-05 — Face-Gone Detection

From Stage 6 overlay. Add a `_FACE_WAS_PRESENT = [False]` global and check `face_was and not face_now` in `camera_tick_fn`.

---

## SESSION 5 — New Features Worth Adding (Either File)

### FEATURE-01 — Mood Decay Between Sessions

Mood is currently saved/loaded as-is. Add a decay function in `load_mood()`:
```python
# On load, blend toward baseline based on elapsed time since last save
elapsed = time.time() - datetime.fromisoformat(data.get("_saved_at", now_iso())).timestamp()
decay_rate = min(0.85, elapsed / 3600 * 0.15)  # up to 15% per hour, max 85%
if decay_rate > 0.01:
    weights = data.get("emotion_weights", DEFAULT_EMOTIONS.copy())
    for k in weights:
        if k in DEFAULT_EMOTIONS:
            weights[k] = weights[k] + (DEFAULT_EMOTIONS[k] - weights[k]) * decay_rate
    data["emotion_weights"] = normalize_emotions(weights)
```
Add `data["_saved_at"] = now_iso()` in `save_mood()`.

### FEATURE-02 — Curiosity Questions Into Initiative

`self_model.json` accumulates up to 16 curiosity questions but they're never fed to `collect_initiative_candidates()`. Add them:

```python
# At the end of collect_initiative_candidates(), before return:
questions = model.get("curiosity_questions", []) or []
recent_text = " ".join(r.get("content","") for r in load_recent_chat(person_id=person_id)[-10:]).lower()
for q in questions[-6:]:
    q_text = str(q).strip()
    if not q_text or q_text.lower() in seen:
        continue
    key_words = [w for w in q_text.lower().split()[:4] if len(w) > 4]
    if sum(1 for w in key_words if w in recent_text) >= 2:
        continue  # already being discussed
    seen.add(q_text.lower())
    candidates.append({
        "kind": "genuine_curiosity",
        "text": q_text,
        "topic_key": _topic_key(q_text),
        "base_score": 0.62,
        "memory_importance": 0.60,
    })
```

Add `"genuine_curiosity"` to `CAMERA_AUTONOMOUS_ALLOWED_KINDS`.

### FEATURE-03 — Goal Deduplication

Before `make_goal_entry()` in `add_structured_goal()`:
```python
for existing in [g for g in system.get("goals", []) if g.get("status","active") == "active"]:
    a = set(re.findall(r"[a-z]+", goal_text.lower()))
    b = set(re.findall(r"[a-z]+", existing.get("text","").lower()))
    if a and b and len(a & b) / len(a | b) >= 0.52:
        existing["importance"] = min(1.0, float(existing.get("importance", 0.6)) + 0.05)
        existing["last_updated"] = now_iso()
        return existing  # merge instead of add
```

### FEATURE-04 — Circadian Tone Shifts

```python
def get_circadian_modifiers() -> dict:
    hour = datetime.now().hour
    if 5 <= hour < 9:    return {"initiative_scale": 0.7, "tone_hint": "soft and unhurried"}
    elif 9 <= hour < 12: return {"initiative_scale": 1.1, "tone_hint": "focused and energized"}
    elif 12 <= hour < 17: return {"initiative_scale": 1.0, "tone_hint": "steady and grounded"}
    elif 17 <= hour < 21: return {"initiative_scale": 0.95, "tone_hint": "relaxed and conversational"}
    else:                return {"initiative_scale": 0.5, "tone_hint": "quiet and low-key"}
```

Apply `initiative_scale` to the idle time check in camera_tick_fn.
Add `tone_hint` to the TIME section of `build_prompt()`.

---

## WHAT TO NEVER TOUCH

These are working correctly in both files:
- The 27-emotion / 7-style system
- `score_memory_candidate()` — 15-factor scoring
- `build_reflection_record()` / `reflect_on_last_reply()`
- `process_camera_snapshot()` — importance/trend/transition pipeline
- The initiative scoring pipeline (`score_initiative_candidate`, `_hard_gate_candidate`, `_apply_soft_choice_penalties`, `_dynamic_top_band`)
- `brain.trust_manager` — logic is correct
- `brain.persona_switcher` — logic is correct
- `brain.identity_loader` — logic is correct
- `brain.output_guard` — logic is correct
- v34 `META_MODES` and `_all_meta_modes()` — well-designed

---

## PRIORITY TABLE

| Session | Change | Risk | Value |
|---|---|---|---|
| 1, FIX-01 | BASE_DIR to AvaAgentv2 | 🔴 Low risk, high impact | Fixes all file paths |
| 1, FIX-02 | DeepFace subprocess | 🔴 Low risk, high impact | Fixes expression sensing |
| 1, FIX-03 | Pass latest_user_input through overlays | 🟡 Medium | Fixes save_latest_user_message action |
| 1, FIX-04 | GATE_DEBUG_LOGGING = False | ✅ Zero risk | Reduces console spam |
| 2, FIX-05 | Stage 7 learned_fact key | 🟡 Medium | Enables auto-profile-learning |
| 2, FIX-06 | Identity files path | 🟡 Depends on FIX-01 | Ensures USER.md writes to right place |
| 3 | Consolidate overlays | 🟠 High — careful | Maintainability |
| 4 | Port to github_avaagent.py | 🟠 High — full migration | Clean architecture |
| 5 | New features | ✅ Low risk | Genuine improvements |
