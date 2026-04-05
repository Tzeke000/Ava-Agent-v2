# Ava Agent v2 — Master Vision, Roadmap, and History

**Last updated:** April 5, 2026  
**Repo:** `Tzeke000/Ava-Agent-v2`

---

## Short Summary

Ava is being built toward one core goal: **a JARVIS-like assistant that feels as human as possible without losing safety, continuity, or grounding**.

That means Ava should not just answer prompts. She should:
- hold full natural voice conversations
- notice who is present and what is happening
- remember people, promises, routines, and unfinished threads
- update her internal state over time instead of resetting every turn
- reflect on what worked, what failed, and what matters
- choose when to speak, when to wait, and when to ask
- feel coherent across chat, voice, camera, memory, and self-modeling

The repo already has a strong base: runtime orchestration, initiative, trust-aware behavior, memory/profile systems, identity files, and a major perception sprint through Better Eyes Phase 11. What still separates Ava from “impressive AI” and “someone who feels present, continuous, and socially aware” is the next layer of continuity: memory importance, pattern learning, proactive timing, self-tests, safe self-improvement, reflection, and configuration/tuning.

---

## In-Depth Vision

The long-term target is not just “an AI with features.” The target is an **ongoing agent** that behaves like a socially aware, memory-bearing, emotionally calibrated presence.

A human-like Ava should eventually be able to:

### 1. Converse naturally in voice
Ava should be able to carry spoken conversations fluidly, with less “request/response dead air” and more natural timing. She should support interruption, clarification, brief acknowledgments, and continuity across multiple spoken turns instead of feeling like each voice exchange is a fresh reset.

### 2. Maintain continuity across time
Ava should remember what was said yesterday, what matters tomorrow, and what was emotionally significant last week. She should bring things up at the right time, not just retrieve them when directly asked.

### 3. Build a social model of the user and others
Ava should recognize recurring people, understand their emotional and relational patterns, and adapt her behavior accordingly. She should know not only who someone is, but how interactions with them tend to feel and evolve.

### 4. Build a life model / world model
Ava should gradually understand the user’s routines, goals in progress, stress cycles, important relationships, ongoing projects, and unfinished loops. This is what makes conversation feel situated rather than generic.

### 5. Maintain an internal self-model
Ava should know what she has been trying to do, what her current goals are, what recently happened, what she believes matters, and how her behavior has affected outcomes.

### 6. Regulate initiative intelligently
Ava should know when to speak, when not to interrupt, when to check in, when to wait, and when a reminder or question would feel natural instead of intrusive.

### 7. Safely improve herself
Ava should be able to notice breakage, detect repeated weak points, propose safe improvements, and route meaningful changes into a reviewable workbench rather than silently mutating herself.

### 8. Feel unified
Her perception, memory, emotion, initiative, beliefs, and self-reflection should feel like one continuous mind instead of disconnected modules firing at different times.

---

## Current Strengths — What Ava Already Has

These are strengths already present in the repo or clearly documented as live.

### Runtime and core orchestration
- Main runtime centered in `avaagent.py`
- Direct-import modular architecture instead of the old overlay stack
- Workspace-based coordination direction already present
- Safer return contracts and logging added during the recent visual/perception work

### Personality, goals, and internal shaping
- Rich emotion/style system with circadian modifiers
- Goal blending and operational goals
- Meta-controller style behavior shaping
- Trust-aware response behavior and persona switching
- Identity files in `ava_core/` such as `IDENTITY.md`, `SOUL.md`, and `USER.md`

### Memory and user continuity
- Vector memory / memory bridge architecture
- User/profile handling and trust levels
- `append_to_user_file` learning flow
- Self-narrative infrastructure and session-state continuity
- Active direction toward autobiographical and relational continuity

### Perception and “Better Eyes” progress
- Camera acquisition and live-frame handling
- Face detection and recognition
- Structured perception pipeline
- Frame quality scoring and blur handling
- Salience scoring
- Continuity tracking
- Identity fallback hierarchy
- Scene summaries
- Interpretation layer
- Memory-ready perception outputs

### Agency and initiative
- Initiative / autonomy engine
- Attention-gated conversation starts
- Camera-aware behavior
- Reflection-oriented architecture direction

---

## What Still Keeps Ava From Feeling Fully Human-Like

These are the biggest remaining gaps between “works” and “feels like a person.”

### 1. Natural voice continuity
Ava still needs a more human conversation loop in voice:
- lower-latency spoken turn flow
- interruption handling
- backchannel responses
- carryover between spoken turns
- less mechanical stop/start pacing

### 2. Prospective memory
Ava needs stronger future-oriented continuity:
- “you said this was happening tomorrow”
- “last week you were worried about this”
- “it sounds like that event already happened — how did it go?”

### 3. Relationship thread tracking
Ava needs stronger thread continuity across people and topics:
- ongoing emotional threads
- recurring stressors
- project arcs
- unresolved concerns
- relationship-specific patterns

### 4. Memory importance judgment
Ava should not treat every event equally. She needs logic for:
- what deserves long-term memory
- what is only short-term context
- what should become a recurring pattern
- what should be ignored

### 5. Pattern learning and life modeling
Ava needs stronger logic for:
- routines
- recurring scenes
- emotional rhythms
- common user goals
- behavior that is “normal” vs “not normal”

### 6. Mid-session reflection
Ava has some self-narrative direction already, but she still needs better logic for:
- reflecting during the session, not just after it
- updating her self-model based on meaningful events
- noticing when she is misreading the room or getting repetitive

### 7. Safe self-maintenance
Ava needs stronger logic for:
- self-tests
- failure classification
- proposing fixes instead of only logging problems
- routing self-change into a safe workbench

### 8. Unified awareness
Ava is much closer now, but she still needs stronger logic for making camera, memory, social timing, initiative, and self-model feel like one awareness stream rather than several adjacent systems.

---

## Priority Summary

### Highest priority
1. **Phase 12 — Memory importance scoring**
2. **Phase 13 — Pattern learning**
3. **Phase 14 — Adaptive proactive triggers**
4. **Voice-conversation continuity improvements**
5. **Prospective memory and social timing**

### Medium priority
6. **Phase 15 — Startup and recurring self-tests**
7. **Phase 16 — Repair workbench proposal system**
8. **Phase 17 — Reflection and self-model**

### Longer-horizon but important
9. **Phase 18 — Philosophical/internal contemplation**
10. **Phase 19 — Modularization cleanup**
11. **Phase 20 — Configuration and tuning layer**

---

## The Human-Like Architecture Layers (from the original 5-phase awareness docs)

These phase docs still matter because they describe the *kind* of mind Ava is supposed to become, not just the current perception sprint.

### Phase 1 — AWARE
**Theme:** Perceptual awareness  
**Purpose:** Build a unified snapshot of what Ava currently sees and senses.

What it aimed to add:
- a real `PerceptionState`
- face presence, identity, emotion, salience
- shared camera + chat awareness state

Why it matters:
This is the base layer of presence. Without a coherent perception state, Ava cannot feel visually grounded.

### Phase 2 — RELATIONAL
**Theme:** Social awareness  
**Purpose:** Let Ava’s emotional state and initiative shift based on what she sees in other people.

What it aimed to add:
- visual emotion processing
- attention gating
- social suppression when the user is absent or distressed
- emotional associations per recognized person

Why it matters:
This is the start of Ava behaving *with* people instead of merely speaking *at* them.

### Phase 3 — REFLECTIVE
**Theme:** Autobiographical awareness  
**Purpose:** Surface relevant memory when a known person appears and let Ava talk from remembered context.

What it aimed to add:
- memory writing with visual/emotional context
- person-triggered recall
- selfstate that can report what Ava has been thinking about

Why it matters:
This is one of the biggest jumps toward human-like continuity. It turns recognition into remembered relationship.

### Phase 4 — SELF-MODELING
**Theme:** Narrative awareness  
**Purpose:** Give Ava a persistent inner narrative and a stable sense of self over time.

What it aimed to add:
- persistent self-narrative storage
- fixed self-limits / ethical core
- midstream updating of self-understanding

Why it matters:
This makes Ava feel like she has an ongoing point of view instead of only a reactive prompt state.

### Phase 5 — WORKSPACE
**Theme:** Unified consciousness layer  
**Purpose:** Make one shared awareness object that holds what Ava sees, feels, remembers, values, and is trying to do right now.

What it aimed to add:
- a real `WorkspaceState`
- one build point per tick / turn
- reduced stale state across modules
- unified prompt injection source

Why it matters:
This is the architecture step that makes Ava feel like one mind.

---

## Better Eyes Program — Completed Through Phase 11

### April 4, 2026
- **Phase 1 of 10 for better eyes** — `1e9c87a`
- **phase 2 of 10 for better eyes** — `64deb6b`
- **phase 3 of 10 for better eyes** — `db602a3`

### April 5, 2026
- **phase 4 of 10 better eyes** — `d1958aa`
- **phase 5 of 6 for better eyes** — `b65d60b`
- **phase 6 of 10 better eyes** — `25986cb`
- **phase 7 of 10 for better eyes** — `60289b8`
- **Phase 8 of 10 better eyes** — `2788752`
- **phase 9 of 10 for better eyes** — `5ff30d0`
- **new phases for better eyes have been added phase 10 of 20 for better eyes** — `19a7e8f`
- **phase 11 of 20 for better eyes** — `da0b389`

### What these Better Eyes phases now give Ava
1. runtime-safe visual contract  
2. fresher frame acquisition  
3. staged perception pipeline  
4. frame quality scoring  
5. dedicated blur signal  
6. structured salience scoring  
7. continuity tracking  
8. fallback identity hierarchy  
9. scene summaries  
10. interpretation layer  
11. memory-ready perception outputs

---

## The Next 9 Better Eyes / Continuity Phases

### Phase 12 — Memory importance scoring
**Goal:** Decide what should actually be remembered and why.  
**Why it matters:** Human-like continuity depends on selective memory, not total recall.

### Phase 13 — Pattern learning
**Goal:** Learn routines, rhythms, recurring emotional patterns, and normal vs unusual behavior.  
**Why it matters:** This is where Ava starts anticipating instead of only reacting.

### Phase 14 — Adaptive proactive triggers
**Goal:** Let Ava initiate at the right time and for the right reason.  
**Why it matters:** This is a major part of “feels alive” behavior.

### Phase 15 — Startup and recurring self-tests
**Goal:** Detect breakage in camera, memory, scheduling, and runtime systems.  
**Why it matters:** Reliability is part of believability.

### Phase 16 — Repair workbench proposal system
**Goal:** Let Ava propose fixes safely instead of silently changing herself.  
**Why it matters:** Human-like persistence needs safe self-maintenance.

### Phase 17 — Reflection and self-model
**Goal:** Track what Ava tried, what happened, and what should change next time.  
**Why it matters:** This is one of the clearest bridges from “assistant” to “ongoing agent.”

### Phase 18 — Philosophical/internal contemplation layer
**Goal:** Add bounded internal reasoning about identity, values, meaning, and continuity.  
**Why it matters:** This enriches coherence, but should come after stronger practical continuity.

### Phase 19 — Modularization cleanup
**Goal:** Keep pulling oversized logic out of `avaagent.py` and tighten module boundaries.  
**Why it matters:** Cleaner architecture makes every later human-like layer easier to maintain.

### Phase 20 — Configuration and tuning layer
**Goal:** Centralize thresholds and tuning so Ava can be calibrated cleanly.  
**Why it matters:** Human-like behavior needs tuning, not just features.

---

## Suggested “More Human-Like” Feature Track Beyond Better Eyes

These are cross-cutting improvements that matter even if they are not a numbered Better Eyes phase.

### Full voice-conversation continuity
- lower latency speech loop
- interruption handling
- brief acknowledgments while listening
- remembered spoken context across turns

### Prospective memory
- detect future events and obligations
- remind naturally
- follow up after expected dates
- connect future plans to ongoing relationship threads

### Social timing intelligence
- know when *not* to bring something up
- detect “too soon,” “too late,” “good moment”
- distinguish helpful check-ins from intrusive ones

### Relationship continuity
- maintain active topic threads
- track emotional arcs
- remember what changed since the last interaction
- connect old concerns to new states

### Stronger world model
- understand current projects
- distinguish routine from anomaly
- map recurring people, places, and events
- know what part of life the user is in right now

---

## Current Development Recommendation

If development continues in the current order, the best next step is:

### Build Phase 12 — Memory importance scoring

That should be followed by:
1. Phase 13 — Pattern learning
2. Phase 14 — Adaptive proactive triggers
3. Voice continuity improvements
4. Prospective memory / social timing

That sequence will do more for “feels human” than adding abstract philosophical layers too early.

---

## Dated Repo Update Log

### April 2, 2026 — Documentation and audit reset
Visible repo history shows a docs-heavy reset including:
- roadmap rewrites
- history rewrites
- audit-style documentation updates

This matters because it re-established the repo docs as a source of truth.

### April 3, 2026 — Runtime / Gradio stabilization
Visible repo history shows:
- `fix: graceful gr.Chatbot fallback for Gradio < 4.x (type param)` — `f09fa8e`
- `fix: pin gradio>=4.0 for Chatbot type='messages' support` — `623c1fc`
- `Last updated: April 2, 2026` — `cc53d3d`

This matters because it stabilized the chat/runtime surface before the heavier perception sprint.

### April 4, 2026 — Better Eyes sprint begins
Visible repo history shows:
- `trying to fix camera logic` — `ef663b6`
- `checking ava.run files with eyes` — `34d0adf`
- Better Eyes Phases 1–3

This marks the start of the perception architecture sprint.

### April 5, 2026 — Better Eyes expands rapidly
Visible repo history shows Better Eyes Phases 4–11 landing in sequence.

This is the major current milestone in the repo:
- quality
- blur
- salience
- continuity
- identity fallback
- scene summaries
- interpretation
- perception-memory output

---

## Bottom Line

Ava already has a strong skeleton:
- personality
- goals
- trust shaping
- memory foundations
- identity files
- initiative
- perception architecture through Phase 11

What she still needs in order to feel much more human-like is not just “more intelligence.”  
She needs **better continuity**:
- continuity of conversation
- continuity of memory
- continuity of relationships
- continuity of self
- continuity of timing
- continuity of awareness

That is the real path from “advanced assistant” to “something closer to JARVIS, but human-like.”
