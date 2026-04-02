# Ava Agent v2 — Development Roadmap
**Last updated:** April 2, 2026  
**Repo:** `Tzeke000/Ava-Agent-v2` (public)  
**Based on:** Full repo audit + roadmap planning session

---

## Vision: JARVIS, But As Human-Like As Possible

Ava's technical foundation is already strong. The gap between "impressive AI" and "feels like a person who actually knows you" comes down to **continuity** — does she remember what you told her is coming, bring it up at the right moment, and connect past threads to the present? That's what this roadmap builds toward.

---

## Current Strengths (What's Already Working)

- ✅ Rich 27-emotion + style blend system with circadian modifiers
- ✅ Meta-controller with modes, outcome learning, drive normalization
- ✅ Goal system + operational goals shaping every response
- ✅ Initiative / autonomy engine (camera-triggered + attention-gated)
- ✅ Self-reflection + self-narrative (live via `atexit` + session milestones)
- ✅ Vector memory (ChromaDB) + person profiles with trust levels
- ✅ Camera + visual pattern detection + transition recognition
- ✅ Stage 7 trust gate + per-person persona tones
- ✅ `ava_core/` identity files (IDENTITY.md, SOUL.md, USER.md) versioned and auto-updating
- ✅ `append_to_user_file` wired — Ava learns facts about Zeke and writes them to USER.md

---

## The 8 Missing "Human-Like Continuity" Pieces

These are the real gaps between what Ava is now and what she needs to become.

| Priority | Feature | Why It Matters | Status |
|---|---|---|---|
| 1 | **Prospective Memory / Commitments Calendar** | Tracks open loops ("John has football game tomorrow") and turns them into natural follow-ups | ❌ Not present |
| 2 | **Event Extraction** | Auto-detects dates, future events, promises from conversation ("tomorrow", "next week", "my game is Friday") | ⚠️ Partial / weak |
| 3 | **Social Timing Intelligence** | Knows when to bring something up — too soon / too late / gentle reminder window | ❌ Not present |
| 4 | **Relationship Continuity / Thread Tracking** | Connects "you were stressed about work Tuesday" to "you seem more relaxed now" — not just profile notes but active threads | ⚠️ Partial (profiles exist) |
| 5 | **Richer Memory Writing** | Memories written with emotional tone, context, future implications, and relationship impact — not just text dumps | ⚠️ Improving but incomplete |
| 6 | **Mid-Session Narrative Updates** | `update_self_narrative` fires at shutdown — needs a mid-session trigger too (every 10 messages, or on significant emotional event) | ⚠️ Partially live |
| 7 | **Life Model / World Model** | Understands Zeke's recurring activities, stress cycles, goals in progress, family/friends rhythm over time | ⚠️ Very early stage |
| 8 | **Debug Panel in UI** | Current mood, meta mode, active goal, last reflection visible at a glance during development | ❌ Not present |

---

## Phase 1 — Stability & Polish (1–2 days)

### P1-01 — Fix Gradio Chatbot Format Warning

Gradio's `gr.Chatbot` expects `type="messages"` format (list of dicts with `role`/`content`) in newer versions, but may still receive tuples in some paths. Audit all `chat_fn`, `voice_fn`, and `camera_tick_fn` return paths to ensure they always return proper message dicts, never tuples.

Check: `gr.Chatbot(type="messages")` — if not set, add it. Then verify `_sync_canonical_history()` and `_get_canonical_history()` always return `[{"role": ..., "content": ...}]` format.

### P1-02 — Add Debug Panel to UI

Add a collapsible row at the bottom of the Gradio UI showing:
- Current meta mode + meta state
- Active operational goal + strength
- Last self-narrative snapshot (who_i_am, how_i_feel)
- Last reflection summary + importance score
- Health state (overall + degraded_mode)
- Relationship score for active person

This is a development-only quality-of-life feature that makes tuning the system dramatically easier. Four `gr.Textbox` components wired to a refresh button. Low effort, high payoff.

### P1-03 — Untrack Legacy `.tmp` Files

Two `.tmp` files are still tracked in git from before `.gitignore` was updated:
```
git rm --cached "memory/self reflection/self_model.json.7wfk1g__.tmp"
git rm --cached "memory/self reflection/self_model.json.mjr0vlog.tmp"
git commit -m "chore: untrack legacy .tmp files"
```

---

## Phase 2 — Prospective Memory / Calendar System (3–5 days)
### The #1 Missing Feature

This is the single biggest upgrade that will make Ava feel dramatically more human-like. Right now Ava has excellent memory of the past but zero awareness of the future. She can't say "hey, didn't you say John's football game was today?" — and that's exactly the kind of thing that separates a real companion from a chatbot.

### P2-01 — Create `brain/prospective.py`

New module. Stores and manages time-bound memory items.

**Event object schema:**
```python
{
    "id": "uuid",
    "person_id": "zeke",
    "event_text": "John has a football game",
    "due_date": "2026-04-05",          # ISO date or datetime
    "due_description": "tomorrow",      # original phrasing
    "trigger": "person_returns",        # "person_returns" | "time_based" | "manual"
    "prompt_template": "Hey, didn't you say {event_text} was {due_description}? How did it go?",
    "status": "pending",                # "pending" | "triggered" | "dismissed" | "expired"
    "created_at": "2026-04-02T14:30:00",
    "triggered_at": null,
    "source_turn": 42,                  # which conversation turn created it
    "confidence": 0.88,                 # how confident extraction was
}
```

**Key functions:**
- `save_prospective_event(event)` — persist to `state/prospective_memory.json`
- `load_pending_events(person_id)` — load all pending events for a person
- `get_due_events(person_id, now)` — returns events that are now due or past-due
- `mark_triggered(event_id)` — mark event as triggered so it doesn't fire again
- `expire_old_events(days=7)` — auto-clean events older than N days with no trigger

### P2-02 — Create `brain/event_extractor.py`

Scans conversation turns for time-bound references and creates prospective events.

**Detection approach (two-layer):**

Layer 1 — regex fast-pass:
```python
TEMPORAL_PATTERNS = [
    r"\btomorrow\b",
    r"\btonight\b", 
    r"\bnext\s+(week|monday|tuesday|...|weekend)\b",
    r"\bthis\s+(friday|saturday|...)\b",
    r"\bon\s+(monday|tuesday|...)\b",
    r"\b(january|february|...)\s+\d{1,2}\b",
    r"\bin\s+\d+\s+(days?|weeks?|hours?)\b",
    r"\b(game|match|appointment|meeting|birthday|interview|deadline|exam|surgery|trip)\b",
]
```

Layer 2 — LLM extraction pass (only if Layer 1 hits):
```
"Does this message mention a future event, appointment, or commitment?
If yes, extract: event description, time reference, person involved.
Return JSON or null."
```

**Integration point:** Call from `finalize_ava_turn()` on every user message — lightweight because Layer 1 is just regex and Layer 2 only fires on hits.

### P2-03 — Wire Prospective Events Into Initiative Candidates

In `collect_initiative_candidates()`, add a new check:
```python
# Prospective memory follow-ups
due_events = get_due_events(person_id, now=datetime.now())
for event in due_events[:2]:  # max 2 at a time
    candidates.append({
        "kind": "prospective_followup",
        "text": event["prompt_template"].format(**event),
        "topic_key": f"prospective_{event['id']}",
        "base_score": 0.88,  # high — these are deliberate commitments
        "memory_importance": 0.82,
        "event_id": event["id"],  # so we can mark_triggered after firing
    })
```

Also add `"prospective_followup"` to `INITIATIVE_KIND_COOLDOWNS` (0 cooldown — fire once and mark triggered, never again).

### P2-04 — Add to `CAMERA_AUTONOMOUS_ALLOWED_KINDS`

```python
CAMERA_AUTONOMOUS_ALLOWED_KINDS.add("prospective_followup")
```

Prospective follow-ups should be allowed to fire when the person returns to camera — that's exactly the right trigger moment.

### P2-05 — Handle Trigger in `maybe_autonomous_initiation`

After a `prospective_followup` candidate fires successfully, call `mark_triggered(event["event_id"])` so it never repeats.

---

## Phase 3 — Social Timing + Relationship Threading (1 week)

### P3-01 — Social Timing Rules for Prospective Events

Not every due event should be mentioned immediately. Add timing metadata to events:

```python
{
    "cooldown_before_hours": 12,   # don't mention before N hours before due date
    "expires_after_hours": 72,     # stop trying after N hours past due date
    "mention_window": "same_day",  # "before" | "same_day" | "after" | "any"
}
```

`get_due_events()` respects these windows — so a birthday reminder fires the morning of, not 3 days early. A football game follow-up fires when the person returns the same day or next day, not a week later.

### P3-02 — Relationship Thread Tracking

Add a `threads` field to person profiles — active emotional/situational threads:

```python
"threads": [
    {
        "id": "uuid",
        "topic": "job stress",
        "first_mentioned": "2026-03-28T...",
        "last_mentioned": "2026-04-01T...",
        "emotion": "anxious",
        "resolved": false,
        "notes": "stressed about a deadline at work"
    }
]
```

These threads get created/updated by `reflect_on_last_reply()` when it detects emotionally significant topics. When the same person returns, Ava checks unresolved threads and can naturally reference them: "You seemed stressed about that deadline — did it work out?"

This is the mechanism behind the "connected" feeling. Not a graph — just a rolling list of unresolved emotional situations per person.

### P3-03 — Conversation Cadence Tracking

Add to profiles:
```python
"cadence": {
    "avg_days_between_sessions": 1.2,
    "longest_gap_days": 7,
    "total_sessions": 23,
    "last_gap_days": 0,
}
```

When a person returns after an unusually long gap, Ava notices: "It's been a while — everything okay?" When they return right on schedule, she doesn't make it weird.

---

## Phase 4 — Richer Memory Writing & Narrative Continuity (Ongoing)

### P4-01 — Emotionally-Toned Memory Writing

Current memory entries are factual text. Add emotional + relational metadata at write time:

```python
{
    "text": "Zeke mentioned he's been working late on a project deadline",
    "emotional_tone": "stressed",
    "person_impact": "high",          # how much this matters to their life
    "future_implications": "may need support or check-ins over next few days",
    "relationship_relevance": 0.85,   # weight for relationship context
    "tags": ["work", "stress", "project"]
}
```

`maybe_autoremember()` already calls the LLM for importance scoring — extend that same call to extract emotional tone and future implications.

### P4-02 — Mid-Session Narrative Updates

`update_self_narrative()` currently fires at session end via `atexit`. Add a mid-session trigger:

```python
# In finalize_ava_turn():
sess = load_session_state()
count = int(sess.get("total_message_count", 0))
if count > 0 and count % 10 == 0:   # every 10 messages
    try:
        _trigger_narrative_update_async()
    except Exception:
        pass
```

Run it in a background thread so it doesn't block the response. This means Ava's self-narrative evolves *during* long conversations, not just when she shuts down.

### P4-03 — Forward References in Self-Model

Currently `self_model.json` has `core_drives`, `behavior_patterns`, etc. Add a `pending_threads` field that mirrors the relationship threads from P3-02 but from Ava's internal perspective:

```python
"pending_threads": [
    "Zeke seemed tense about the work deadline — I want to follow up",
    "I noticed I've been initiating more than usual — should check if that's welcome"
]
```

These feed into the next conversation's prompt context and give Ava a sense of "things I was thinking about since we last talked."

---

## Phase 5 — Life Model & Emerging World Awareness (Long-term)

This phase isn't something you build directly — it emerges from the layers below it. Once Ava has:
- Prospective memory (Phase 2)
- Relationship threads (Phase 3)
- Rich emotional memory (Phase 4)
- Enough conversation history

...she'll naturally start to understand Zeke's recurring patterns: work stress cycles, creative project rhythms, who the important people in his life are and how relationships with them evolve.

The one deliberate addition here:

### P5-01 — Life Rhythm Detector

After ~50+ sessions, add a weekly analysis job (triggered by an automation or on startup once per day) that:
1. Scans the last 30 days of reflections and memory
2. Extracts recurring patterns: "Zeke is usually energized on weekends", "Work stress peaks mid-week", "Creative output spikes late at night"
3. Writes a `state/life_model.json` summary
4. Injects relevant sections into the prompt context

This is the long-term payoff of everything built before it.

---

## What NOT to Touch

These are working well — don't refactor:
- `brain/selfstate.py` — clean and correct
- `brain/output_guard.py` — tight scrubbing logic
- `brain/memory_reader.py` — robust multi-signature fallback
- `brain/initiative_sanity.py` — desaturation prevents score inflation
- `brain/profile_manager.py` — `looks_like_phrase_profile` is solid
- `brain/shared.py` — atomic save utilities
- The 27-emotion system + style blend
- The ChromaDB memory + reflection pipeline
- The `workspace.tick()` architecture
- `ava_personality.txt` — core personality is good

---

## Priority Summary

| Phase | Feature | Effort | Impact |
|---|---|---|---|
| 1, P1-01 | Gradio format fix | 🟢 Low | Medium |
| 1, P1-02 | Debug panel in UI | 🟢 Low | High (dev quality of life) |
| 1, P1-03 | Untrack .tmp files | 🟢 Trivial | Low |
| **2, P2-01** | **`brain/prospective.py`** | 🟡 Medium | **🔴 Highest** |
| **2, P2-02** | **`brain/event_extractor.py`** | 🟡 Medium | **🔴 Highest** |
| 2, P2-03 | Wire into initiative | 🟢 Low | 🔴 High |
| 3, P3-01 | Social timing rules | 🟢 Low | 🔴 High |
| 3, P3-02 | Relationship thread tracking | 🟡 Medium | High |
| 3, P3-03 | Conversation cadence | 🟢 Low | Medium |
| 4, P4-01 | Richer memory writing | 🟡 Medium | High |
| 4, P4-02 | Mid-session narrative updates | 🟢 Low | Medium |
| 4, P4-03 | Forward references in self-model | 🟢 Low | Medium |
| 5, P5-01 | Life rhythm detector | 🔴 High effort | High (long-term) |
