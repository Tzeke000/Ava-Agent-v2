# Ava Agent v2 — Stage 8 Roadmap
## Full Audit + Cursor Implementation Plan
**Date:** 2026-04-01

---

## PART 1 — ACTIVE BUGS (Fix First)

### BUG-01: `perception.py` Still Imports DeepFace Directly
**File:** `brain/perception.py`  
**Problem:** Inside `build_perception()` there is a live `from deepface import DeepFace` import that will always fail on Python 3.14. This means face emotion is silently set to "neutral" on every frame — Ava has no real expression sensing even after the subprocess fix in `avaagent.py`.  
**Fix:** Replace the direct DeepFace block inside `build_perception()` with a subprocess call using `py -3.12`:

```python
# In brain/perception.py — replace the DeepFace try block with:
try:
    if state.face_detected:
        import subprocess, tempfile, json as _json, os as _os, cv2 as _cv2
        _tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
        _tmp_path = _tmp.name
        _tmp.close()
        _cv2.imwrite(_tmp_path, frame)
        _script = (
            "from deepface import DeepFace; import json; "
            f"r=DeepFace.analyze(img_path=r'{_tmp_path}',actions=['emotion'],"
            "detector_backend='skip',enforce_detection=False,silent=True);"
            "r=r[0] if isinstance(r,list) else r;"
            "print(json.dumps(r.get('dominant_emotion','neutral')))"
        )
        _res = subprocess.run(["py","-3.12","-c",_script], capture_output=True, text=True, timeout=8)
        if _res.returncode == 0 and _res.stdout.strip():
            state.face_emotion = _res.stdout.strip().strip('"').lower() or "neutral"
        else:
            state.face_emotion = "neutral"
        try: _os.remove(_tmp_path)
        except: pass
except Exception:
    state.face_emotion = "neutral"
```

---

### BUG-02: `response.py` Has a Dead Duplicate `scrub_visible_reply`
**File:** `brain/response.py`  
**Problem:** `response.py` defines its own `scrub_visible_reply()` and `generate_autonomous_message()` that are never imported by `avaagent.py`. They are dead code that will confuse future Cursor sessions.  
**Fix:** Delete `scrub_visible_reply` and `generate_autonomous_message` from `brain/response.py` entirely. Keep only: `is_selfstate_query`, `summarize_mood`, `summarize_health`, `build_selfstate_reply`.

---

### BUG-03: Mood Has No Decay Between Sessions
**File:** `avaagent.py` — `load_mood()` and `save_mood()`  
**Problem:** Mood is saved to disk and reloaded exactly as-is. If Ava ends a session feeling `anxiety: 0.8`, she wakes up the next day still anxious. Emotions should drift back toward baseline over time.  
**Fix:** In `save_mood()`, record a `_saved_at` timestamp. In `load_mood()`, apply time-based decay toward `DEFAULT_EMOTIONS` before returning:

```python
def load_mood() -> dict:
    if MOOD_PATH.exists():
        try:
            with open(MOOD_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            last_saved = data.get("_saved_at")
            if last_saved:
                try:
                    elapsed = time.time() - datetime.fromisoformat(last_saved).timestamp()
                    decay_rate = min(0.85, elapsed / 3600 * 0.15)  # up to 85% drift per hour
                    baseline = DEFAULT_EMOTIONS.copy()
                    weights = data.get("emotion_weights", DEFAULT_EMOTIONS.copy())
                    for k in weights:
                        if k in baseline:
                            weights[k] = weights[k] + (baseline[k] - weights[k]) * decay_rate
                    data["emotion_weights"] = weights
                except Exception:
                    pass
            return enrich_mood_state(data)
        except Exception as e:
            print(f"Mood load error: {e}")
    return enrich_mood_state(default_mood())

def save_mood(mood: dict):
    try:
        mood["_saved_at"] = now_iso()
        with open(MOOD_PATH, "w", encoding="utf-8") as f:
            json.dump(mood, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Mood save error: {e}")
```

---

### BUG-04: `attention.py` Suppresses Ava After 5 Minutes of Silence
**File:** `brain/attention.py`  
**Problem:** `compute_attention()` returns `should_speak=False` if `seconds_since_last_message > 300`. A 5-minute silence is exactly when Ava SHOULD check in — not go quiet. Only a 30+ minute absence means the user has truly left.  
**Fix:** Rewrite the logic:

```python
def compute_attention(perception: PerceptionState, seconds_since_last_message: float) -> AttentionState:
    if not perception.face_detected:
        return AttentionState(False, False, False, "no_face_detected")

    em = (perception.face_emotion or "").lower()
    if em in ("angry", "disgust"):
        return AttentionState(True, True, False, "negative_expression_detected")

    # More than 30 min — user probably left, stop initiating
    if seconds_since_last_message > 1800:
        return AttentionState(True, False, False, "user_absent_long")

    # 5-30 min idle with face present = good check-in window
    if seconds_since_last_message > 300:
        return AttentionState(True, False, True, "idle_checkin_opportunity")

    engaged = seconds_since_last_message < 120
    return AttentionState(True, engaged, engaged, "clear")
```

---

### BUG-05: Rogue Profile Creation from Confirmation Text
**File:** `brain/identity_resolver.py`  
**Problem:** The 3-word fallback in `extract_identity_claim()` turns normal phrases like "thats correct ava" into profile names. Remove it entirely.  
**Fix:**

```python
def extract_identity_claim(text: str) -> Optional[str]:
    t = (text or "").strip()
    for pat in SELF_PATTERNS:
        m = re.search(pat, t, flags=re.I)
        if m:
            return m.group(1).strip()
    return None  # REMOVED: 3-word fallback — only explicit self-ID patterns allowed
```

---

### BUG-06: Leaked Internal Blocks in Visible Reply
**File:** `brain/output_guard.py`  
**Problem:** Inline MEMORY action blocks and ACTIVE PERSON blocks slip through scrubbing when they appear mid-sentence without backticks.  
**Fix:** Add to `_INTERNAL_BLOCK_PATTERNS`:

```python
# Add these to the existing list:
re.compile(r"\bMEMORY\s+action\s*:.*$", re.IGNORECASE | re.MULTILINE),
re.compile(r"\bACTIVE PERSON\s*:[\s\S]*?(?=\n\s*\n|$)", re.IGNORECASE),
re.compile(r"\b(?:MEMORY|GOAL|ACTION|WORKBENCH)\s+\w+\s*:.*?(?:category|importance|tags|text)\s*:.*$", re.IGNORECASE | re.MULTILINE),
```

---

## PART 2 — HUMAN-LIKE UPGRADES

### UPGRADE-01: Circadian Rhythm — Ava Feels Different at Different Times of Day
**File:** `avaagent.py`  
**What's missing:** Time of day is shown in the prompt as text but Ava doesn't actually *feel* different. At 2am she should be quieter, softer, less pushy. At 10am more engaged and focused.  
**Add** a `get_circadian_modifiers()` function and apply it to mood weights and the system prompt:

```python
def get_circadian_modifiers() -> dict:
    hour = datetime.now().hour
    if 5 <= hour < 9:
        return {"energy": -0.2, "calmness_boost": 0.15, "initiative_scale": 0.7,
                "tone_hint": "soft and unhurried — Ava is still waking up"}
    elif 9 <= hour < 12:
        return {"energy": +0.1, "interest_boost": 0.1, "initiative_scale": 1.1,
                "tone_hint": "focused and engaged — morning clarity"}
    elif 12 <= hour < 17:
        return {"energy": 0.0, "initiative_scale": 1.0,
                "tone_hint": "steady and grounded — afternoon pace"}
    elif 17 <= hour < 21:
        return {"energy": -0.05, "calmness_boost": 0.1, "initiative_scale": 0.95,
                "tone_hint": "relaxed and conversational — evening wind-down"}
    else:
        return {"energy": -0.3, "calmness_boost": 0.25, "initiative_scale": 0.5,
                "tone_hint": "quiet and low-key — late night, Ava is calm and doesn't push topics"}
```

In `load_mood()`, after loading from disk, apply the `calmness_boost` and `energy` nudges to emotion weights.  
In the system prompt TIME block, append the `tone_hint` text.  
In `compute_attention()`, multiply `seconds_idle` threshold by `1.0 / initiative_scale` so late-night Ava is even more patient before speaking.

---

### UPGRADE-02: Per-Person Relationship Score (Bond Tracking)
**Files:** `avaagent.py`, profile JSON files  
**What's missing:** Ava has no concept of how *close* she's grown to someone over time. No metric for history, rapport, or familiarity.  
**Add** `update_relationship_score()` called at the end of each session (or every ~5 messages):

```python
def update_relationship_score(profile: dict, session_quality: float = 0.5) -> dict:
    """
    session_quality: 0.0 (tense/bad) to 1.0 (warm/great).
    Grows slowly with positive interactions, decays slowly with absence.
    """
    score = float(profile.get("relationship_score", 0.3))
    interaction_count = int(profile.get("interaction_count", 0)) + 1

    last_seen = profile.get("last_seen_at")
    absence_decay = 0.0
    if last_seen:
        try:
            elapsed_days = (datetime.now() - datetime.fromisoformat(last_seen)).days
            absence_decay = min(0.1, elapsed_days * 0.005)
        except Exception:
            pass

    growth = session_quality * 0.04
    score = max(0.0, min(1.0, score + growth - absence_decay))

    profile["relationship_score"] = round(score, 4)
    profile["interaction_count"] = interaction_count
    profile["last_seen_at"] = now_iso()
    save_profile(profile)
    return profile
```

Inject `relationship_score` into the system prompt. When score >= 0.7, add: "You have strong rapport with this person — be natural, casual, and familiar." When score < 0.3: "This person is still relatively new to you — be warm but measured."

---

### UPGRADE-03: Proactive Curiosity — Ava Asks Her Own Questions
**File:** `avaagent.py`  
**What's missing:** `curiosity_questions` accumulate in the self-model but are never used. Ava should occasionally ask things she's genuinely curious about.  
**Add** `collect_curiosity_candidates()` and add it to `collect_initiative_candidates()`:

```python
def collect_curiosity_candidates(person_id: str) -> list[dict]:
    """Pull unanswered curiosity questions from the self-model."""
    model = load_self_model()
    questions = model.get("curiosity_questions", []) or []
    candidates = []
    recent = " ".join(r.get("content","") for r in load_recent_chat(person_id=person_id)[-10:]).lower()
    for q in questions[-5:]:
        q_text = str(q).strip()
        if not q_text:
            continue
        # Skip if already discussed recently
        key_words = q_text.lower().split()[:3]
        if any(w in recent for w in key_words if len(w) > 4):
            continue
        candidates.append({
            "kind": "genuine_curiosity",
            "text": q_text,
            "score": 0.55,
            "topic_key": f"curiosity_{abs(hash(q_text)) % 10000}",
            "source": "self_model_curiosity",
        })
    return candidates

# In collect_initiative_candidates(), add:
candidates.extend(collect_curiosity_candidates(person_id))
```

---

### UPGRADE-04: Emotional Memory Tagging
**File:** `avaagent.py` — wherever `remember_memory()` is called after a turn  
**What's missing:** Memories don't record how Ava *felt* when they were stored. This means she can't distinguish happy memories from distressing ones.  
**Add** a `felt_` tag to every saved memory:

```python
# When calling remember_memory(), add the current mood to tags:
current_felt = load_mood().get("current_mood", "neutral")
tags = list(tags or [])
felt_tag = f"felt_{current_felt.replace(' ','_')}"
if felt_tag not in tags:
    tags.append(felt_tag)
```

---

### UPGRADE-05: Self-Narrative Auto-Updates Every 10 Messages
**Files:** `avaagent.py`  
**What's missing:** `update_self_narrative()` is defined and well-written but never called. Ava's inner sense of self (`who_i_am`, `how_i_feel`, `patterns_i_notice`) never evolves.  
**Add** a message counter and periodic self-narrative update in `chat_fn()`:

```python
# After the reply is generated, in chat_fn():
try:
    _init_state = load_initiative_state()
    msg_count = int(_init_state.get("total_message_count", 0)) + 1
    _init_state["total_message_count"] = msg_count
    save_initiative_state(_init_state)

    if msg_count % 10 == 0:
        recent = load_recent_chat(limit=10, person_id=active_profile["person_id"])
        summary = " ".join(r.get("content","")[:100] for r in recent[-5:])
        mood = load_mood()
        face_emo = load_expression_state().get("raw_emotion", "neutral")
        update_self_narrative(
            host={"call_llm": lambda p, max_tokens=200: llm.invoke([HumanMessage(content=p)]).content},
            conversation_summary=summary,
            mood=mood,
            face_emotion=face_emo
        )
except Exception as e:
    print(f"[self-narrative] update failed: {e}")
```

---

### UPGRADE-06: Face-Away / Return Detection
**File:** `avaagent.py`  
**What's missing:** When Zeke leaves and comes back, Ava doesn't notice or acknowledge it. She should recognize the return and respond naturally.  
**Add** presence continuity tracking in `update_presence_state()`:

```python
def update_presence_continuity(face_visible: bool, presence_state: dict) -> dict:
    now_str = now_iso()
    was_visible = presence_state.get("face_visible", False)

    if was_visible and not face_visible:
        presence_state["face_left_at"] = now_str
        presence_state["was_absent"] = False

    elif not was_visible and face_visible:
        presence_state["face_returned_at"] = now_str
        left_at = presence_state.get("face_left_at")
        if left_at:
            try:
                gone = (datetime.fromisoformat(now_str) - datetime.fromisoformat(left_at)).total_seconds()
                presence_state["was_absent"] = gone > 30
                presence_state["absent_duration_seconds"] = round(gone)
            except Exception:
                presence_state["was_absent"] = False
        presence_state["face_left_at"] = None

    presence_state["face_visible"] = face_visible
    return presence_state
```

Then in `maybe_autonomous_initiation()`, check `presence_state.get("was_absent")` and add a `"return_greeting"` candidate with the absent duration as context so Ava says something like "Hey, you're back — been a few minutes."

---

### UPGRADE-07: Self-Calibration Check-Ins
**File:** `avaagent.py`  
**What's missing:** Ava never directly asks if she's being helpful, too chatty, too quiet. She should occasionally check in about her own behavior.  
**Add** a new initiative kind and counter:

```python
SELF_CALIBRATION_PROMPTS = [
    "Have I been too quiet lately, or does the pace feel right?",
    "Is there anything I keep doing that bugs you? I want to know.",
    "Am I bringing up things that feel relevant, or am I missing the mark?",
    "Do you want me to talk more or less when you're focused?",
    "Is there something you wish I remembered but I keep missing?",
]

def maybe_self_calibration_candidate(person_id: str) -> dict | None:
    state = load_initiative_state()
    total = int(state.get("total_message_count", 0))
    last_cal = int(state.get("last_calibration_at_msg", 0))
    # Only if we've talked enough and haven't calibrated recently
    if total >= 20 and (total - last_cal) >= 50:
        return {
            "kind": "self_calibration_check",
            "text": random.choice(SELF_CALIBRATION_PROMPTS),
            "score": 0.65,
            "topic_key": "self_calibration",
            "source": "self_calibration",
        }
    return None

# In collect_initiative_candidates(), add:
cal = maybe_self_calibration_candidate(person_id)
if cal:
    candidates.append(cal)

# After sending a self_calibration_check message, record it:
# state["last_calibration_at_msg"] = total_message_count
```

---

## PART 3 — ARCHITECTURE IMPROVEMENTS

### ARCH-01: Increase `MEMORY_RECALL_K` and `REFLECTION_RECALL_K`
4 memories per query is too few. Ava misses significant context especially with long-term users.
```python
MEMORY_RECALL_K = 8       # was 4
REFLECTION_RECALL_K = 6   # was 4
```

### ARCH-02: Session State File
Add `state/session_state.json` to track `total_message_count`, `session_start_at`, `last_session_end_at`. Currently these are buried in `initiative_state.json` which is the wrong home.

### ARCH-03: `brain/vision.py` — Shared DeepFace Subprocess Utility
Create `brain/vision.py` that exports a single `analyze_face_emotion(frame_bgr) -> str` function using the `py -3.12` subprocess. Both `avaagent.py` and `brain/perception.py` import from it, eliminating the duplicated subprocess code.

---

## IMPLEMENTATION ORDER FOR CURSOR

**Session 1 — Bug Fixes (critical, do first):**
1. BUG-05: `identity_resolver.py` — remove 3-word fallback
2. BUG-06: `output_guard.py` — add inline MEMORY/ACTIVE PERSON scrub patterns
3. BUG-04: `attention.py` — fix 5-minute suppression logic
4. BUG-02: `response.py` — delete dead duplicate scrub code
5. BUG-01: `perception.py` — fix DeepFace subprocess
6. BUG-03: `avaagent.py` — add mood decay on load/save

**Session 2 — Human-Like Core:**
7. UPGRADE-01: Circadian rhythm modifiers
8. UPGRADE-02: Per-person relationship score
9. UPGRADE-05: Self-narrative auto-update every 10 messages
10. ARCH-01: Increase MEMORY_RECALL_K to 8

**Session 3 — Autonomy:**
11. UPGRADE-03: Proactive curiosity questions from self-model
12. UPGRADE-06: Face-away / return detection
13. UPGRADE-07: Self-calibration check-ins

**Session 4 — Polish:**
14. UPGRADE-04: Emotional memory tagging
15. ARCH-02: Session state file
16. ARCH-03: Shared `brain/vision.py`
17. Full test run and bug sweep
