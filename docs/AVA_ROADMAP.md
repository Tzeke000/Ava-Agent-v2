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
**Problem:** `build_perception()` does a direct `from deepface import DeepFace` import. Python 3.14 cannot load DeepFace/TensorFlow, so this always silently falls back to `"neutral"`. Ava has been emotionally blind since v2 launched.

Note: `brain/workspace.py` already correctly sets `g["_last_perception_emotion"]` from `ws.perception.face_emotion`. The problem is purely that `perception.py` never gets a real emotion — fix this and the whole chain works.

**Fix:** Replace the DeepFace import block in `brain/perception.py` with a `py -3.12` subprocess call. Python 3.12 is at `C:\Users\Tzeke\AppData\Local\Programs\Python\Python312\`:

```python
# In brain/perception.py — replace the DeepFace try/except block with:
def _analyze_face_emotion_subprocess(frame) -> str:
    """Run DeepFace via Python 3.12 subprocess to bypass Python 3.14 incompatibility."""
    try:
        import subprocess, tempfile, os as _os, cv2 as _cv2
        tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
        tmp_path = tmp.name
        tmp.close()
        _cv2.imwrite(tmp_path, frame)
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

Then in `build_perception()`, replace any direct DeepFace call with:
```python
if state.face_detected and frame is not None:
    state.face_emotion = _analyze_face_emotion_subprocess(frame)
else:
    state.face_emotion = "neutral"
```

---

### FIX-02: `attention.py` — Silence Suppression Logic (HIGH)
**File:** `brain/attention.py`
**Problem:** `compute_attention()` returns `should_speak=False` when `seconds_since_last_message > 300`. This means Ava goes completely silent after 5 minutes of no messages, even with a face present. A 5-minute pause with a face visible is actually the best time to check in — not go quiet. Only a 30+ minute gap means the user truly stepped away.

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
**Problem:** The 3-word fallback in `extract_identity_claim()` turns normal phrases like "thats correct ava" or "yes it is" into new named profiles.

**Fix:** Remove the 3-word fallback entirely. Only explicit self-ID patterns (`"I am X"`, `"it's me X"`) should create profiles:

```python
def extract_identity_claim(text: str) -> Optional[str]:
    t = (text or "").strip()
    for pat in SELF_PATTERNS:
        m = re.search(pat, t, flags=re.I)
        if m:
            return m.group(1).strip()
    return None  # No fallback. Only "I am X" / "it's me X" creates a profile.
```

---

### FIX-04: `response.py` — Dead Duplicate Code (MEDIUM)
**File:** `brain/response.py`
**Problem:** `response.py` defines its own `scrub_visible_reply()` and `generate_autonomous_message()`. Neither is imported by `avaagent.py` — both are dead code that shadow the real versions.

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
                    elapsed = time.time() - datetime.fromisoformat(last_saved).timestamp()
                    # Up to 85% drift toward baseline per hour elapsed (max 15% per hour)
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

### FIX-07: `avaagent.py` — Increase Memory and Reflection Recall (LOW)
**File:** `avaagent.py`
**Problem:** `MEMORY_RECALL_K = 4` and `REFLECTION_RECALL_K = 4` are low. Ava misses relevant context in long-term relationships.

**Fix:**
```python
MEMORY_RECALL_K = 8       # was 4
REFLECTION_RECALL_K = 6   # was 4
```

---

## SESSION 2 — Fluid Voice / Conversation (The ChatGPT Feel)

This makes talking to Ava feel natural. Currently voice only fires when you fully stop recording — she has no idea if you paused mid-sentence or finished.

The goal: if you pause briefly mid-sentence, she waits. If you resume within ~2 seconds, she treats it as continuation. If you stop for longer, she responds. If she's mid-reply and you start talking again, she stops.

---

### FEATURE-01: Streaming Voice with Pause Detection (HIGH)

**What to build:** Replace `voice_input.stop_recording` (fires only when recording stops) with `voice_input.stream` (fires on every 500ms audio chunk). Accumulate chunks, use Whisper's VAD filter to detect real pauses vs. mid-sentence pauses.

**Step 1 — Add state constants near Whisper init:**

```python
VAD_SILENCE_THRESHOLD_MS = 800       # ms of silence = likely end of utterance
VAD_CONTINUATION_WINDOW_SECONDS = 2.0  # if speech resumes within this, it's continuation

_PARTIAL_SPEECH_BUFFER = []       # accumulated audio chunks
_LAST_SPEECH_END_TS = 0.0         # when user last stopped speaking
_AVA_SPEAKING = False             # True while Ava is generating a reply
```

**Step 2 — Add `combine_audio_chunks()` helper:**

```python
def combine_audio_chunks(chunks: list) -> str:
    """Write accumulated audio chunks to a temp file and return the path."""
    import soundfile as sf
    import numpy as np
    import tempfile
    
    arrays = []
    sample_rate = 16000
    for chunk in chunks:
        if chunk is None:
            continue
        sr, data = chunk
        if data is None or len(data) == 0:
            continue
        sample_rate = sr
        if data.dtype != np.float32:
            data = data.astype(np.float32) / np.iinfo(data.dtype).max
        arrays.append(data)
    
    if not arrays:
        return None
    
    combined = np.concatenate(arrays)
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    sf.write(tmp.name, combined, sample_rate)
    return tmp.name
```

**Step 3 — Replace `voice_fn` with a streaming version:**

```python
_voice_stream_state = {"last_partial": "", "last_end_ts": 0.0}

def voice_stream_fn(audio_chunk, history, image):
    """Called every 500ms with a new audio chunk."""
    global _PARTIAL_SPEECH_BUFFER, _LAST_SPEECH_END_TS, _AVA_SPEAKING
    
    history = _sync_canonical_history(history)
    
    # If Ava is speaking and user starts a new chunk, interrupt her
    if _AVA_SPEAKING and audio_chunk is not None:
        _AVA_SPEAKING = False
        _PARTIAL_SPEECH_BUFFER = []
        return _get_canonical_history(), None
    
    if audio_chunk is None:
        return _get_canonical_history(), None
    
    _PARTIAL_SPEECH_BUFFER.append(audio_chunk)
    
    # Transcribe current buffer with VAD to detect speech end
    combined_path = combine_audio_chunks(_PARTIAL_SPEECH_BUFFER)
    if not combined_path:
        return _get_canonical_history(), None
    
    try:
        segments, info = whisper_model.transcribe(
            combined_path,
            beam_size=3,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": VAD_SILENCE_THRESHOLD_MS}
        )
        text = " ".join(s.text for s in segments).strip()
    except Exception:
        text = ""
    finally:
        try:
            import os
            os.remove(combined_path)
        except Exception:
            pass
    
    if not text:
        return _get_canonical_history(), None
    
    now = time.time()
    
    # Check if silence detected (VAD found a clean end)
    # Use total audio duration vs speech duration as a heuristic
    total_dur = sum((c[1].shape[0] / c[0]) if c and c[1] is not None else 0 for c in _PARTIAL_SPEECH_BUFFER)
    gap_since_last = now - _LAST_SPEECH_END_TS
    
    # If we have a substantial gap since last utterance and the buffer has enough content
    speech_ended = total_dur > 0.8  # at least 800ms of audio collected
    
    if speech_ended:
        # Check if this is a continuation of recent speech
        if gap_since_last < VAD_CONTINUATION_WINDOW_SECONDS and _voice_stream_state["last_partial"]:
            # User is still going — accumulate but don't respond yet
            _voice_stream_state["last_partial"] = text
            return _get_canonical_history(), None
        
        # Real end of utterance — process it
        final_text = text
        _PARTIAL_SPEECH_BUFFER = []
        _LAST_SPEECH_END_TS = now
        _voice_stream_state["last_partial"] = ""
        
        if not final_text.strip():
            return _get_canonical_history(), None
        
        # Process the utterance (same as old voice_fn logic)
        _AVA_SPEAKING = True
        result = process_voice_utterance(final_text.strip(), history, image)
        _AVA_SPEAKING = False
        return result
    else:
        _voice_stream_state["last_partial"] = text
        _LAST_SPEECH_END_TS = now
        return _get_canonical_history(), None


def process_voice_utterance(text: str, history: list, image) -> tuple:
    """Process a completed voice utterance — same logic as old voice_fn."""
    note_user_interaction_for_initiative(text, interaction_kind="voice")
    workspace.record_user_message()
    workspace.tick(camera_manager, image, globals(), text)
    
    # ... (copy the rest of voice_fn's processing logic here, 
    #      starting from the recognize_face call through to the final return)
```

**Step 4 — Update Gradio wiring (replace stop_recording line):**

```python
# Remove this line:
# voice_input.stop_recording(voice_fn, ...)

# Replace with:
voice_input.stream(
    voice_stream_fn,
    inputs=[voice_input, chatbot, camera],
    outputs=[chatbot, voice_input],
    time_limit=30,
    stream_every=0.5
)
```

**Note on output outputs:** The streaming version returns fewer outputs to keep it fast. You can expand it to match the full output list of voice_fn after the basic version is working.

---

### FEATURE-02: Short Message Merging in Text Chat (LOW)
**File:** `avaagent.py` — `chat_fn()`
**What to build:** If the user sends a very short message (< 4 words) followed quickly by another message, merge them into one input before processing.

```python
SHORT_MESSAGE_WINDOW_SECONDS = 4.0
_PENDING_SHORT_MESSAGE = {"text": None, "ts": 0.0}

def maybe_merge_with_pending(new_text: str) -> str | None:
    """Returns merged text, original new_text, or None if holding short message."""
    global _PENDING_SHORT_MESSAGE
    now = time.time()
    
    pending = _PENDING_SHORT_MESSAGE["text"]
    pending_ts = _PENDING_SHORT_MESSAGE["ts"]
    
    # If there's a pending short message within the window, merge
    if pending and (now - pending_ts) < SHORT_MESSAGE_WINDOW_SECONDS:
        merged = pending + " " + new_text
        _PENDING_SHORT_MESSAGE = {"text": None, "ts": 0.0}
        return merged
    
    # If this is a short message, hold it
    if len(new_text.strip().split()) < 4:
        _PENDING_SHORT_MESSAGE = {"text": new_text, "ts": now}
        return None  # Don't process yet — wait for continuation
    
    # Clear any stale pending message
    _PENDING_SHORT_MESSAGE = {"text": None, "ts": 0.0}
    return new_text

# In chat_fn(), near the top after extracting clean_message:
processed_message = maybe_merge_with_pending(clean_message)
if processed_message is None:
    # Holding short message — return current history unchanged
    return _get_canonical_history(), "", ...
clean_message = processed_message
```

---

## SESSION 3 — Project File Awareness

Ava can currently read the first 12,000 chars of `avaagent.py` via a UI button, but NOT her brain modules or any other project files. She has no way to read `brain/perception.py`, `brain/beliefs.py`, etc.

---

### FEATURE-03: Ava Can See the Full AvaAgentv2 Project (HIGH)
**File:** `avaagent.py`
**What to build:** Give Ava read-only access to all files in `D:\AvaAgentv2` — her own source code, brain modules, docs, config. She should be able to list and read (but NOT write) any project file.

**Step 1 — Add constants:**

```python
PROJECT_DIR = BASE_DIR  # D:\AvaAgentv2 — already defined
MAX_PROJECT_FILE_CHARS = 15000  # generous but bounded
```

**Step 2 — Add list and read functions:**

```python
def list_project_files(subdir: str = "", limit: int = 150) -> list[str]:
    """List files in AvaAgentv2 project (read-only). Skips private dirs."""
    skip_dirs = {".git", "__pycache__", "memory", "faces", "Ava workbench", "state", "logs"}
    target = (PROJECT_DIR / subdir).resolve() if subdir else PROJECT_DIR.resolve()
    if not str(target).startswith(str(PROJECT_DIR)):
        return []
    rows = []
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
    """Read any file in AvaAgentv2 project (read-only, safe)."""
    try:
        target = (PROJECT_DIR / relative_path).resolve()
        if not str(target).startswith(str(PROJECT_DIR)):
            return "❌ Access denied — path escapes project directory."
        skip_dirs = {".git", "__pycache__", "memory", "faces"}
        if any(part in skip_dirs for part in target.parts):
            return "❌ Access denied — this directory is private."
        if not target.exists() or not target.is_file():
            return "❌ File not found."
        return target.read_text(encoding="utf-8", errors="ignore")[:max_chars]
    except Exception as e:
        return f"❌ Failed to read project file: {e}"
```

**Step 3 — Register in system prompt tools section** (in `SYSTEM_PROMPT`):

```
To list your project files:
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

**Step 4 — Wire into `process_ava_action_blocks()`:**

```python
PROJECT_BLOCK_RE = re.compile(r"```PROJECT\n(.*?)```", re.DOTALL | re.IGNORECASE)

def project_repl(match):
    block = parse_key_values(match.group(1))
    action = block.get("action", "list").strip().lower()
    if action == "list":
        subdir = block.get("subdir", "").strip()
        files = list_project_files(subdir=subdir)
        actions.append(f"[project files]\n" + "\n".join(files))
    elif action == "read":
        path = block.get("path", "").strip()
        content = read_project_file(path)
        actions.append(f"[project file: {path}]\n{content}")
    return ""

cleaned = PROJECT_BLOCK_RE.sub(project_repl, cleaned)
```

**Step 5 — Upgrade the existing `read_code_fn` button** to read any project file path, not just `avaagent.py`. Or add a new "Read Project File" text field + button to the UI.

---

## SESSION 4 — Goal Intelligence (Merge + Prune)

---

### FEATURE-04: Semantic Goal Deduplication / Merging (HIGH)
**File:** `avaagent.py`
**Problem:** Only exact text matches are deduplicated in `add_structured_goal()`. Goals like "track meaningful memories", "remember important things about the user", and "store context from conversations" are all kept separate even though they mean the same thing. `GOAL_MAX_ACTIVE = 48` means this can get very bloated.

**What to build:** Before adding a new goal, check semantic similarity using Jaccard overlap. If similarity ≥ 0.52, merge instead of creating:

```python
def _goal_jaccard_similarity(text_a: str, text_b: str) -> float:
    """Fast word-overlap similarity. No external model needed."""
    tokens_a = set(re.findall(r"[a-z]+", text_a.lower()))
    tokens_b = set(re.findall(r"[a-z]+", text_b.lower()))
    if not tokens_a or not tokens_b:
        return 0.0
    return len(tokens_a & tokens_b) / len(tokens_a | tokens_b)

def _find_similar_goal(new_text: str, goals: list[dict], threshold: float = 0.52) -> dict | None:
    """Return the most similar active goal above threshold, else None."""
    best = None
    best_score = 0.0
    for g in goals:
        if g.get("status", "active") != "active":
            continue
        score = _goal_jaccard_similarity(new_text, g.get("text", ""))
        if score > best_score and score >= threshold:
            best_score = score
            best = g
    return best
```

Update `add_structured_goal()` — after the exact match check, add:

```python
# NEW: Semantic similarity check
active_goals = [g for g in system.get("goals", []) if g.get("status", "active") == "active"]
similar = _find_similar_goal(goal_text, active_goals, threshold=0.52)
if similar:
    # Merge: boost existing goal's importance slightly, record this text as an alias
    similar["importance"] = min(1.0, float(similar.get("importance", 0.6)) + 0.05)
    similar["last_updated"] = now_iso()
    aliases = similar.get("text_aliases", [])
    if goal_text not in aliases:
        aliases.append(goal_text)
    similar["text_aliases"] = aliases[-5:]
    save_goal_system(recalculate_goal_priorities(system))
    print(f"[goals] Merged '{goal_text}' into: '{similar['text']}'")
    return similar
```

---

### FEATURE-05: Goal Auto-Pruning (MEDIUM)
**File:** `avaagent.py`
**Problem:** Completed, stale, or very low-priority goals accumulate. With `GOAL_MAX_ACTIVE = 48`, the list gets long before being capped.

**Add** a pruning step called at the end of `recalculate_goal_priorities()`:

```python
GOAL_PRUNE_PRIORITY = 0.08   # prune active goals below this priority
GOAL_STALE_DAYS = 14         # prune goals not updated in 14 days
GOAL_MAX_HEALTHY = 20        # soft target for active goal count

def prune_stale_goals(system: dict) -> dict:
    goals = system.get("goals", [])
    now = datetime.now()
    for g in goals:
        if g.get("status") != "active":
            continue
        # Prune very low priority
        if float(g.get("current_priority", 1.0) or 1.0) < GOAL_PRUNE_PRIORITY:
            g["status"] = "pruned"
            g["pruned_reason"] = "low_priority"
            continue
        # Prune if stale
        try:
            updated = datetime.fromisoformat(g.get("last_updated", g.get("created_at", now.isoformat())))
            if (now - updated).days > GOAL_STALE_DAYS:
                g["status"] = "pruned"
                g["pruned_reason"] = "stale"
                continue
        except Exception:
            pass
    # If still over soft target, prune lowest priority
    active = [g for g in goals if g.get("status") == "active"]
    if len(active) > GOAL_MAX_HEALTHY:
        active_sorted = sorted(active, key=lambda g: float(g.get("current_priority", 0) or 0))
        for g in active_sorted[:len(active) - GOAL_MAX_HEALTHY]:
            g["status"] = "pruned"
            g["pruned_reason"] = "capacity"
    system["goals"] = goals
    return system

# In recalculate_goal_priorities(), add at the end before the return:
system = prune_stale_goals(system)
```

---

## SESSION 5 — Self-Evolution (Ava Actually Changes Over Time)

Note: `update_self_narrative()` IS already being called every 10 messages in `chat_fn`. These features add the things that are NOT wired yet.

---

### FEATURE-06: Wire Curiosity Questions Into Initiative (HIGH)
**File:** `avaagent.py`
**Problem:** `curiosity_questions` build up in the self-model but are never fed into `collect_initiative_candidates()`. Ava's genuine curiosity is stored and never asked.

**Add** a candidate collector and wire it into the initiative pipeline:

```python
def collect_curiosity_candidates(person_id: str) -> list[dict]:
    """Turn self_model curiosity_questions into initiative candidates."""
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
        # Skip if already discussed recently
        key_words = [w for w in q_text.lower().split()[:3] if len(w) > 4]
        if any(w in recent_text for w in key_words):
            continue
        candidates.append({
            "kind": "genuine_curiosity",
            "text": q_text,
            "score": 0.55,
            "topic_key": f"curiosity_{abs(hash(q_text)) % 10000}",
            "source": "self_model_curiosity",
            "base_score": 0.55,
            "memory_importance": 0.55,
        })
    return candidates
```

In `collect_initiative_candidates()`, add near the end before returning:
```python
candidates.extend(collect_curiosity_candidates(person_id))
```

Also add `"genuine_curiosity"` to `CAMERA_AUTONOMOUS_ALLOWED_KINDS`.

---

### FEATURE-07: Per-Person Relationship Score (MEDIUM)
**File:** `avaagent.py`
**What to build:** Track how much history and rapport Ava has with each person. Affects how she talks to them.

```python
def update_relationship_score(profile: dict, session_quality: float = 0.5) -> dict:
    """
    session_quality: 0.0 (tense) to 1.0 (warm/great)
    Score: 0.0 (stranger) to 1.0 (deep bond)
    """
    score = float(profile.get("relationship_score", 0.3))
    interaction_count = int(profile.get("interaction_count", 0)) + 1
    last_seen = profile.get("last_seen")
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
    return profile
```

Call `update_relationship_score(active_profile)` in `finalize_ava_turn()`.

Inject into system prompt in `build_prompt()`:
```python
rel_score = float(active_profile.get("relationship_score", 0.3))
if rel_score >= 0.7:
    rel_hint = "You have deep, genuine rapport with this person. Be natural, casual, familiar."
elif rel_score >= 0.4:
    rel_hint = "You know this person reasonably well. Be warm and engaged."
else:
    rel_hint = "This person is relatively new to you. Be warm but don't assume familiarity."
# Append rel_hint to the ACTIVE PERSON section of the prompt
```

---

### FEATURE-08: Face-Away / Return Detection (MEDIUM)
**File:** `avaagent.py`
**What to build:** When the user leaves the camera and comes back, Ava should notice.

```python
_PRESENCE_CONTINUITY = {"face_visible": False, "face_left_at": None, "was_absent": False, "absent_duration_seconds": 0}

def update_presence_continuity(face_visible: bool) -> dict:
    global _PRESENCE_CONTINUITY
    now_str = now_iso()
    was_visible = _PRESENCE_CONTINUITY.get("face_visible", False)
    
    if was_visible and not face_visible:
        _PRESENCE_CONTINUITY["face_left_at"] = now_str
        _PRESENCE_CONTINUITY["was_absent"] = False
    elif not was_visible and face_visible:
        left_at = _PRESENCE_CONTINUITY.get("face_left_at")
        if left_at:
            try:
                gone = (datetime.fromisoformat(now_str) - datetime.fromisoformat(left_at)).total_seconds()
                _PRESENCE_CONTINUITY["was_absent"] = gone > 30
                _PRESENCE_CONTINUITY["absent_duration_seconds"] = round(gone)
            except Exception:
                _PRESENCE_CONTINUITY["was_absent"] = False
        _PRESENCE_CONTINUITY["face_left_at"] = None
    
    _PRESENCE_CONTINUITY["face_visible"] = face_visible
    return dict(_PRESENCE_CONTINUITY)
```

Call `update_presence_continuity(face_visible)` at the top of `camera_tick_fn()`.

In `collect_initiative_candidates()`, add:
```python
if _PRESENCE_CONTINUITY.get("was_absent"):
    duration = _PRESENCE_CONTINUITY.get("absent_duration_seconds", 60)
    absence_text = f"You just came back — were you away for a bit?" if duration < 600 else "You're back — it's been a while."
    candidates.append({
        "kind": "return_greeting",
        "text": absence_text,
        "score": 0.88,
        "topic_key": "return_greeting",
        "base_score": 0.88,
        "memory_importance": 0.75,
    })
    _PRESENCE_CONTINUITY["was_absent"] = False  # consume the event
```

Add `"return_greeting"` to `CAMERA_AUTONOMOUS_ALLOWED_KINDS`.

---

### FEATURE-09: Circadian Tone Shifts (MEDIUM)
**File:** `avaagent.py`
**What to build:** Ava's initiative threshold and tone should shift with time of day.

```python
def get_circadian_modifiers() -> dict:
    hour = datetime.now().hour
    if 5 <= hour < 9:
        return {"initiative_scale": 0.7, "tone_hint": "soft and unhurried — early morning"}
    elif 9 <= hour < 12:
        return {"initiative_scale": 1.1, "tone_hint": "focused and engaged — morning energy"}
    elif 12 <= hour < 17:
        return {"initiative_scale": 1.0, "tone_hint": "steady and grounded — afternoon"}
    elif 17 <= hour < 21:
        return {"initiative_scale": 0.95, "tone_hint": "relaxed and conversational — evening"}
    else:
        return {"initiative_scale": 0.5, "tone_hint": "quiet and low-key — late night, don't push topics"}
```

- Apply `initiative_scale` to `INITIATIVE_INACTIVITY_SECONDS` (multiply threshold by scale)
- Append `tone_hint` to the TIME section of the system prompt in `build_prompt()`

---

### FEATURE-10: Self-Calibration Check-Ins (LOW)
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

def maybe_self_calibration_candidate() -> dict | None:
    state = load_initiative_state()
    total = int(state.get("total_message_count", 0))
    last_cal = int(state.get("last_calibration_at_msg", 0))
    if total >= 20 and (total - last_cal) >= 50:
        return {
            "kind": "self_calibration",
            "text": random.choice(SELF_CALIBRATION_PROMPTS),
            "score": 0.72,
            "topic_key": "self_calibration",
            "base_score": 0.72,
            "memory_importance": 0.70,
        }
    return None
```

Wire into `collect_initiative_candidates()` and add `"self_calibration"` to `CAMERA_AUTONOMOUS_ALLOWED_KINDS`. When fired, record `state["last_calibration_at_msg"] = total_message_count` and save.

---

## SESSION 6 — Architecture Cleanup

---

### ARCH-01: Create `brain/vision.py` — Shared DeepFace Utility
Move the `py -3.12` subprocess call from FIX-01 into a standalone shared module:

```python
# brain/vision.py
import subprocess, tempfile, os

PYTHON312_CMD = "py"  # "py -3.12" or direct path if needed

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
            [PYTHON312_CMD, "-3.12", "-c", script],
            capture_output=True, text=True, timeout=8
        )
        os.remove(tmp_path)
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip().strip('"').lower() or "neutral"
    except Exception:
        pass
    return "neutral"
```

Then `brain/perception.py` imports from `.vision`:
```python
from .vision import analyze_face_emotion
# In build_perception():
if state.face_detected and frame is not None:
    state.face_emotion = analyze_face_emotion(frame)
```

---

### ARCH-02: Session State File
Currently `initiative_state.json` holds session counters. Add a dedicated `state/session_state.json`:

```python
SESSION_STATE_PATH = STATE_DIR / "session_state.json"

def default_session_state() -> dict:
    return {
        "total_message_count": 0,
        "session_start_at": now_iso(),
        "last_session_end_at": "",
        "last_calibration_at_msg": 0,
    }

def load_session_state() -> dict:
    if SESSION_STATE_PATH.exists():
        try:
            base = default_session_state()
            base.update(json.loads(SESSION_STATE_PATH.read_text(encoding="utf-8")))
            return base
        except Exception:
            pass
    return default_session_state()

def save_session_state(state: dict):
    SESSION_STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")
```

Increment `total_message_count` in `finalize_ava_turn()` and use it to drive Feature-10 (self-calibration).

---

## IMPLEMENTATION PRIORITY SUMMARY

| Session | Focus | Impact |
|---|---|---|
| 1 | Bug fixes | 🔴 Critical — fixes broken emotion, silence bug, rogue profiles |
| 2 | Fluid voice | 🔴 High — biggest UX gap |
| 3 | Project file access | 🟡 High — Ava should know her own code |
| 4 | Goal merging/pruning | 🟡 Medium — prevents goal bloat over time |
| 5 | Self-evolution / personality | 🟡 Medium — wires curiosity, relationship scores, circadian |
| 6 | Architecture cleanup | 🟢 Low — tidying |

---

## What NOT to Touch

These are working well. Do not rewrite:
- `brain/camera.py` — OpenCV LBPH face recognition, solid
- `brain/trust_manager.py` — trust levels working correctly
- `brain/profile_manager.py` — profile CRUD solid
- `brain/health.py` — health checks solid
- `brain/shared.py` — utility functions solid
- `brain/workspace.py` — WorkspaceState tick working, correctly sets `_last_perception_emotion`
- `brain/beliefs.py` — `update_self_narrative()` is wired and firing every 10 messages
- The emotion weight system in `avaagent.py` (27 emotions, 7 styles, style scoring) — very solid
- The initiative scoring/gate system — working well, just needs the attention fix and curiosity wiring
- The reflection system — auto-reflection, promotion to memory, self-model updates all working
