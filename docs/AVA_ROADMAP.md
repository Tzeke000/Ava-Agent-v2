# Ava Agent v2 — Master Roadmap for Cursor
**Last Updated:** April 2026  
**Base:** `D:\AvaAgentv2` / https://github.com/Tzeke000/Ava-Agent-v2

---

## How to Use This Document

Each section is a Cursor session. Do them in order — each one builds on the previous.  
Every fix includes the exact file, the exact problem, and the exact replacement code.  
Do not skip ahead. Do not rewrite working modules.

---

## SESSION 1 — Bug Fixes (Do These First)

These are active defects. Fix all of them before adding any new features.

---

### FIX-01: `perception.py` — DeepFace Subprocess (CRITICAL)
**File:** `brain/perception.py`  
**Problem:** The `build_perception()` function has a direct `from deepface import DeepFace` import. Python 3.14 cannot load DeepFace/TensorFlow, so this always silently falls back to `"neutral"`. Ava has been emotionally blind since v2 launched.  
**Fix:** Replace the entire DeepFace try/except block with a `py -3.12` subprocess call (Python 3.12 is at `C:\Users\Tzeke\AppData\Local\Programs\Python\Python312\`):

```python
# In brain/perception.py — replace the DeepFace block:
try:
    if state.face_detected:
        import subprocess, tempfile, os as _os, cv2 as _cv2
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
        _res = subprocess.run(
            ["py", "-3.12", "-c", _script],
            capture_output=True, text=True, timeout=8
        )
        if _res.returncode == 0 and _res.stdout.strip():
            state.face_emotion = _res.stdout.strip().strip('"').lower() or "neutral"
        else:
            state.face_emotion = "neutral"
        try:
            _os.remove(_tmp_path)
        except Exception:
            pass
except Exception:
    state.face_emotion = "neutral"
```

---

### FIX-02: `attention.py` — Silence Suppression Logic (HIGH)
**File:** `brain/attention.py`  
**Problem:** `compute_attention()` returns `should_speak=False` when `seconds_since_last_message > 300`. This means Ava goes silent after 5 minutes. A 5-minute pause with a face visible is the best time to check in — not go quiet. Only a 30+ minute gap means the user truly left.  
**Fix:** Replace `compute_attention()` entirely:

```python
def compute_attention(perception: PerceptionState, seconds_since_last_message: float) -> AttentionState:
    if not perception.face_detected:
        return AttentionState(False, False, False, "no_face_detected")

    em = (perception.face_emotion or "").lower()
    if em in ("angry", "disgust"):
        return AttentionState(True, True, False, "negative_expression_detected")

    # 30+ min with no message — user probably stepped away entirely
    if seconds_since_last_message > 1800:
        return AttentionState(True, False, False, "user_absent_long")

    # 5–30 min idle, face present — good window to check in
    if seconds_since_last_message > 300:
        return AttentionState(True, False, True, "idle_checkin_opportunity")

    engaged = seconds_since_last_message < 120
    return AttentionState(True, engaged, engaged, "clear")
```

---

### FIX-03: `identity_resolver.py` — Rogue Profile Creation (HIGH)
**File:** `brain/identity_resolver.py`  
**Problem:** Any 3-word phrase in user input can create a new profile. Phrases like "thats correct ava" or "yes it is" get turned into named profiles.  
**Fix:** Remove the 3-word fallback from `extract_identity_claim()`. Only explicit self-ID patterns (`"I am X"`, `"it's me X"`) should create profiles:

```python
def extract_identity_claim(text: str) -> Optional[str]:
    t = (text or "").strip()
    for pat in SELF_PATTERNS:
        m = re.search(pat, t, flags=re.I)
        if m:
            return m.group(1).strip()
    return None  # No fallback — only explicit "I am X" / "it's me X" patterns allowed
```

---

### FIX-04: `response.py` — Dead Duplicate Code (MEDIUM)
**File:** `brain/response.py`  
**Problem:** `response.py` defines its own `scrub_visible_reply()` and `generate_autonomous_message()`. Neither is imported by `avaagent.py` — both are dead code that shadow the real versions in `output_guard.py` and could confuse Cursor in future sessions.  
**Fix:** Delete `scrub_visible_reply` and `generate_autonomous_message` from `brain/response.py`. Keep only: `is_selfstate_query`, `summarize_mood`, `summarize_health`, `build_selfstate_reply`.

---

### FIX-05: `avaagent.py` — Mood Decay Between Sessions (MEDIUM)
**File:** `avaagent.py` — `load_mood()` and `save_mood()`  
**Problem:** Mood is saved to disk and reloaded exactly as-is next session. If Ava ends a session anxious (anxiety: 0.8), she wakes up the next day just as anxious. Emotions should drift back toward the default baseline when she hasn't been active.  
**Fix:** Add `_saved_at` timestamp in `save_mood()`, apply time-based decay in `load_mood()`:

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
                    import time as _time
                    elapsed = _time.time() - datetime.fromisoformat(last_saved).timestamp()
                    # Up to 85% drift toward baseline per hour elapsed
                    decay_rate = min(0.85, elapsed / 3600 * 0.15)
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
```

---

### FIX-06: `output_guard.py` — Leaked Internal Blocks (MEDIUM)
**File:** `brain/output_guard.py`  
**Problem:** Inline MEMORY action blocks and ACTIVE PERSON blocks slip through `scrub_visible_reply()` when they appear without backtick wrappers.  
**Fix:** Add these patterns to `_INTERNAL_BLOCK_PATTERNS`:

```python
re.compile(r"\bMEMORY\s+action\s*:.*$", re.IGNORECASE | re.MULTILINE),
re.compile(r"\bACTIVE\s+PERSON\s*:[\s\S]*?(?=\n\s*\n|$)", re.IGNORECASE),
re.compile(r"\b(?:MEMORY|GOAL|ACTION|WORKBENCH)\s+\w+\s*:.*$", re.IGNORECASE | re.MULTILINE),
```

---

### FIX-07: `avaagent.py` — Increase Memory Recall Depth (LOW)
**File:** `avaagent.py`  
**Problem:** `MEMORY_RECALL_K = 4` and `REFLECTION_RECALL_K = 4` are too low. Ava misses relevant context especially in long-term relationships.  
**Fix:**
```python
MEMORY_RECALL_K = 8       # was 4
REFLECTION_RECALL_K = 6   # was 4
```

---

## SESSION 2 — Fluid Voice / Conversation (The ChatGPT Feel)

This session makes talking to Ava feel natural. The current system only processes audio when you fully stop recording — she has no idea if you paused mid-sentence or finished speaking.

---

### FEATURE-01: Partial Speech / Interruption Awareness (HIGH)

**What to build:** Ava should detect when you pause briefly mid-sentence vs. when you actually finish. If she's speaking and you start talking, she should stop and listen.

**File:** `avaagent.py` — voice pipeline

**Step 1 — Add a VAD (Voice Activity Detection) helper using `faster_whisper`'s built-in VAD:**

```python
# Add near the Whisper init section:
VAD_SILENCE_THRESHOLD_MS = 800   # ms of silence = end of utterance
VAD_CONTINUATION_WINDOW_MS = 2000  # if speech resumes within this window, it's continuation

# State for tracking partial speech
_PARTIAL_SPEECH_BUFFER = []       # list of audio chunks
_LAST_SPEECH_END_TS = 0.0         # timestamp when user last stopped speaking
_SPEECH_IN_PROGRESS = False
```

**Step 2 — Replace `voice_fn` trigger with a streaming audio handler:**

In Gradio, change `voice_input.stop_recording` to `voice_input.stream` with a short chunk interval. Each chunk is fed through Whisper with `vad_filter=True`:

```python
def voice_stream_fn(audio_chunk, history, image, state):
    """
    Called on every audio chunk (~500ms intervals).
    Accumulates speech, detects pauses, decides when to respond.
    """
    global _PARTIAL_SPEECH_BUFFER, _LAST_SPEECH_END_TS, _SPEECH_IN_PROGRESS

    if audio_chunk is None:
        return history, state

    # Append chunk to buffer
    _PARTIAL_SPEECH_BUFFER.append(audio_chunk)

    # Transcribe current buffer with VAD
    combined = combine_audio_chunks(_PARTIAL_SPEECH_BUFFER)
    segments, info = whisper_model.transcribe(
        combined,
        beam_size=3,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": VAD_SILENCE_THRESHOLD_MS}
    )
    text = " ".join(s.text for s in segments).strip()

    if not text:
        return history, state

    # Detect if speech has stopped (silence detected by VAD)
    speech_ended = info.duration - info.all_language_probs[0][1] < 0.5  # rough heuristic
    now = time.time()

    if speech_ended:
        # Check if this is a continuation of recent speech
        gap = now - _LAST_SPEECH_END_TS
        if gap < (VAD_CONTINUATION_WINDOW_MS / 1000) and state.get("last_partial"):
            # Still continuing — don't respond yet, accumulate
            state["last_partial"] = text
            return history, state
        else:
            # Real end of utterance — process it
            _PARTIAL_SPEECH_BUFFER = []
            _LAST_SPEECH_END_TS = now
            state["last_partial"] = ""
            return process_voice_utterance(text, history, image)
    else:
        state["last_partial"] = text
        return history, state
```

**Step 3 — Add `_SPEAKING` flag so Ava stops mid-sentence if user starts talking:**

```python
_AVA_SPEAKING = False  # global flag

# When Ava starts generating a reply:
_AVA_SPEAKING = True

# In voice_stream_fn, at the top:
if _AVA_SPEAKING and audio_chunk is not None:
    _AVA_SPEAKING = False  # user interrupted — abort current response
    _PARTIAL_SPEECH_BUFFER = []
    # Optionally: append "[interrupted]" note to history so Ava knows

# When Ava finishes her reply:
_AVA_SPEAKING = False
```

**Step 4 — Update Gradio wiring:**

```python
# In the Gradio interface, replace stop_recording with streaming:
voice_input.stream(
    voice_stream_fn,
    inputs=[voice_input, chatbot, camera, voice_state],
    outputs=[chatbot, voice_state],
    time_limit=30,
    stream_every=0.5  # process every 500ms
)
```

**What this achieves:** Ava processes speech in 500ms chunks. If you pause briefly mid-sentence, she waits. If you resume within 2 seconds, she treats it as the same utterance. If you stop for longer, she responds. If she's mid-reply and you start talking, she stops.

---

### FEATURE-02: Natural Pause Handling in Text Chat (LOW)
**File:** `avaagent.py`  
**What to build:** When using text chat, if the user sends a very short message (< 4 words) followed quickly by another message, treat them as one combined input rather than two separate turns.

```python
# Add to chat_fn() at the top:
SHORT_MESSAGE_WINDOW_SECONDS = 4.0  # if next message comes within 4s of a short one, merge

_PENDING_SHORT_MESSAGE = None
_PENDING_SHORT_MESSAGE_TS = 0.0

def maybe_merge_with_pending(new_text: str) -> str:
    global _PENDING_SHORT_MESSAGE, _PENDING_SHORT_MESSAGE_TS
    now = time.time()
    if _PENDING_SHORT_MESSAGE and (now - _PENDING_SHORT_MESSAGE_TS) < SHORT_MESSAGE_WINDOW_SECONDS:
        merged = _PENDING_SHORT_MESSAGE + " " + new_text
        _PENDING_SHORT_MESSAGE = None
        return merged
    words = len(new_text.strip().split())
    if words < 4:
        _PENDING_SHORT_MESSAGE = new_text
        _PENDING_SHORT_MESSAGE_TS = now
        return None  # hold, don't process yet
    return new_text
```

---

## SESSION 3 — Project File Awareness

Ava currently has a `Workbench` folder for file read/write, but it's a separate directory (`D:\AvaAgentv2\Ava workbench`). She cannot see her own source code, brain modules, or project structure.

---

### FEATURE-03: Ava Can See the AvaAgentv2 Project (HIGH)
**File:** `avaagent.py`  
**What to build:** Give Ava read-only access to the full `D:\AvaAgentv2` directory — her own source code, brain modules, config files, docs. She should be able to list and read (but NOT write) any file in the project.

**Step 1 — Add a read-only project directory constant:**

```python
PROJECT_DIR = BASE_DIR  # D:\AvaAgentv2 — already defined as BASE_DIR
MAX_PROJECT_FILE_CHARS = 15000  # max chars to read from any project file
```

**Step 2 — Add `list_project_files()` and `read_project_file()`:**

```python
def list_project_files(subdir: str = "", limit: int = 150) -> list[str]:
    """List files in the project directory. Optional subdir to narrow scope."""
    target = (PROJECT_DIR / subdir).resolve() if subdir else PROJECT_DIR.resolve()
    # Safety: must still be inside PROJECT_DIR
    if not str(target).startswith(str(PROJECT_DIR)):
        return []
    rows = []
    skip_dirs = {".git", "__pycache__", "memory", "faces", "Ava workbench", "state", "logs"}
    for p in sorted(target.rglob("*")):
        if any(part in skip_dirs for part in p.parts):
            continue
        if p.is_file():
            try:
                rows.append(p.relative_to(PROJECT_DIR).as_posix())
            except Exception:
                continue
    return rows[:limit]

def read_project_file(relative_path: str, max_chars: int = MAX_PROJECT_FILE_CHARS) -> str:
    """Read a file from the project directory (read-only)."""
    try:
        target = (PROJECT_DIR / relative_path).resolve()
        # Safety: must be inside PROJECT_DIR
        if not str(target).startswith(str(PROJECT_DIR)):
            return "❌ Access denied — path is outside the project directory."
        skip_dirs = {".git", "__pycache__", "memory", "faces"}
        if any(part in skip_dirs for part in target.parts):
            return "❌ Access denied — this directory is private."
        if not target.exists() or not target.is_file():
            return "❌ File not found."
        return target.read_text(encoding="utf-8", errors="ignore")[:max_chars]
    except Exception as e:
        return f"❌ Failed to read project file: {e}"
```

**Step 3 — Register in the system prompt tools section:**

Add to the tools/capabilities block in `build_prompt()`:
```
- list_project_files(subdir="") → list files in the AvaAgentv2 project
- read_project_file(relative_path) → read any project source file (read-only)
```

**Step 4 — Wire into the ACTION parser** so when Ava outputs:
```
ACTION: read_project_file
path: brain/identity.py
```
It executes `read_project_file("brain/identity.py")` and injects the result.

---

## SESSION 4 — Goal Intelligence (Merge + Prune)

---

### FEATURE-04: Semantic Goal Deduplication / Merging (HIGH)
**File:** `avaagent.py` — `add_structured_goal()`  
**Problem:** Currently, only exact text matches are deduplicated. Goals like "track meaningful memories", "remember important things about the user", and "store context from conversations" are all kept as separate goals even though they mean the same thing. Over time this creates a bloated goal list.

**What to build:** Before adding a new goal, check semantic similarity against all active goals. If similarity > 0.82, merge instead of creating:

```python
def _goal_semantic_similarity(text_a: str, text_b: str) -> float:
    """
    Fast word-overlap similarity using Jaccard on lowercase tokens.
    No external model needed.
    """
    tokens_a = set(re.findall(r"[a-z]+", text_a.lower()))
    tokens_b = set(re.findall(r"[a-z]+", text_b.lower()))
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union)

def _find_similar_goal(new_text: str, goals: list[dict], threshold: float = 0.52) -> dict | None:
    """Return the most similar active goal if above threshold, else None."""
    best_match = None
    best_score = 0.0
    for g in goals:
        if g.get("status", "active") != "active":
            continue
        score = _goal_semantic_similarity(new_text, g.get("text", ""))
        if score > best_score and score >= threshold:
            best_score = score
            best_match = g
    return best_match
```

Update `add_structured_goal()` to call `_find_similar_goal()` before creating a new entry:

```python
def add_structured_goal(goal_text, kind="goal", horizon="short_term", ...):
    goal_text = trim_for_prompt((goal_text or "").strip(), limit=220)
    if not goal_text:
        return None
    system = load_goal_system()
    active_goals = [g for g in system.get("goals", []) if g.get("status", "active") == "active"]

    # Exact match check (existing)
    for g in active_goals:
        if g.get("text", "").strip().lower() == goal_text.lower() and g.get("kind") == kind:
            g["importance"] = max(float(g.get("importance", 0.6)), float(importance or 0.6))
            g["last_updated"] = now_iso()
            save_goal_system(recalculate_goal_priorities(system))
            return g

    # NEW: Semantic similarity check
    similar = _find_similar_goal(goal_text, active_goals, threshold=0.52)
    if similar:
        # Merge: keep the existing goal, boost its importance slightly
        similar["importance"] = min(1.0, float(similar.get("importance", 0.6)) + 0.05)
        similar["last_updated"] = now_iso()
        # Append new text as a note/alias so context isn't lost
        aliases = similar.get("text_aliases", [])
        if goal_text not in aliases:
            aliases.append(goal_text)
        similar["text_aliases"] = aliases[-5:]  # keep last 5
        save_goal_system(recalculate_goal_priorities(system))
        print(f"[goals] Merged '{goal_text}' into existing goal: '{similar['text']}'")
        return similar

    # Create new goal (existing logic continues...)
```

---

### FEATURE-05: Goal Auto-Pruning (MEDIUM)
**File:** `avaagent.py`  
**Problem:** Completed, stale, or very low-priority goals accumulate forever. The goal list grows unbounded.  
**Add** a pruning step that runs every time goals are recalculated:

```python
GOAL_MAX_ACTIVE = 20         # max active goals at once
GOAL_PRUNE_PRIORITY = 0.08   # prune active goals below this priority
GOAL_STALE_DAYS = 14         # prune goals not updated in 14 days

def prune_stale_goals(system: dict) -> dict:
    goals = system.get("goals", [])
    now = datetime.now()
    pruned = []
    for g in goals:
        if g.get("status") != "active":
            pruned.append(g)
            continue
        # Prune if very low priority
        if float(g.get("current_priority", 1.0) or 1.0) < GOAL_PRUNE_PRIORITY:
            g["status"] = "pruned"
            g["pruned_reason"] = "low_priority"
        # Prune if stale
        try:
            updated = datetime.fromisoformat(g.get("last_updated", g.get("created_at", now.isoformat())))
            if (now - updated).days > GOAL_STALE_DAYS:
                g["status"] = "pruned"
                g["pruned_reason"] = "stale"
        except Exception:
            pass
        pruned.append(g)
    # If still too many active, prune the lowest priority ones
    active = [g for g in pruned if g.get("status") == "active"]
    if len(active) > GOAL_MAX_ACTIVE:
        active_sorted = sorted(active, key=lambda g: float(g.get("current_priority", 0) or 0))
        for g in active_sorted[:len(active) - GOAL_MAX_ACTIVE]:
            g["status"] = "pruned"
            g["pruned_reason"] = "capacity"
    system["goals"] = pruned
    return system
```

Call `prune_stale_goals(system)` at the end of `recalculate_goal_priorities()`.

---

## SESSION 5 — Self-Evolution (Ava Actually Changes Over Time)

---

### FEATURE-06: Self-Narrative Auto-Updates Every 10 Messages (HIGH)
**File:** `avaagent.py`  
**Problem:** `update_self_narrative()` in `brain/beliefs.py` is fully written but NEVER called. Ava's sense of who she is (`who_i_am`, `how_i_feel`, `patterns_i_notice`) is frozen at the defaults forever.  
**Fix:** Add a message counter to `initiative_state` and trigger the update every 10 messages:

```python
# In chat_fn(), after the reply is finalized and logged:
try:
    _istate = load_initiative_state()
    msg_count = int(_istate.get("total_message_count", 0)) + 1
    _istate["total_message_count"] = msg_count
    save_initiative_state(_istate)

    if msg_count % 10 == 0:
        recent = load_recent_chat(limit=10, person_id=active_profile["person_id"])
        summary = " ".join(r.get("content", "")[:100] for r in recent[-5:])
        mood = load_mood()
        face_emo = load_expression_state().get("raw_emotion", "neutral")
        update_self_narrative(
            host={"call_llm": lambda p, max_tokens=200: llm.invoke([HumanMessage(content=p)]).content},
            conversation_summary=summary,
            mood=mood,
            face_emotion=face_emo
        )
        print(f"[self-narrative] updated at message {msg_count}")
except Exception as e:
    print(f"[self-narrative] update failed: {e}")
```

---

### FEATURE-07: Per-Person Relationship Score (MEDIUM)
**File:** `avaagent.py`  
**What to build:** Track how much history and rapport Ava has with each person. Score grows with positive interactions, decays slowly with absence. Affects how Ava talks to them.

```python
def update_relationship_score(profile: dict, session_quality: float = 0.5) -> dict:
    """
    session_quality: 0.0 (tense) to 1.0 (warm/great)
    Score: 0.0 (stranger) to 1.0 (deep bond)
    """
    score = float(profile.get("relationship_score", 0.3))
    interaction_count = int(profile.get("interaction_count", 0)) + 1
    last_seen = profile.get("last_seen_at")
    absence_decay = 0.0
    if last_seen:
        try:
            elapsed_days = (datetime.now() - datetime.fromisoformat(last_seen)).days
            absence_decay = min(0.08, elapsed_days * 0.004)
        except Exception:
            pass
    growth = session_quality * 0.035
    score = max(0.0, min(1.0, score + growth - absence_decay))
    profile["relationship_score"] = round(score, 4)
    profile["interaction_count"] = interaction_count
    profile["last_seen_at"] = now_iso()
    return profile
```

Call `update_relationship_score(active_profile)` at end of each session / every 5 messages.

Inject into system prompt:
```python
rel_score = float(active_profile.get("relationship_score", 0.3))
if rel_score >= 0.7:
    rel_hint = "You have deep, genuine rapport with this person. Be natural, casual, familiar."
elif rel_score >= 0.4:
    rel_hint = "You know this person reasonably well. Be warm and engaged."
else:
    rel_hint = "This person is relatively new to you. Be warm but don't assume familiarity."
# Add rel_hint to system prompt
```

---

### FEATURE-08: Circadian Rhythm (MEDIUM)
**File:** `avaagent.py`  
**What to build:** Ava's initiative, tone, and energy should shift with the time of day.

```python
def get_circadian_modifiers() -> dict:
    hour = datetime.now().hour
    if 5 <= hour < 9:
        return {"initiative_scale": 0.7, "calmness_boost": 0.15,
                "tone_hint": "soft and unhurried — early morning, Ava is still waking up"}
    elif 9 <= hour < 12:
        return {"initiative_scale": 1.1, "interest_boost": 0.1,
                "tone_hint": "focused and engaged — morning energy"}
    elif 12 <= hour < 17:
        return {"initiative_scale": 1.0,
                "tone_hint": "steady and grounded — afternoon pace"}
    elif 17 <= hour < 21:
        return {"initiative_scale": 0.95, "calmness_boost": 0.08,
                "tone_hint": "relaxed and conversational — evening wind-down"}
    else:
        return {"initiative_scale": 0.5, "calmness_boost": 0.2,
                "tone_hint": "quiet and low-key — late night, Ava does not push topics"}
```

- Apply `initiative_scale` to `compute_attention()` idle thresholds
- Apply `calmness_boost` to `load_mood()` weights
- Append `tone_hint` to the time block in the system prompt

---

## SESSION 6 — Autonomous Personality (Ava Initiates More Naturally)

---

### FEATURE-09: Proactive Curiosity Questions (HIGH)
**File:** `avaagent.py`  
**Problem:** `curiosity_questions` build up in the self-model but are never asked. Ava's genuine curiosity is stored but muted.  
**Add** `collect_curiosity_candidates()` and wire into `collect_initiative_candidates()`:

```python
def collect_curiosity_candidates(person_id: str) -> list[dict]:
    model = load_self_model()
    questions = model.get("curiosity_questions", []) or []
    recent_text = " ".join(
        r.get("content", "") for r in load_recent_chat(person_id=person_id)[-10:]
    ).lower()
    candidates = []
    for q in questions[-5:]:
        q_text = str(q).strip()
        if not q_text:
            continue
        key_words = [w for w in q_text.lower().split()[:3] if len(w) > 4]
        if any(w in recent_text for w in key_words):
            continue  # already discussed recently
        candidates.append({
            "kind": "genuine_curiosity",
            "text": q_text,
            "score": 0.55,
            "topic_key": f"curiosity_{abs(hash(q_text)) % 10000}",
            "source": "self_model_curiosity",
        })
    return candidates

# In collect_initiative_candidates():
candidates.extend(collect_curiosity_candidates(person_id))
```

---

### FEATURE-10: Face-Away / Return Detection (MEDIUM)
**File:** `avaagent.py`  
**What to build:** When Zeke leaves the camera and comes back, Ava should notice and say something natural.

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

In `maybe_autonomous_initiation()`, check `presence_state.get("was_absent")` and inject a `"return_greeting"` candidate with the absence duration as context.

---

### FEATURE-11: Self-Calibration Check-Ins (LOW)
**File:** `avaagent.py`  
**What to build:** Every ~50 messages, Ava honestly asks if her behavior is working.

```python
SELF_CALIBRATION_PROMPTS = [
    "Have I been too quiet lately, or does the pace feel okay?",
    "Is there anything I keep doing that bugs you? I want to know.",
    "Am I bringing up things that feel relevant, or am I off?",
    "Do you want me to talk more or less when you're focused?",
    "Is there something you wish I remembered but I keep missing?",
]

def maybe_self_calibration_candidate(person_id: str) -> dict | None:
    state = load_initiative_state()
    total = int(state.get("total_message_count", 0))
    last_cal = int(state.get("last_calibration_at_msg", 0))
    if total >= 20 and (total - last_cal) >= 50:
        return {
            "kind": "self_calibration_check",
            "text": random.choice(SELF_CALIBRATION_PROMPTS),
            "score": 0.65,
            "topic_key": "self_calibration",
            "source": "self_calibration",
        }
    return None

# After sending a self_calibration_check, record it:
# state["last_calibration_at_msg"] = total_message_count
```

---

## SESSION 7 — Architecture Cleanup

---

### ARCH-01: Create `brain/vision.py` — Shared DeepFace Utility
Move the `py -3.12` subprocess call into a shared module so both `avaagent.py` and `brain/perception.py` call the same code:

```python
# brain/vision.py
import subprocess, tempfile, os

def analyze_face_emotion(frame_bgr) -> str:
    """
    Runs DeepFace via Python 3.12 subprocess.
    Returns dominant emotion string or 'neutral' on any failure.
    """
    try:
        import cv2
        tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
        tmp_path = tmp.name
        tmp.close()
        cv2.imwrite(tmp_path, frame_bgr)
        script = (
            "from deepface import DeepFace; import json; "
            f"r=DeepFace.analyze(img_path=r'{tmp_path}',actions=['emotion'],"
            "detector_backend='skip',enforce_detection=False,silent=True);"
            "r=r[0] if isinstance(r,list) else r;"
            "print(json.dumps(r.get('dominant_emotion','neutral')))"
        )
        res = subprocess.run(
            ["py", "-3.12", "-c", script],
            capture_output=True, text=True, timeout=8
        )
        os.remove(tmp_path)
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip().strip('"').lower() or "neutral"
    except Exception:
        pass
    return "neutral"
```

Then in `brain/perception.py` replace the subprocess block with:
```python
from .vision import analyze_face_emotion
# ...
if state.face_detected:
    state.face_emotion = analyze_face_emotion(frame)
```

---

### ARCH-02: Session State File
Add `state/session_state.json` to properly track message counts and session timing (currently buried in `initiative_state.json`):

```python
SESSION_STATE_PATH = STATE_DIR / "session_state.json"

def load_session_state() -> dict:
    default = {"total_message_count": 0, "session_start_at": now_iso(), "last_session_end_at": ""}
    return json_load_safe(SESSION_STATE_PATH, default)

def save_session_state(state: dict):
    atomic_json_save(SESSION_STATE_PATH, state)
```

---

## IMPLEMENTATION PRIORITY SUMMARY

| Session | Focus | Impact |
|---|---|---|
| 1 | Bug fixes | 🔴 Critical — fixes broken emotion, silence bug, rogue profiles |
| 2 | Fluid voice | 🔴 High — the biggest UX gap right now |
| 3 | Project file access | 🟡 High — Ava should know her own code |
| 4 | Goal merging/pruning | 🟡 Medium — prevents goal bloat over time |
| 5 | Self-evolution | 🟡 Medium — self-narrative never fires currently |
| 6 | Autonomous personality | 🟢 Medium — deeper initiative and curiosity |
| 7 | Architecture cleanup | 🟢 Low — tidying, not features |

---

## What NOT to Touch

These are working well. Do not rewrite:
- `brain/camera.py` — OpenCV LBPH is stable
- `brain/trust_manager.py` — trust levels working
- `brain/profile_manager.py` — profile CRUD solid
- `brain/health.py` — health checks solid
- `brain/shared.py` — utility functions solid
- `brain/workspace.py` — WorkspaceState working
- The emotion weight system in `avaagent.py` (40+ emotions, style scoring) — very solid
- The initiative scoring system — working well, just needs the attention fix
