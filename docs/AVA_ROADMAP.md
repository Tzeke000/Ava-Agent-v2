# Ava Agent v2 — Master Roadmap for Cursor
**Last Updated:** April 2026 — Based on full codebase audit (all 6,509 lines of avaagent.py + all 21 brain modules)
**Base:** `D:\AvaAgentv2` / https://github.com/Tzeke000/Ava-Agent-v2

---

## How to Use This Document

Sessions are in priority order. Do SESSION 1 before anything else — these are crashes and silent failures.
Every fix includes: exact file, exact problem, exact code change.
Never rewrite a working module — patch only the broken function.

---

## SESSION 1 — Fix 4 Silent/Critical Failures

These are broken now and block real usage.

---

### FIX-01 🔴 CRITICAL — `build_selfstate_reply` Signature Mismatch

**File to edit:** `brain/selfstate.py`

**Problem:** `run_ava()` calls:
```python
build_selfstate_reply(globals(), user_input, image, active_profile, active_goal=..., narrative_snippet=...)
```
But `selfstate.py` defines:
```python
def build_selfstate_reply(health, mood, tendency=None, active_goal=None, narrative_snippet=None):
```
Passing `active_profile` as the 4th positional arg → `TypeError` crash on every self-state query.

**Fix:** Replace `build_selfstate_reply` in `brain/selfstate.py` with a dual-signature version:

```python
def build_selfstate_reply(
    g_or_health,
    user_input_or_mood=None,
    image_or_tendency=None,
    active_profile=None,
    active_goal: str | None = None,
    narrative_snippet: str | None = None,
) -> str:
    """
    Accepts both call signatures:
      avaagent.py v2: (globals(), user_input, image, active_profile, active_goal=, narrative_snippet=)
      legacy:         (health_dict, mood_dict, tendency_str, active_goal=, narrative_snippet=)
    """
    # Detect which signature we got by checking if the first arg has load_mood
    if isinstance(g_or_health, dict) and callable(g_or_health.get("load_mood")):
        # New signature: g_or_health is globals()
        g = g_or_health
        load_mood_fn = g.get("load_mood")
        load_health_fn = g.get("load_health_state")
        mood = {}
        health = {}
        try:
            mood = dict(load_mood_fn() or {}) if callable(load_mood_fn) else {}
        except Exception:
            pass
        try:
            health = dict(load_health_fn(g) if callable(load_health_fn) else {})
        except TypeError:
            try:
                health = dict(load_health_fn() or {}) if callable(load_health_fn) else {}
            except Exception:
                pass
        except Exception:
            pass
        # Derive tendency from mood behavior_modifiers
        tendency = None
        try:
            bm = mood.get("behavior_modifiers", {}) or {}
            if float(bm.get("caution", 0.0)) > 0.60:
                tendency = "cautious"
            elif float(bm.get("initiative", 0.0)) > 0.65:
                tendency = "engaged"
            else:
                tendency = "balanced"
        except Exception:
            tendency = "balanced"
    else:
        # Legacy signature
        health = g_or_health or {}
        mood = user_input_or_mood or {}
        tendency = image_or_tendency

    state, detail = summarize_health(health)
    mood_text = summarize_mood(mood)
    tendency = tendency or "balanced"

    if state == "healthy":
        prefix = "I'm A-OK right now."
    elif state == "degraded":
        prefix = "I'm mostly okay, but a little degraded right now."
    elif state == "error":
        prefix = "I'm running, but something is definitely off."
    else:
        prefix = "I'm not fully okay right now."

    reply = (
        f"{prefix} Operationally, {detail}. "
        f"Mood-wise I'm leaning {mood_text}, and behavior-wise I'm a bit more {tendency} at the moment."
    )
    if active_goal:
        reply += f"\nRight now my focus is: {active_goal}."
    if narrative_snippet:
        reply += f"\nI've been thinking: {narrative_snippet}"
    return reply
```

---

### FIX-02 🔴 HIGH — `perception.py` DeepFace Always Returns Neutral

**File to edit:** `brain/perception.py`

**Problem:** `build_perception()` does a direct `from deepface import DeepFace` which fails silently on Python 3.14 → `face_emotion` always `"neutral"` → `process_visual_emotion()` in workspace tick always sees neutral → mood never updates from camera.

**Note:** `avaagent.py` already has `_deepface_via_py312()` that uses a subprocess correctly. We just need perception.py to use the same pattern.

**Fix — add this function at the top of `brain/perception.py`** (before `build_perception`):

```python
def _subprocess_face_emotion(frame) -> str:
    """Analyze face emotion via Python 3.12 subprocess (DeepFace/TF incompatible with 3.14)."""
    try:
        import subprocess, tempfile, os as _os, cv2 as _cv2, json as _json
        tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
        tmp_path = tmp.name
        tmp.close()
        _cv2.imwrite(tmp_path, frame)
        script = (
            "from deepface import DeepFace; import json; "
            f"r=DeepFace.analyze(img_path={_json.dumps(tmp_path)}, actions=['emotion'],"
            "detector_backend='skip',enforce_detection=False,silent=True);"
            "r=r[0] if isinstance(r,list) else r;"
            "print(json.dumps(r.get('dominant_emotion','neutral')))"
        )
        res = subprocess.run(
            ["py", "-3.12", "-c", script],
            capture_output=True, text=True, timeout=8
        )
        try:
            _os.remove(tmp_path)
        except Exception:
            pass
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip().strip('"').lower() or "neutral"
    except Exception:
        pass
    return "neutral"
```

**Then in `build_perception()`, replace the entire DeepFace try/except block** with:

```python
try:
    if state.face_detected and frame is not None:
        state.face_emotion = _subprocess_face_emotion(frame)
    else:
        state.face_emotion = "neutral"
except Exception:
    state.face_emotion = "neutral"
```

Python 3.12 is at `C:\Users\Tzeke\AppData\Local\Programs\Python\Python312\` — `py -3.12` will find it.

---

### FIX-03 🔴 HIGH — `attention.py` Kills Check-ins After 5 Minutes

**File to edit:** `brain/attention.py`

**Problem:** `seconds_since_last_message > 300` → `should_speak=False`. 5 min quiet with face = suppressed. But `choose_initiative_candidate()` in avaagent.py checks `attention_state.should_speak` first and returns immediately if False. This means the camera-driven check-in that's supposed to happen at 8-minute idle never fires.

**Fix — replace `compute_attention()` entirely:**

```python
def compute_attention(perception: PerceptionState, seconds_since_last_message: float) -> AttentionState:
    if not perception.face_detected:
        return AttentionState(False, False, False, "no_face_detected")

    em = (perception.face_emotion or "").lower()
    if em in ("angry", "disgust"):
        return AttentionState(True, True, False, "negative_expression_hold")

    # 30+ minutes with face visible — probably stepped away but left cam on
    if seconds_since_last_message > 1800:
        return AttentionState(True, False, False, "extended_absence")

    # 5–30 min idle — prime window for a check-in, NOT for suppression
    if seconds_since_last_message > 300:
        return AttentionState(True, False, True, "idle_checkin_window")

    # Active: < 2 min since last message
    engaged = seconds_since_last_message < 120
    return AttentionState(True, engaged, engaged, "clear")
```

---

### FIX-04 🔴 HIGH — `memory_bridge.py` Never Finds Reflections

**File to edit:** `brain/memory_bridge.py`

**Problem:** In `MemoryBridge.build_summary()`, reflection rows are read as:
```python
txt = str(row.get('reflection_text', row.get('text', '')))[:180].strip()
```

But `build_reflection_record()` in avaagent.py (line ~1987) stores:
```python
{"summary": summarize_reflection(...), ...}
```

The key is `'summary'`. `'reflection_text'` and `'text'` are both absent. The reflection section always shows `"- none retrieved"` and the LLM never sees past self-reflections in context.

**Fix — one line change in `build_summary()`:**

```python
# OLD:
txt = str(row.get('reflection_text', row.get('text', '')))[:180].strip()

# NEW:
txt = str(
    row.get('summary') or
    row.get('reflection_text') or
    row.get('text') or
    ''
)[:180].strip()
```

---

## SESSION 2 — Commit Missing Files to Git

### FIX-05 🟡 MEDIUM — `health_runtime.py` and `initiative_sanity.py` Missing from Repo

These are imported at avaagent.py startup (lines 34–35) but not committed to GitHub. A re-clone crashes immediately.

**Action in `D:\AvaAgentv2`:**
```bash
git add brain/health_runtime.py brain/initiative_sanity.py
git commit -m "fix: commit missing brain modules (health_runtime, initiative_sanity)"
git push
```

If the files are somehow missing locally, recreate them:

**`brain/health_runtime.py`:**
```python
def print_startup_selftest(g: dict):
    checks = [
        ("vector_memory", g.get("vectorstore") is not None),
        ("mood_path", bool(g.get("MOOD_PATH"))),
        ("personality_path", bool(g.get("PERSONALITY_PATH"))),
        ("face_model_loader", callable(g.get("load_face_model_if_available"))),
    ]
    ok = sum(1 for _, v in checks if v)
    total = len(checks)
    status = "HEALTHY" if ok == total else "DEGRADED"
    parts = ", ".join(f"{name}={'ok' if v else 'missing'}" for name, v in checks)
    print(f"[startup-selftest] {status} ({ok}/{total}) :: {parts}")
```

**`brain/initiative_sanity.py`** — copy from `incoming_files/ava_brain_stage6_1/brain/initiative_sanity.py` (it's the correct version).

---

## SESSION 3 — Output and Identity Polish

### FIX-06 🟡 MEDIUM — `output_guard.py` Tail-Trim Over-Cuts

**File to edit:** `brain/output_guard.py`

**Problem:** Any trailing line ≤8 words not ending in `.!?'"` is deleted. Can silently cut a complete, short reply.

**Fix — tighten to only trim clearly hanging fragments:**

```python
# Replace this block:
if cleaned and cleaned[-1] not in '.!?"\'':
    tail = cleaned.rsplit('\n', 1)[-1]
    if len(tail.split()) <= 8:
        cleaned = cleaned[: -len(tail)].rstrip()

# With this:
if cleaned and cleaned[-1] not in '.!?"\'':
    tail = cleaned.rsplit('\n', 1)[-1]
    tail_words = tail.strip().lower().split()
    HANGING_ENDINGS = {
        "and", "but", "or", "so", "to", "for", "with", "in", "on",
        "at", "of", "the", "a", "an", "i", "it", "is"
    }
    is_hanging_fragment = (
        len(tail_words) <= 4 and
        (not tail_words or tail_words[-1] in HANGING_ENDINGS)
    )
    if is_hanging_fragment:
        cleaned = cleaned[: -len(tail)].rstrip()
```

---

### FIX-07 🟡 MEDIUM — `identity_resolver.py` 3-Word Rogue Profile Fallback

**File to edit:** `brain/identity_resolver.py`

**Problem:** The fallback `if len(t.split()) <= 3 and is_valid_profile_name(t): return t.strip()` creates profiles from normal phrases that happen to be ≤3 words.

**Fix — remove the fallback entirely:**
```python
def extract_identity_claim(text: str) -> Optional[str]:
    t = (text or "").strip()
    for pat in SELF_PATTERNS:
        m = re.search(pat, t, flags=re.I)
        if m:
            return m.group(1).strip()
    return None  # Explicit "I am X" / "it's me X" only — no fallback
```

---

## SESSION 4 — Wire the Dormant Systems

Two complete, well-written modules exist and are never wired in.

---

### FEATURE-01 — Wire `trust_manager.py` Into Prompts + Initiative Gate

**File to edit:** `avaagent.py`

`trust_manager.py` has 5 trust levels, per-permission flags, and `build_trust_context_note()`. It just needs to be imported and used.

**Step 1 — add import near line 32:**
```python
from brain.trust_manager import get_trust_label, build_trust_context_note, can, is_blocked
```

**Step 2 — in `build_prompt()` after `active_profile` is resolved, add:**
```python
trust_note = build_trust_context_note(active_profile)
```

**Step 3 — add to ACTIVE PERSON section in the prompt string:**
```
TRUST CONTEXT:
{trust_note}
```

**Step 4 — in `maybe_autonomous_initiation()`, add before `choose_initiative_candidate()` call:**
```python
if is_blocked(load_profile_by_id(person_id)):
    return history, "Blocked person — initiative suppressed."
if not can(load_profile_by_id(person_id), "trigger_initiative"):
    return history, "Trust level too low for autonomous initiative."
```

---

### FEATURE-02 — Wire `health.py` Into Startup + Runtime

**File to edit:** `avaagent.py` and `brain/health.py`

**Step 1 — fix relative path fallback in `brain/health.py`:**
```python
def _health_path(host):
    p = host.get('HEALTH_STATE_PATH') or host.get('STATE_DIR')
    if p:
        from pathlib import Path
        base = Path(str(p))
        return str(base / 'health_state.json' if base.is_dir() else base)
    return 'state/health_state.json'
```

**Step 2 — add to avaagent.py near other PATH constants:**
```python
HEALTH_STATE_PATH = STATE_DIR / "health_state.json"
```

**Step 3 — add import to avaagent.py:**
```python
from brain.health import run_system_health_check, load_health_state, print_startup_health
```

**Step 4 — add to startup section (after `print_startup_selftest`):**
```python
print_startup_health(globals())
```

**Step 5 — run light check every 20 turns in `chat_fn()`:**
```python
if len(_get_canonical_history()) % 20 == 0:
    try:
        run_system_health_check(globals(), kind='light')
    except Exception:
        pass
```

---

## SESSION 5 — Goal Intelligence

### FEATURE-03 — Curiosity Questions Into Initiative

**File to edit:** `avaagent.py`, `collect_initiative_candidates()`

Curiosity questions build up in `self_model.json` (up to 16) but are never fed into the initiative pipeline.

**Add at the end of `collect_initiative_candidates()`, before the `return` line:**

```python
# Feed stored curiosity questions into initiative candidates
model = load_self_model()
questions = model.get("curiosity_questions", []) or []
if questions:
    recent_text = " ".join(
        r.get("content", "") for r in load_recent_chat(person_id=person_id)[-10:]
    ).lower()
    for q in questions[-6:]:
        q_text = str(q).strip()
        if not q_text or q_text.lower() in seen:
            continue
        # Skip if topic is being actively discussed
        key_words = [w for w in q_text.lower().split()[:4] if len(w) > 4]
        if sum(1 for w in key_words if w in recent_text) >= 2:
            continue
        seen.add(q_text.lower())
        candidates.append({
            "kind": "genuine_curiosity",
            "text": q_text,
            "topic_key": _topic_key(q_text),
            "base_score": 0.58,
            "memory_importance": 0.58,
        })
```

**Also add `"genuine_curiosity"` to `CAMERA_AUTONOMOUS_ALLOWED_KINDS`** (near line 192):
```python
CAMERA_AUTONOMOUS_ALLOWED_KINDS = {
    ...,
    "genuine_curiosity",
}
```

---

### FEATURE-04 — Semantic Goal Deduplication

**File to edit:** `avaagent.py`, `add_structured_goal()`

**Problem:** Goals with same meaning but different wording accumulate until hitting the 48-goal cap.

**Add before the `entry = make_goal_entry(...)` block:**

```python
def _goal_text_jaccard(a: str, b: str) -> float:
    ta = set(re.findall(r"[a-z]+", a.lower()))
    tb = set(re.findall(r"[a-z]+", b.lower()))
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)

# In add_structured_goal(), after the exact-match loop:
active_goals = [g for g in system.get("goals", []) if g.get("status", "active") == "active"]
for existing in active_goals:
    if _goal_text_jaccard(goal_text, existing.get("text", "")) >= 0.52:
        existing["importance"] = min(1.0, float(existing.get("importance", 0.6)) + 0.05)
        existing["last_updated"] = now_iso()
        system = recalculate_goal_priorities(system)
        save_goal_system(system)
        return existing  # merge, don't add
```

---

### FEATURE-05 — Goal Auto-Pruning

**File to edit:** `avaagent.py`, `recalculate_goal_priorities()`

Add at the end before `return system`:

```python
GOAL_PRUNE_PRIORITY = 0.08
GOAL_STALE_DAYS = 14
GOAL_MAX_HEALTHY = 20

goals = system.get("goals", [])
now_dt = datetime.now()

for g in goals:
    if g.get("status") != "active":
        continue
    if float(g.get("current_priority", 1.0) or 1.0) < GOAL_PRUNE_PRIORITY:
        g["status"] = "pruned"
        g["pruned_reason"] = "low_priority"
        continue
    try:
        updated = datetime.fromisoformat(g.get("last_updated", g.get("created_at", now_dt.isoformat())))
        if (now_dt - updated).days > GOAL_STALE_DAYS:
            g["status"] = "pruned"
            g["pruned_reason"] = "stale"
    except Exception:
        pass

active = [g for g in goals if g.get("status") == "active"]
if len(active) > GOAL_MAX_HEALTHY:
    active_sorted = sorted(active, key=lambda g: float(g.get("current_priority", 0) or 0))
    for g in active_sorted[:len(active) - GOAL_MAX_HEALTHY]:
        g["status"] = "pruned"
        g["pruned_reason"] = "capacity"

system["goals"] = goals
```

---

## SESSION 6 — Self-Evolution Features

### FEATURE-06 — Mood Decay Between Sessions

**File to edit:** `avaagent.py`, `load_mood()` and `save_mood()`

**Problem:** Mood is saved and loaded as-is. If Ava ends a session anxious, she starts the next equally anxious forever.

**Fix — add `_saved_at` stamp on save, apply decay on load:**

```python
def save_mood(mood: dict):
    try:
        mood["_saved_at"] = now_iso()
        with open(MOOD_PATH, "w", encoding="utf-8") as f:
            json.dump(mood, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Mood save error: {e}")

def load_mood() -> dict:
    if MOOD_PATH.exists():
        try:
            with open(MOOD_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            last_saved = data.get("_saved_at")
            if last_saved:
                try:
                    elapsed = time.time() - datetime.fromisoformat(last_saved).timestamp()
                    # Up to 15% decay per hour, max 85%
                    decay_rate = min(0.85, elapsed / 3600 * 0.15)
                    if decay_rate > 0.01:
                        weights = data.get("emotion_weights", DEFAULT_EMOTIONS.copy())
                        baseline = DEFAULT_EMOTIONS.copy()
                        for k in weights:
                            if k in baseline:
                                weights[k] = weights[k] + (baseline[k] - weights[k]) * decay_rate
                        data["emotion_weights"] = normalize_emotions(weights)
                except Exception:
                    pass
            return enrich_mood_state(data)
        except Exception as e:
            print(f"Mood load error: {e}")
    return enrich_mood_state(default_mood())
```

---

### FEATURE-07 — Face-Away / Return Greeting

**File to edit:** `avaagent.py`

**Add near top of file (after constants):**

```python
_FACE_PRESENCE = {"visible": False, "left_at": None, "was_absent": False, "absent_seconds": 0}

def update_face_presence(face_visible: bool) -> dict:
    global _FACE_PRESENCE
    was = _FACE_PRESENCE["visible"]
    now_str = now_iso()
    if was and not face_visible:
        _FACE_PRESENCE["left_at"] = now_str
        _FACE_PRESENCE["was_absent"] = False
    elif not was and face_visible:
        left_at = _FACE_PRESENCE.get("left_at")
        if left_at:
            try:
                gone = (datetime.fromisoformat(now_str) - datetime.fromisoformat(left_at)).total_seconds()
                _FACE_PRESENCE["was_absent"] = gone > 30
                _FACE_PRESENCE["absent_seconds"] = round(gone)
            except Exception:
                _FACE_PRESENCE["was_absent"] = False
        _FACE_PRESENCE["left_at"] = None
    _FACE_PRESENCE["visible"] = face_visible
    return dict(_FACE_PRESENCE)
```

**Call at top of `camera_tick_fn()`:**
```python
presence = update_face_presence(face_visible)
```

**Add to `collect_initiative_candidates()`** (after the pattern check-in block):
```python
if _FACE_PRESENCE.get("was_absent"):
    secs = _FACE_PRESENCE.get("absent_seconds", 60)
    absence_text = (
        "You're back — I noticed you stepped away for a bit." if secs < 600
        else "You're back — it's been a while."
    )
    if absence_text.lower() not in seen:
        seen.add(absence_text.lower())
        candidates.append({
            "kind": "return_greeting",
            "text": absence_text,
            "topic_key": "return_greeting",
            "base_score": 0.90,
            "memory_importance": 0.75,
        })
    _FACE_PRESENCE["was_absent"] = False
```

**Add `"return_greeting"` to `CAMERA_AUTONOMOUS_ALLOWED_KINDS`.**

---

### FEATURE-08 — Per-Person Relationship Score

**File to edit:** `avaagent.py`, `finalize_ava_turn()`

```python
def update_relationship_score(profile: dict, session_quality: float = 0.5) -> dict:
    score = float(profile.get("relationship_score", 0.3))
    interaction_count = int(profile.get("interaction_count", 0)) + 1
    absence_decay = 0.0
    last_seen = profile.get("last_seen")
    if last_seen:
        try:
            elapsed_days = (datetime.now() - datetime.fromisoformat(last_seen)).days
            absence_decay = min(0.08, elapsed_days * 0.004)
        except Exception:
            pass
    score = max(0.0, min(1.0, score + session_quality * 0.035 - absence_decay))
    profile["relationship_score"] = round(score, 4)
    profile["interaction_count"] = interaction_count
    return profile
```

**Call in `finalize_ava_turn()` after `log_chat()`:**
```python
active_profile = update_relationship_score(active_profile)
save_profile(active_profile)
```

**Inject into `build_prompt()`** in the ACTIVE PERSON section:
```python
rel_score = float(active_profile.get("relationship_score", 0.3))
if rel_score >= 0.7:
    rel_hint = "Deep rapport — be natural, casual, fully familiar."
elif rel_score >= 0.4:
    rel_hint = "Good familiarity — be warm and engaged."
else:
    rel_hint = "Relatively new — be warm but don't over-assume familiarity."
# Add rel_hint to the prompt ACTIVE PERSON block
```

---

### FEATURE-09 — Circadian Tone Shifts

**File to edit:** `avaagent.py`

```python
def get_circadian_modifiers() -> dict:
    hour = datetime.now().hour
    if 5 <= hour < 9:
        return {"initiative_scale": 0.7, "tone_hint": "soft and unhurried — early morning"}
    elif 9 <= hour < 12:
        return {"initiative_scale": 1.1, "tone_hint": "focused and energized — morning"}
    elif 12 <= hour < 17:
        return {"initiative_scale": 1.0, "tone_hint": "steady and grounded — afternoon"}
    elif 17 <= hour < 21:
        return {"initiative_scale": 0.95, "tone_hint": "relaxed and conversational — evening"}
    else:
        return {"initiative_scale": 0.5, "tone_hint": "quiet and low-key — late night"}
```

- Apply `initiative_scale` to the `INITIATIVE_INACTIVITY_SECONDS` comparison in `camera_tick_fn`
- Add `tone_hint` to the TIME section of `build_prompt()`

---

## SESSION 7 — Project File Self-Awareness

Ava can read first 12,000 chars of avaagent.py. She can't read her brain modules or docs.

### FEATURE-10 — Read Any Project File

**File to edit:** `avaagent.py`

```python
PROJECT_READABLE_EXTENSIONS = {".py", ".md", ".txt", ".json", ".bat", ".ps1"}
PROJECT_SKIP_DIRS = {".git", "__pycache__", "memory", "faces", "Ava workbench", "state", "logs"}

def list_project_files(subdir: str = "", limit: int = 100) -> list[str]:
    target = (BASE_DIR / subdir).resolve() if subdir else BASE_DIR.resolve()
    if not str(target).startswith(str(BASE_DIR)):
        return ["❌ Path escapes project."]
    rows = []
    for p in sorted(target.rglob("*")):
        if any(part in PROJECT_SKIP_DIRS for part in p.parts):
            continue
        if p.is_file() and p.suffix in PROJECT_READABLE_EXTENSIONS:
            try:
                rows.append(p.relative_to(BASE_DIR).as_posix())
            except Exception:
                continue
    return rows[:limit]

def read_project_file(relative_path: str, max_chars: int = 15000) -> str:
    try:
        target = (BASE_DIR / relative_path).resolve()
        if not str(target).startswith(str(BASE_DIR)):
            return "❌ Access denied."
        if any(part in PROJECT_SKIP_DIRS for part in target.parts):
            return "❌ Private directory."
        if not target.exists() or not target.is_file():
            return "❌ File not found."
        if target.suffix not in PROJECT_READABLE_EXTENSIONS:
            return "❌ File type not allowed."
        return target.read_text(encoding="utf-8", errors="ignore")[:max_chars]
    except Exception as e:
        return f"❌ Failed: {e}"
```

**Add to `SYSTEM_PROMPT`** (after WORKBENCH section):
```
To list project files:
```PROJECT
action: list
subdir: brain
```

To read a project file:
```PROJECT
action: read
path: brain/beliefs.py
```
```

**Add `PROJECT_BLOCK_RE`** and wire `project_repl` into `process_ava_action_blocks()`.

---

## WHAT TO NEVER TOUCH

These are working correctly — do not modify:
- `brain/camera.py` — CameraManager
- `brain/camera_live.py` — live frame capture
- `brain/camera_truth.py` — camera identity reply
- `brain/workspace.py` — WorkspaceState and tick wiring
- `brain/beliefs.py` — self-narrative system
- `brain/shared.py` — utilities
- `brain/profile_manager.py` — profile key resolution
- `brain/identity.py` — IdentityRegistry
- `brain/memory.py` — decay_tick and recall_for_person
- `brain/trust_manager.py` — trust levels (correct, just not wired)
- `brain/health.py` — health checks (correct, just not wired)
- 27-emotion / 7-style system in avaagent.py
- The `choose_initiative_candidate` pipeline (400 lines, solid)
- The reflection/self-model system in avaagent.py
- The camera snapshot + trend analysis system in avaagent.py

---

## PRIORITY SUMMARY

| Session | Fixes | Impact | Time |
|---|---|---|---|
| 1 | 4 bugs: selfstate crash, emotion blind, 5-min suppression, empty reflections | 🔴 Critical | ~30 min |
| 2 | Commit 2 missing files to git | 🔴 Critical | 2 min |
| 3 | Output trim + identity cleanup | 🟡 Polish | ~15 min |
| 4 | Wire trust + health (already built) | 🟡 Medium | ~20 min |
| 5 | Goal dedup + curiosity initiative + pruning | 🟡 Medium | ~30 min |
| 6 | Mood decay + return greeting + relationship score + circadian | 🟢 Evolution | ~45 min |
| 7 | Project file read self-awareness | 🟢 Nice | ~20 min |
