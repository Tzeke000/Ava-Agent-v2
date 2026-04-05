# Ava Agent v2 — Vision, Roadmap, and Dated History

**Version date:** April 5, 2026  
**Intended use:** repo `/docs` reference and local master planning document

## Short summary
Ava’s overall purpose is to become as close as possible to a human-like JARVIS: a local AI companion that can see, listen, remember, speak naturally, track relationship continuity, initiate at the right time, and gradually build a stable inner model of you, herself, and the world around her.

The repo already has a strong foundation in identity, memory, initiative, camera perception, trust-aware behavior, and reflection. The main remaining gaps are natural voice conversation, stronger continuity across time, smarter memory judgment, richer world and life modeling, safer self-maintenance, and more modular long-term architecture.

## Overall purpose and long-term vision
The real target for Ava is not just “a useful assistant.” The target is a human-like JARVIS: an AI that feels continuous, emotionally aware, context-sensitive, and socially well-timed rather than merely reactive. She should be able to hold full spoken conversations, notice what is happening around her, remember what matters, follow up later in a natural way, and gradually form a stable sense of ongoing relationship and personal continuity.

### Human-like target state
- Natural voice conversation with low-latency back-and-forth, interruption handling, turn-taking, and less robotic pacing.
- Continuity across time: Ava should carry forward threads, promises, worries, routines, and unfinished situations rather than treating each session as separate.
- Social timing intelligence: she should know when to bring something up, when to hold back, and when a reminder or follow-up would feel caring instead of intrusive.
- Stable visual understanding: she should know who is likely present, what changed, whether the frame is trustworthy, and what matters most in the scene.
- Emotionally grounded memory: she should remember not only facts, but why they mattered, how confident she is, and what future implications they may have.
- Self-model and reflection: she should keep track of what she tried, what worked, what failed, and how her behavior affects outcomes over time.
- Safe growth: improvements, repairs, and tuning should become more autonomous, but still reviewable and controllable.

## What Ava already has in the repo
- A main runtime centered on `avaagent.py`, with a growing modular `brain/` architecture instead of a purely stacked monolith.
- Identity and personality files in `ava_core/`, including persistent identity-oriented docs and user-aware context scaffolding.
- Mood, emotion, and style systems already wired into responses and state shaping.
- Memory and profile infrastructure, including person-aware memory writing and profile handling.
- Initiative / autonomy behavior that allows Ava to do more than only wait for direct prompts.
- Reflection and self-narrative layers that move her toward longer-term self-consistency.
- Camera-based perception, now expanded into a structured pipeline with freshness, quality, blur, salience, continuity, identity fallback, scene summaries, interpretation, and memory-ready perception events.
- Trust-aware handling and guardrail behavior that helps prevent overclaiming when vision is weak or uncertain.

## What still needs to exist for Ava to feel more human-like
| Area | What is still missing | Why it matters | Current state |
|---|---|---|---|
| Voice loop | More natural real-time spoken conversation, interruption support, lower latency, better pacing, and stronger listening/speaking continuity | This is a huge part of feeling like ChatGPT voice or a human companion instead of turn-based text | Partial |
| Prospective memory | Remember future events, commitments, deadlines, games, appointments, and promised follow-ups | Human-like companions remember what is coming, not only what already happened | Missing / weak |
| Thread continuity | Carry unresolved emotional or practical threads across sessions and bring them up naturally | This is one of the biggest differences between “smart AI” and “someone who knows you” | Partial |
| Life / world model | Track routines, stress cycles, recurring people, locations, and long-running goals | Lets Ava understand patterns instead of isolated moments | Early |
| Memory judgment | Decide what to keep, what to compress, and what not to store | Without this, memory becomes noisy and less human-like | Next |
| Pattern learning | Learn what is normal, unusual, effective, or unwelcome over time | Necessary for adaptive behavior and better timing | Upcoming |
| Self-maintenance | Run health checks, propose fixes, and maintain safer evolution workflows | Needed for long-lived reliability | Upcoming |
| Conversation timing | Know when to speak, wait, follow up, remind, or stay quiet | Good social timing is one of the deepest human-like signals | Partial |

## Dated repository update log
| Date | Commit / window | What landed | Why it mattered |
|---|---|---|---|
| Apr 2, 2026 | Docs audit window | Roadmap/history reset and repo-audit style documentation refresh | Re-established docs as the repo narrative baseline |
| Apr 3, 2026 | Runtime / Gradio fixes | UI/runtime compatibility fixes and related cleanup | Stabilized the app enough for the later perception sprint |
| Apr 4, 2026 | `1e9c87a`, `64deb6b`, `db602a3` | Perception Phases 1–3: runtime stabilization, camera freshness, and staged pipeline structure | Turned vision from a fragile path into a cleaner architecture base |
| Apr 5, 2026 | `d1958aa` | Perception Phase 4: structured frame quality scoring | Made visual trust more explicit and tunable |
| Apr 5, 2026 | `b65d60b` | Perception Phase 5: dedicated blur signal and blur-aware scaling | Separated blur from general quality so confidence can degrade more honestly |
| Apr 5, 2026 | `25986cb` | Perception Phase 6: structured salience scoring | Gave Ava a way to decide what visually matters most |
| Apr 5, 2026 | `60289b8` | Perception Phase 7: tracking and continuity | Reduced identity flicker and introduced temporal carry-over |
| Apr 5, 2026 | `2788752` | Perception Phase 8: fallback identity hierarchy | Separated raw recognition from resolved identity and stable identity |
| Apr 5, 2026 | `5ff30d0` | Perception Phase 9: scene summaries | Created a stable, compact “what is happening” layer |
| Apr 5, 2026 | `19a7e8f` | Perception Phase 10: interpretation layer | Moved the visual stack from detection toward meaning |
| Apr 5, 2026 | `da0b389` | Perception Phase 11: memory-ready perception outputs | Created semantic event records without persistence side effects yet |

## The next 9 phases of “better eyes”
### Phase 12 — Memory importance scoring
Score perception-memory events for importance, future usefulness, novelty, emotional weight, and relationship relevance.

### Phase 13 — Pattern learning
Learn routines, recurring moods, common return times, typical scene states, and which interventions help or annoy.

### Phase 14 — Adaptive proactive triggers
Let Ava initiate more naturally based on inactivity, returns, unresolved threads, due events, completed tasks, or meaningful scene change.

### Phase 15 — Startup and recurring self-tests
Check camera health, frame freshness, microphone path, model availability, memory I/O, timers, and critical files on startup and on recurring intervals.

### Phase 16 — Repair workbench proposal system
Allow Ava to suggest threshold changes, config fixes, or patch proposals in a safe, reviewable workbench instead of uncontrolled self-editing.

### Phase 17 — Reflection and self-model
Track what Ava tried, what happened, how the user responded, and what should change next time.

### Phase 18 — Philosophical / internal contemplation layer
Give Ava bounded space for questions like continuity of self, what matters most, and when to speak versus observe.

### Phase 19 — Modularization cleanup
Keep moving oversized logic out of `avaagent.py`, strengthen module boundaries, and make the repo easier to maintain and extend.

### Phase 20 — Configuration and tuning layer
Centralize thresholds and runtime-tuning knobs so perception, memory, continuity, and proactive behavior can be adjusted without repeated code edits.

## Recommended near-term “more human-like” upgrades beyond the current visual sprint
- A more natural full-duplex voice loop: faster replies, interruption support, “thinking while listening” feel, and fewer rigid turn boundaries.
- Prospective memory and future-event extraction so Ava can remember what is coming up and follow up later like a real companion would.
- Relationship thread tracking so worries, projects, and emotional situations carry across sessions and get revisited naturally.
- Conversation cadence awareness so Ava notices unusual gaps or unusually frequent returns without making it awkward.
- Smarter memory writing with emotional tone, future implications, and relationship impact rather than only factual notes.
- A life-rhythm model that slowly learns patterns like stress cycles, creative cycles, and recurring people or situations.
- A developer-facing debug panel that makes internal state easier to inspect during tuning.
