# Ava Agent v2 — Development Roadmap
**Last updated:** April 28, 2026  
**Repo:** `Tzeke000/Ava-Agent-v2` (public)  
**Based on:** Full repo audit + roadmap planning session

---

## Executive status — April 27, 2026

**The staged roadmap through Phase 31 is implemented in this repo**, including **Phase 16.5** (supervised execution, `brain/workbench_execute.py`) and **Phase 16.6** (approval / command layer, `brain/workbench_commands.py`). Later sections document **what was built**; **future / additive** work (prospective memory calendar, debug UI, etc.) is called out explicitly so completed phases are not re-listed as missing baseline.

**What Ava is:** a local, camera-aware agent with a **staged perception pipeline**, **vector memory**, **profiles**, **goals**, **initiative**, **reflection/contemplation**, **social and multi-session continuity**, **bounded tone guidance**, and a **supervised** (human-approved) path from diagnostics → workbench proposals → execution/rollback — without claiming human consciousness.

**Identity anchors (continuity policy):** `ava_core/IDENTITY.md` is Ava’s **core self** anchor; `ava_core/SOUL.md` is **values, boundaries, and self-guidance**; `ava_core/USER.md` is the **durable relationship** anchor for the user. `ava_core/BOOTSTRAP.md` is **first-run scaffolding only** and is **not** treated as ongoing primary self once IDENTITY/SOUL are established (see Phase 29). Runtime continuity layers **read** these for grounding; **editing** them remains a deliberate, reviewable concern—not casual prompt churn.

---

## Current Phase Board (April 28, 2026)

| Phase | Title | Status |
|---|---|---|
| 1–31 | Core staged architecture (perception, memory, routing, continuity, heartbeat) | **COMPLETE** |
| 32 | Operator HTTP + presence shell hardening | **COMPLETE** |
| 33 | Shutdown ritual + desktop agent foundation | **COMPLETE** |
| 33b | Shutdown-overlay polish and desktop continuity glue | **COMPLETE** |
| 34 | MeloTTS scaffold + pyttsx3 fallback | **COMPLETE** |
| 35 | Fury HistoryManager context overhaul | **COMPLETE** |
| 36 | Social chat routing fix (`mistral:7b`) | **COMPLETE** |
| 37 | Emotional orb UI with 27 emotions | **COMPLETE** |
| 38 | Fine-tuning pipeline (75 examples, `ava-personal:latest`) | **COMPLETE** |
| 39 | LLaVA scene understanding scaffold | **COMPLETE** |
| 40 | Deep self-awareness (theory of mind, self-critique, repair behaviors) | **COMPLETE** |
| 41 | Tools foundation (`web_search`, `file_manager`, diagnostics) | **COMPLETE** |
| 42 | Visual memory scaffold (cluster-fk inspired) | **COMPLETE** |
| 43 | Voice pipeline (pyttsx3 Zira + STT scaffold + sounddevice) | **COMPLETE** |
| 44 | Switch Ava to `ava-personal:latest` as primary brain | **PLANNED** |
| 45 | Concept graph decay + associative recall in prompts | **PLANNED** |
| 46 | Emil integration planning | **PLANNED** |
| 47 | WebSocket transport replacing HTTP polling | **PLANNED** |
| 48 | Ava proposes next phases autonomously | **PLANNED** |
| 49 | MeloTTS female voice upgrade (post-Zira) | **PLANNED** |
| 50 | Clap detection for hands-free activation | **PLANNED** |

### App Milestones (completed)

- Tauri desktop app with sci-fi presence view.
- Three.js energy orb with 5 layers and 27 emotion morphs.
- Color + shape morphing per emotion (teardrop / double / elongated variants).
- Voice tab as default, with chat tab orb beneath camera.
- Brain tab with D3 force graph, legend, stats bar, and zoom-glitch fix.
- Finetune tab with live status and log feed.
- Input mute button integrated into presence flow.
- Graceful shutdown with goodbye overlay and process close handoff.
- Concept graph now reporting 500 nodes / 1593 edges, with Zeke most connected.
- `ava-personal:latest` fine-tuned model available for routing.
- Microsoft Zira female voice active for pyttsx3.

### Tools Roadmap

| Track | Status | Notes |
|---|---|---|
| Desktop tools Tier 1 (read/search/diagnostics/web/local tools) | **COMPLETE** | Default autonomous operations inside project safety boundaries |
| Desktop tools Tier 2 verbal check-ins | **IN PROGRESS** | "I'm going to [action] — doing it now." narration plus immediate execution |
| Tier 3 explicit confirmation flow for external/high-impact actions | **IN PROGRESS** | Requires explicit confirmation phrase from Zeke before execution |
| Three-laws policy enforcement in tool layer | **IN PROGRESS** | Financial/privacy/harm checks block execution regardless of user prompt style |
| Structured tool arguments in `[TOOL:...]` reply tags | **COMPLETE** | JSON parameter payloads supported in inline tool tags |
| Tool telemetry in operator snapshot/debug | **COMPLETE** | Last tool, result preview, and execution counts surfaced |

---

## Architecture baseline — Phases 1 through 31 complete

**Foundation (Phases 1–20):** Staged **perception** (quality, blur, detection, recognition, salience, continuity, identity fallback, scene summary, interpretation layer), **perception memory**, **memory scoring**, **pattern learning**, **proactive triggers**, **self-tests**, **workbench proposals**, **reflection**, **contemplation**, **`bundle_to_perception_state`** modularization (**Phase 19** — mapping consolidated in `brain/perception_state_adapter.py` instead of inline in the pipeline), and centralized knobs in **`config/ava_tuning.py`** (**Phase 20**).

**Post-foundation (Phases 21–31):** **Calibration / tuning** (21), **voice conversation & turn-taking hints** (22), **social continuity / relationship modeling** (23), **memory refinement** (24), **dynamic Ollama model routing** (25), **bounded curiosity** (26), **outcome learning** (advisory) (27), **conversational nuance** (28), **multi-session strategic continuity** with **ava_core** anchors (29), **supervised self-improvement loop** (30), **resident heartbeat + bounded adaptive learning** (31 — quiet background continuity between perception ticks; **no** unsafe autonomy). **Workbench 16.5** and **16.6** ship alongside Phase 16 proposals.

**Plain-language capability map (major areas):** perception stack • memory events / scoring / refinement • pattern learning • proactive triggers • self-tests • workbench proposals • supervised execution • approval/command flow • reflection • contemplation • social continuity • voice turn-taking • conversational nuance • multi-session continuity • dynamic model routing • supervised self-improvement loop • heartbeat / adaptive preferences • calibration/tuning • modular adapter cleanup (Phase 19).

Further work **extends** this stack (calendar/prospective memory, richer event extraction, UI)—it does **not** replace the shipped architecture.

---

## Vision: JARVIS, But As Human-Like As Possible

Ava's technical foundation is already strong. The gap between "impressive AI" and "feels like a person who actually knows you" comes down to **continuity** — does she remember what you told her is coming, bring it up at the right moment, and connect past threads to the present? **Implemented layers** (profiles, social continuity, strategic continuity, outcome learning, nuance) move in that direction; **future** items below (prospective memory, social timing, life model) still represent the next leap.

---

## Current Strengths (What's Already Working)

- ✅ Rich 27-emotion + style blend system with circadian modifiers
- ✅ Meta-controller with modes, outcome learning, drive normalization
- ✅ Goal system + operational goals shaping every response
- ✅ Initiative / autonomy engine (camera-triggered + attention-gated)
- ✅ Self-reflection + self-narrative (live via `atexit` + session milestones)
- ✅ Vector memory (ChromaDB) + person profiles with trust levels
- ✅ Camera + visual pattern detection + transition recognition
- ✅ Better Eyes **E1** scaffolding: resolved-frame trust metadata, recovery/low-quality states, workspace logging (Phase 6)
- ✅ Stage 7 trust gate + per-person persona tones
- ✅ `ava_core/` identity files (IDENTITY.md, SOUL.md, USER.md) versioned and auto-updating
- ✅ `append_to_user_file` wired — Ava learns facts about Zeke and writes them to USER.md

---

## The 8 Missing "Human-Like Continuity" Pieces (next-generation / additive)

These are **not** claims that the baseline roadmap is unfinished—they are the **next** gaps between shipped continuity layers and a **full** JARVIS-like companion experience (calendar awareness, timing intelligence, richer memory writing, etc.).

| Priority | Feature | Why It Matters | Status |
|---|---|---|---|
| 1 | **Prospective Memory / Commitments Calendar** | Tracks open loops ("John has football game tomorrow") and turns them into natural follow-ups | ❌ Not present |
| 2 | **Event Extraction** | Auto-detects dates, future events, promises from conversation ("tomorrow", "next week", "my game is Friday") | ⚠️ Partial / weak |
| 3 | **Social Timing Intelligence** | Knows when to bring something up — too soon / too late / gentle reminder window | ❌ Not present |
| 4 | **Relationship Continuity / Thread Tracking** | Connects "you were stressed about work Tuesday" to "you seem more relaxed now" — not just profile notes but active threads | ⚠️ Partial — **Phase 23** social continuity + profiles + Phase 29 carryover; **full** arc tracking still future |
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

### P1-04 — Stabilize `run_ava` return contract *(live)*

- **`brain/turn_visual.py`**: `default_visual_payload()`, `normalize_visual_payload()` — every turn returns a **full visual dict** (face / recognition / expression / memory_preview + optional `turn_route`, `vision_status`, `visual_truth_trusted`) so empty `{}` never blanks Gradio columns.
- **`run_ava`**: entry/exit logging, `turn_route` per branch (`blocked`, `deflect`, `selfstate`, `camera_identity`, `llm`, `error`), top-level exception fallback with explicit visual + `run_ava_error` action.
- **`finalize_ava_turn`**: normalizes visual before return; logs finalize line.
- **`build_prompt` / camera identity**: `[visual_pipeline]` / `[recognition]` logs; **`camera_live`**: log when a live read returns no frame.

### Camera / vision — Phase 2 — Frame acquisition & freshness *(live)*

*(Distinct from the “Phase 2 — Prospective Memory” section below — this is the vision pipeline track.)*

- **`brain/frame_store.py`**: Centralized **`FRESH_MAX_AGE_SEC`**, **`AGING_MAX_AGE_SEC`**, **`LIVE_CACHE_MAX_AGE_SEC`**; **`classify_acquisition_freshness()`** → `fresh` | `aging` | `stale` | `unavailable`; **`read_live_frame_with_meta()`** maintains the latest good buffer, capture timestamp, and explicit logs (cache vs device, open/read success/failure, stale cache warning, no frame).
- **`brain/camera_live.py`**: Thin wrapper — still **`(frame, capture_ts)`**; optional **`device_index`** passed through to the store.
- **`brain/camera.py` / `brain/perception.py`**: **`ResolvedFrame.acquisition_freshness`** and **`PerceptionState.acquisition_freshness`**; **`[camera]`** / **`[perception]`** / **`[workspace]`** logs include **`acq=`**.
- Vision trust / **`STALE_FRAME_MS`** in `camera.py` is unchanged; acquisition labels are diagnostic and age-aware alongside it.

### Perception — Phase 3 — Staged pipeline *(live)*

- **`brain/perception_types.py`**: `StageResult`, stage outputs (`AcquisitionOutput`, `QualityOutput`, `DetectionOutput`, `RecognitionOutput`, `ContinuityOutput`, `InterpretationOutput`, `PackageOutput`), `PerceptionPipelineBundle`; module doc lists future hooks (quality scoring, salience, tracking, scene summaries, interpretation).
- **`brain/perception_utils.py`**: `lbph_distance_to_identity_confidence`, `compute_salience` (shared, no pipeline import cycles).
- **`brain/perception_pipeline.py`**: `run_perception_pipeline()` → staged flow with **`[perception_pipeline]`** logs (`acquisition`, `quality`, `detection`, `recognition`, `continuity`, `interpretation`, `package`). Detection/recognition short-circuit when vision is untrusted (same as before). Stage failures log and continue with safe defaults.
- **`brain/perception_state_adapter.py`**: `bundle_to_perception_state()` maps **`PerceptionPipelineBundle`** → legacy **`PerceptionState`** (Phases 9–18 field copies live here; see Phase 19).
- **`brain/perception.py`**: `build_perception()` delegates to the pipeline; **`PerceptionState`** unchanged for workspace / `avaagent`.
- **Note:** **`PerceptionPipelineBundle`** → **`PerceptionState`** is **`bundle_to_perception_state()`** in **`brain/perception_state_adapter.py`** (centralized in Phase 19; previously inline in **`brain/perception_pipeline.py`**). Sections below spell out **stage orchestration** vs **flat state** where both matter.

### Perception — Phase 4 — Frame quality scoring *(live)*

- **`brain/frame_quality.py`**: `compute_frame_quality()`, `assess_frame_quality_basic()` (compat tuple API), centralized **`USABLE_MIN_OVERALL`** / **`WEAK_MIN_OVERALL`** (aligned with `camera.LOW_QUALITY_THRESHOLD`), per-metric scores (blur, darkness, overexposure; motion smear + occlusion **provisional**), **`[frame_quality]`** logs, labels **`usable` | `weak` | `unreliable`**.
- **`brain/perception_types.py`**: **`FrameQualityAssessment`**; **`QualityOutput`** carries **`structured`**, **`recognition_confidence_scale`**, **`expression_confidence_scale`**.
- **`brain/camera.py`**: Single `compute_frame_quality` pass per resolve; **`ResolvedFrame.quality_detail`**; **`[camera]`** includes **`qlabel=`**.
- **`brain/perception_pipeline.py`**: Quality stage attaches structured output + scales; trusted-path **identity** / **salience** scaled **additively** from label.
- **`brain/perception.py`**: **`PerceptionState`** extended with **`quality_label`**, metric scores, and scale fields (defaults safe for old code paths).

### Perception — Phase 5 — Dedicated blur signal *(live)*

- **`brain/frame_quality.py`**: Central **`BLUR_VAR_SOFT_MAX`** / **`BLUR_VAR_SHARP_MIN`**; **`classify_blur_laplacian_var()`** → **`blur_label`** `sharp` | `soft` | `blurry`; **`blur_layer_confidence_scales()`** → recognition / expression / interpretation multipliers (interpretation slightly milder on **`blurry`**). Legacy **`overall_quality_score`** recipe unchanged; blur also feeds **`reason_flags`** as before.
- **`brain/perception_types.py`**: **`FrameQualityAssessment`** and **`QualityOutput`** carry **`blur_value`**, blur scales, **`quality_only_*`** scales for combining label × blur; **`blur_reason_flags`** for inspection.
- **`brain/perception_pipeline.py`**: Combined confidence = Phase 4 label scale × blur scale; salience uses **`quality_only_expression_scale` × `blur_interpretation_scale`** (lighter blur penalty on interpretation). Logs **`blur_value`**, **`blur_label`**, per-layer blur scales, and combined rec/expr.
- **`brain/perception.py`**: **`PerceptionState`** blur fields for UI / prompts / future hooks (scene summaries, recognition fallback, memory-worthiness).

### Perception — Phase 6 — Structured salience scoring *(live)*

- **`brain/salience.py`**: **`build_salience_result()`** — ranked **`SalientItem`** list (face / scene_cue), factor breakdown (centeredness, prominence, motion attention from frame-quality smear, recognition relevance, legacy emotion/user engagement), **`future_hooks`** for hand-held object and scene-change deltas (placeholders). **`combined_scalar`** blends structured primary score with **`perception_utils.compute_salience`** for backward-compatible magnitude.
- **`brain/perception_types.py`**: **`SalientItem`**, **`SalienceResult`**; **`DetectionOutput.face_rects`**; **`InterpretationOutput.salience_structured`**.
- **`brain/perception_pipeline.py`**: After detection + recognition, interpretation builds structured salience; logs **`[salience]`** per item and **`[perception_pipeline] top_salient=`**.
- **`brain/perception_state_adapter.py`**: **`PerceptionState.salience`** (combined scalar × expression-quality × blur-interp), **`salience_items`**, **`salience_top_*`**, **`salience_combined_scalar`** — set in **`bundle_to_perception_state()`** (Phase 19) for UI / memory / initiative hooks.

### Perception — Phase 7 — Tracking and continuity *(live)*

- **`brain/continuity.py`**: Module-level **recent primary-face memory** (normalized center, area ratio, last identity, salience top label); **`update_continuity()`** compares the current trusted tick using **spatial** (center distance + size ratio), **time decay** (wall clock + frame gap), **salience top** consistency, and **LBPH** when recognized. Emits **`ContinuityResult`**: `identity_state` includes **`likely_identity_by_continuity`** when carrying prior without a fresh recognizer label, plus **`confirmed_recognition`** / **`unknown_face`** / **`no_face`**; **`suppress_flip`** when spatial carry applies.
- **`brain/perception_types.py`**: **`ContinuityResult`**; **`ContinuityOutput.structured`**.
- **`brain/perception_pipeline.py`**: Pipeline order **interpretation → continuity** (salience available); logs **`[continuity]`** and **`[perception_pipeline] continuity`**.

### Perception — Phase 8 — Fallback identity hierarchy *(live)*

- **`brain/identity_fallback.py`**: **`resolve_identity_fallback()`** after continuity — canonical **`identity_state`**: **`confirmed_recognition`** (raw id + scaled LBPH ≥ threshold), **`likely_identity_by_continuity`**, **`unknown_face`**, **`no_face`**. Emits **`IdentityResolutionResult`**: **`raw_identity`**, **`resolved_identity`**, **`stable_identity`**, **`fallback_source`** (`recognition` | `continuity` | `none`), **`fallback_notes`**. Demotes weak LBPH even if recognizer returns a label; logs **`[identity_fallback]`**.
- **`brain/perception_types.py`**: **`IdentityResolutionResult`**; **`PerceptionPipelineBundle.identity_resolution`**.
- **`brain/perception_pipeline.py`**: **`note_trusted_identity`** only when Phase 8 resolution is **`confirmed_recognition`**; **`[perception_pipeline] identity resolved`**.
- **`brain/perception_state_adapter.py`**: **`bundle_to_perception_state()`** copies **`IdentityResolutionResult`** onto **`PerceptionState`** (**`face_identity`** = raw LBPH; **`resolved_face_identity`** / **`stable_face_identity`** / **`identity_fallback_*`**, alongside acquisition/trust paths — Phase 19 adapter).

### Perception — Phase 9 — Scene summaries *(live)*

- **`brain/scene_summary.py`**: **`build_scene_summary()`** after identity resolution — compact **`SceneSummaryResult`** from **`identity_state`**, resolved identity, quality/blur labels, motion smear, face-count delta (entrant hint), and vision trust. **`compact_text_summary`** for UI/prompts; **`overall_scene_state`** is **`stable`** \| **`changed`** \| **`uncertain`**; **`key_entities`** empty until object detection. Logs **`[scene_summary]`**.
- **`brain/perception_types.py`**: **`SceneSummaryResult`**; **`PerceptionPipelineBundle.scene_summary`**.
- **`brain/perception_pipeline.py`**: **`[perception_pipeline] summary`** after **`build_scene_summary`**.
- **`brain/perception_state_adapter.py`**: Maps **`scene_*`** onto **`PerceptionState`** (**`bundle_to_perception_state()`**, Phase 19).

### Perception — Phase 10 — Interpretation layer *(live)*

- **`brain/interpretation.py`**: **`build_interpretation_layer()`** after scene summary — **`InterpretationLayerResult`** with **`event_types`** (e.g. **`person_entered`**, **`person_left`**, **`known_person_present`**, **`likely_known_person_present`**, **`unknown_person_present`**, **`scene_changed`**, **`user_or_subject_engaged`** / **`disengaged`**, **`occupied_or_busy_visual_state`**, **`no_meaningful_change`**, **`uncertain_visual_state`**), **`primary_event`**, **`event_confidence`** / **`event_priority`**, **`interpreted_subject`** / **`interpreted_identity`**, **`evidence`** snapshot, **`no_meaningful_change`**. Uses scene summary, identity resolution, quality/blur, salience/emotion, continuity; untrusted → **`uncertain_visual_state`**. Logs **`[interpretation]`** and **`[perception_pipeline] interpretation`**.
- **`brain/perception_types.py`**: **`InterpretationLayerResult`**; **`PerceptionPipelineBundle.interpretation_layer`**.
- **`brain/perception_pipeline.py`**: Runs **`build_interpretation_layer`** after scene summary; structured **`InterpretationLayerResult`** does **not** overwrite Phase 9 **`scene_*`** text.
- **`brain/perception_state_adapter.py`**: Maps **`interpretation_*`** onto **`PerceptionState`** (**`bundle_to_perception_state()`**, Phase 19).

### Perception — Phase 11 — Memory-ready perception outputs *(live)*

- **`brain/perception_memory.py`**: After the interpretation layer, **`build_perception_memory_output()`** emits at most one **`PerceptionMemoryEvent`** per tick from scene summary + **`InterpretationLayerResult`** + identity resolution (with quality/salience/continuity in **`evidence`**). No storage or scoring yet.
- **`brain/perception_types.py`**: **`PerceptionMemoryEvent`**, **`PerceptionMemoryOutput`**, **`PerceptionPipelineBundle.perception_memory`**.
- **`brain/perception_pipeline.py`**: Runs memory output after **`build_interpretation_layer`**; logs **`[perception_memory]`** and **`[perception_pipeline] memory`**. Duplicate **`no_meaningful_change`** ticks with the same stable signature are skipped (no new record).
- **`brain/perception_state_adapter.py`**: Maps **`perception_memory_*`** onto **`PerceptionState`** (**`bundle_to_perception_state()`**, Phase 19).

### Perception — Phase 12 — Memory importance scoring *(live)*

- **`brain/memory_scoring.py`**: **`score_memory_importance()`** consumes Phase 11 **`PerceptionMemoryOutput`** plus identity/scene/interpretation/quality/continuity context and returns a conservative **`MemoryImportanceResult`** (no persistence side effects).
- **`brain/perception_types.py`**: Adds **`MemoryDecisionResult`** / **`MemoryImportanceResult`** and **`PerceptionPipelineBundle.memory_importance`**.
- **`brain/perception_pipeline.py`**: Pipeline order is memory output → memory scoring → package; logs **`[memory_scoring]`** and **`[perception_pipeline] memory score=`**.
- **`brain/perception_state_adapter.py`**: Maps **`memory_*`** onto **`PerceptionState`** (**`bundle_to_perception_state()`**, Phase 19; for persistence hooks / diagnostics).

### Perception — Phase 13 — Pattern learning *(live)*

- **`brain/pattern_learning.py`**: **`learn_pattern_signals()`** consumes scored events and structured context to produce lightweight probabilistic pattern signals (familiarity, unusualness, recurrence, transition pattern) without durable writes.
- **`brain/perception_types.py`**: Adds **`PatternSignal`** / **`PatternLearningResult`** and **`PerceptionPipelineBundle.pattern_learning`**.
- **`brain/perception_pipeline.py`**: Pipeline order is memory scoring → pattern learning → package; logs **`[pattern_learning]`** and **`[perception_pipeline] pattern=`**.
- **`brain/perception_state_adapter.py`**: Maps **`pattern_*`** onto **`PerceptionState`** (**`bundle_to_perception_state()`**, Phase 19; future hooks: initiative, reflection, diagnostics).

### Perception — Phase 14 — Adaptive proactive triggers *(live)*

- **`brain/proactive_triggers.py`**: **`evaluate_proactive_triggers()`** consumes memory output + memory scoring + pattern signals + identity/scene/quality/continuity context and returns conservative trigger recommendations (no direct speech/tool forcing).
- **`brain/perception_types.py`**: Adds **`ProactiveTriggerCandidate`** / **`ProactiveTriggerResult`** and **`PerceptionPipelineBundle.proactive_trigger`**.
- **`brain/perception_pipeline.py`**: Pipeline order is pattern learning → proactive triggers → package; logs **`[proactive_triggers]`** and **`[perception_pipeline] proactive=`**.
- **`brain/perception_state_adapter.py`**: Maps **`proactive_*`** onto **`PerceptionState`** (**`bundle_to_perception_state()`**, Phase 19; initiative/autonomy integration hooks).

### Perception — Phase 15 — Startup and recurring self-tests *(live)*

- **`brain/selftests.py`**: Lightweight diagnostics-only checks for startup and recurring cadence (camera module/read path, acquisition freshness path, pipeline callability, key dirs/files, memory path, audio/model hook exposure, tick-readiness). No automatic repairs.
- **`brain/perception_types.py`**: Adds **`SelfTestCheckResult`**, **`HealthSummaryResult`**, **`SelfTestRunResult`**, and **`PerceptionPipelineBundle.selftests`**.
- **`brain/perception_pipeline.py`**: Runs **`maybe_run_selftests()`** after proactive triggers; logs **`[selftests]`**.
- **`brain/perception_state_adapter.py`**: Maps **`selftest_*`** onto **`PerceptionState`** (**`bundle_to_perception_state()`**, Phase 19; dashboards / repair-workbench).

### Perception — Phase 16 — Repair workbench proposal system *(live)*

- **`brain/workbench.py`**: **`build_workbench_proposals()`** translates structured self-test/runtime evidence into conservative, human-reviewable repair proposals (no automatic execution).
- **`brain/perception_types.py`**: Adds **`RepairProposal`**, **`WorkbenchProposalResult`**, and **`PerceptionPipelineBundle.workbench`**.
- **`brain/perception_pipeline.py`**: Runs workbench proposal generation after self-tests; logs **`[workbench]`** and **`[perception_pipeline] workbench=`**.
- **`brain/perception_state_adapter.py`**: Maps **`workbench_*`** onto **`PerceptionState`** (**`bundle_to_perception_state()`**, Phase 19; UI / review hooks).

### Perception — Phase 16.5 — Supervised code/file execution layer *(live)*

- **`brain/workbench_execute.py`**: Adds explicit, supervised execution APIs around proposals with strict approval gating, path allowlist/default-deny, sensitive-target elevated approval, backup-before-modify, and rollback support.
- **`brain/perception_types.py`**: Adds **`WorkbenchExecutionRequest`**, **`WorkbenchExecutionResult`**, **`FileChangePlan`**, **`FileChangeRecord`** for reviewable, reversible execution records.
- **Design guardrail**: **proposal != execution**. Workbench proposals never auto-apply. Execution requires explicit approval and runs only through supervised request handling; pipeline only exposes readiness/status fields.

### Perception — Phase 16.6 — Workbench approval/command layer *(live)*

- **`brain/workbench_commands.py`**: Adds a structured operator command path for listing/reviewing/selecting proposals and invoking dry-run/staged/apply/rollback through Phase 16.5 APIs.
- **`brain/perception_types.py`**: Adds **`WorkbenchCommandRequest`**, **`WorkbenchCommandResult`**, **`WorkbenchProposalView`**, **`WorkbenchQueueState`** for explicit command/approval/result handling.
- **Approval guardrail**: Proposal review path now exists, but apply/staged/rollback still require explicit approval and execution still flows through Phase 16.5 safety checks (allowlist, sensitive-target elevation, backups, supervised rollback).

### Perception — Phase 17 — Reflection and self-model *(live)*

- **`brain/reflection.py`**: **`build_reflection_result()`** synthesizes evidence-based operational reflections from structured signals (self-tests, workbench outcomes, perception/memory/pattern/proactive context, optional command/execution adapters).
- **`brain/perception_types.py`**: Adds **`ReflectionObservation`**, **`SelfModelSnapshot`**, **`ReflectionResult`**, and **`PerceptionPipelineBundle.reflection`**.
- **`brain/perception_pipeline.py`**: Runs **`build_reflection_result`** after workbench proposal generation; logs **`[reflection]`** and **`[perception_pipeline] reflection=`**.
- **`brain/perception_state_adapter.py`**: Maps **`ReflectionResult`** onto **`PerceptionState`** **`reflection_*`** and **`self_model_*`** (**`bundle_to_perception_state()`**, Phase 19).
- **Boundedness guardrail**: reflections are grounded in runtime evidence and produce soft operational tags; no autonomous config/action override is introduced in this phase.

### Perception — Phase 18 — Philosophical/internal contemplation *(live)*

- **`brain/contemplation.py`**: **`build_contemplation_result()`** produces bounded, evidence-aware internal contemplation themes and soft internal priority weights from reflection/perception/maintenance context.
- **`brain/perception_types.py`**: Adds **`ContemplationPrompt`**, **`InternalPriorityView`**, **`ContemplationResult`**, and **`PerceptionPipelineBundle.contemplation`**.
- **`brain/perception_pipeline.py`**: Runs **`build_contemplation_result`** after reflection; logs **`[contemplation]`** and **`[perception_pipeline] contemplation=`**.
- **`brain/perception_state_adapter.py`**: Maps **`ContemplationResult`** onto **`PerceptionState`** **`contemplation_*`** (**`bundle_to_perception_state()`**, Phase 19).
- **Boundedness guardrail**: contemplation is descriptive guidance only, grounded in structured evidence, and does not introduce autonomous override behavior.

### Perception — Phase 19 — Modularization cleanup *(live)*

- **`brain/perception_state_adapter.py`**: Owns **`bundle_to_perception_state()`** and all bundle → **`PerceptionState`** field mapping (including **`apply_cognitive_phases_from_bundle()`** for Phases 9–18 so early-exit and full-trust paths stay aligned without duplicated apply chains).
- **`brain/perception_pipeline.py`**: Stages + structured outputs only; re-exports **`bundle_to_perception_state`** for backward-compatible **`from brain.perception_pipeline import bundle_to_perception_state`**.
- **Intent**: structural maintainability only — no intentional semantic changes to scoring, triggers, identity, workbench, reflection, or contemplation.

### Phase 20 — Configuration & tuning layer *(live)*

- **`config/ava_tuning.py`**: Central **dataclass sections** (`QUALITY_CONFIG`, `BLUR_CONFIG`, `SALIENCE_CONFIG`, `CONTINUITY_CONFIG`, `IDENTITY_CONFIG`, `SCENE_SUMMARY_CONFIG`, interpretation and memory-event/scoring knobs, **`PATTERN_CONFIG`**, **`PROACTIVE_CONFIG`**, **`SELFTEST_CONFIG`**, **`WORKBENCH_CONFIG`**, **`REFLECTION_CONFIG`**, **`CONTEMPLATION_CONFIG`**, etc.) with **defaults matching pre–Phase-20 behavior** so tuning is one place to edit, not a semantic retune pass.
- **Feature modules** import these singletons (e.g. **`brain/frame_quality`**, **`brain/reflection`**, **`brain/contemplation`**, proactive/self-test/workbench); **`summarize_tuning_config()`** returns a compact dict for occasional debug.
- **`avaagent.run_ava`**: One-time log on first entry noting the tuning layer source path (non-spammy).
- **Intent**: calibration readiness — fewer scattered magic numbers, clearer subsystem ownership, **no large external settings framework** and **no intentional pipeline semantic changes**.

### Phase 21 — Real-world calibration and tuning *(live)*

- **`brain/calibration.py`**: Session **counters and derived rates** from each **`run_perception_pipeline`** tick (trusted low-quality frames, blur penalty usage, identity states including **unknown_face** / **likely_identity_by_continuity**, **no_meaningful_change**, perception-memory **duplicate suppression**, proactive **suppression vs eligible**, workbench proposals, self-test warnings/failures, reflection uncertain/degraded categories).
- **`brain/perception_types.py`**: **`CalibrationObservation`**, **`ThresholdReviewResult`**, **`CalibrationReport`** — structured diagnostic output (**no auto-retuning**).
- **`summarize_calibration_state()`** / **`get_last_calibration_report()`**: Compact snapshots for debugging; **watchlist** suggests **`raise` / `lower` / `watch`** directions from observed rates (human review only).
- **Logging**: Periodic **`[calibration] summary=...`** (every ~96 ticks, not per-tick spam); first-seen watch items log **`[calibration] subsystem=... metric=... direction=...`**.
- **Intent**: **Evidence-based tuning workflow** after Phase 20 — measure skew (false-positive/negative *signals* via rates), document suggested review directions, **preserve** approval rules, bounded reflection/contemplation, identity hierarchy, and pipeline ordering.

### Phase 22 — Natural voice conversation and turn-taking *(live)*

- **`brain/voice_conversation.py`**: Soft **turn states** (listening / user_pause / assistant_ready / assistant_speaking / yielding / interrupted / idle), **response readiness** and **pause bias** from transcript shape + inter-turn gaps (Gradio **record-stop** — not streaming VAD), **overlap / interrupt hints**, **`continuity_hint`** carry-forward; **`prepare_voice_turn_for_globals`** / **`finalize_voice_turn_after_reply`** bracket **`voice_fn`**.
- **`brain/perception_types.py`**: **`VoiceConversationResult`**, **`VoiceTimingDecision`**.
- **`PerceptionState`** + **`bundle_to_perception_state(..., g)`**: **`voice_turn_state`**, **`voice_should_wait`**, **`voice_should_respond`**, **`voice_response_readiness`**, **`voice_interrupted`**, **`voice_continuity_hint`**, **`voice_pacing_meta`** — safe defaults when not in a voice cycle.
- **`brain/proactive_triggers.py`**: **`voice_user_turn_priority`** gates proactive recommendations during an active microphone turn processing tick (**turn-taking safety**, not workbench approval changes).
- **`build_prompt`**: Optional **VOICE TURN** guidance when **`_voice_user_turn_priority`** so replies stay concise when **bias_wait** / low readiness (**additive** — does not replace chat path).
- **`brain/calibration.py`**: **`voice_calibration_hints`** counts surfaced in **`summarize_calibration_state()`** meta for later tuning.
- **Intent**: more **human pacing** decisions (wait vs respond hints) and **session continuity** without claiming full duplex speech — **TTS generation unchanged** in this phase.

### Phase 23 — Social continuity and relationship modeling *(live)*

- **`brain/relationship_model.py`**: **`build_social_continuity_result()`** consumes contemplation, reflection, pattern learning, memory importance, proactive, interpretation layer, optional **profile** (`relationship_score`, unresolved **`threads`**), voice globals, and rolling **topic recurrence** (soft in-memory counts per person); outputs **`SocialContinuityResult`** with **`RelationshipSignal`** tags (**familiar / practical / warm / quiet / reflective / unfinished thread / uncertain**) — **probabilistic**, no stable “user is X” claims.
- **`brain/perception_types.py`**: **`RelationshipSignal`**, **`InteractionStyleProfile`**, **`SocialContinuityResult`**; **`PerceptionPipelineBundle.social_continuity`**.
- **`brain/perception_pipeline.py`**: Runs **after contemplation**, before package; **`[perception_pipeline] relationship=...`** log line.
- **`PerceptionState`**: **`relationship_familiarity_score`**, **`relationship_trust_signal`**, **`relationship_summary`**, **`interaction_style_hint`**, **`unfinished_thread_present`**, **`recurring_topics`**, **`recent_social_tone`**, **`relationship_confidence`**, **`relationship_meta`** via **`bundle_to_perception_state`** finalize step.
- **Intent**: grounded **interaction-style hints** and **unfinished-thread awareness** for prompts/routing hooks later — **does not** override safety, workbench approval, or user agency.

### Phase 24 — Long-term memory refinement *(live)*

- **`brain/memory_refinement.py`**: **`build_memory_refinement_result`** / **`build_memory_refinement_result_safe`** layers on Phase 11–12 outputs + Phase 23 **social continuity** + voice/interrupt hints — **`RefinedMemoryDecision`** with **`retention_strength`** / **`retrieval_priority`**, **`MemoryLinkSuggestion`** list (identity, topic, recurring topic, unfinished thread, pattern, reflection category), conservative **suppression** for weak duplicates, low-importance **no_meaningful_change**, uncertain reflection; **does not** replace **`brain.memory_scoring`** or durable storage writes.
- **`brain/perception_types.py`**: **`MemoryLinkSuggestion`**, **`RefinedMemoryDecision`**, **`MemoryRefinementResult`**; **`PerceptionPipelineBundle.memory_refinement`**.
- **`brain/perception_pipeline.py`**: Runs **after social continuity**; **`[perception_pipeline] memory_refined=...`** log line alongside **`[memory_refinement]`** detail lines (bounded verbosity).
- **`PerceptionState`**: **`refined_memory_*`** fields (**class**, **worthy**, **retention**, **retrieval**, **unfinished_thread_candidate**, social/episodic/pattern relevance scalars, **`refined_memory_meta`** with link hints).
- **Intent**: richer **classification / retention weighting / link suggestions** for future persistence and retrieval — **additive**, conservative, **no memory explosion** from weak cues.

### Phase 25 — Dynamic Ollama model routing *(live)*

- **Goal**: Choose among **available Ollama models** as different **reasoning engines** (latency vs depth vs coding repair vs memory maintenance vs perception-heavy turns) while **Ava stays one mind** — **identity, memory, values, relationship continuity, and reflection context** are **not** swapped when the inference tag changes.
- **`config/ava_tuning.py`**: **`ModelRoutingConfig`** / **`MODEL_ROUTING_CONFIG`** — per–cognitive-mode model name strings (defaults: **all modes map to the same tag** as before, so behavior is unchanged until you configure distinct models and pull them in Ollama).
- **`brain/model_routing.py`**: **`build_model_routing_result`** (conservative task signals from voice, workbench, memory refinement, reflection, contemplation, interpretation, user text heuristics) → **`ModelRoutingResult`** with **`routing_reason`**, **`routing_confidence`**, priorities, **`model_candidates`**, **`continuity_preserved`**. Lightweight **`/api/tags`** awareness with **graceful fallback** (never random; unknown tags → configured fallbacks). Future hooks: **`g["_routing_model_override"]`**, **`g["_routing_cognitive_mode_override"]`**.
- **`brain/perception_types.py`**: **`ModelRouteCandidate`**, **`CognitiveModeResult`**, **`ModelRoutingResult`**; **`PerceptionPipelineBundle.model_routing`**.
- **`brain/perception_pipeline.py`**: Runs **after memory refinement**; concise **`[model_routing]`** logs.
- **`PerceptionState`**: **`cognitive_mode`**, **`routing_selected_model`**, **`routing_fallback_model`**, **`routing_reason`**, **`routing_confidence`**, **`routing_meta`** (priorities + classification signals).
- **`avaagent.py`**: **`run_ava`** uses **`routing_selected_model`** when it **differs** from **`LLM_MODEL`** (otherwise reuses the shared **`ChatOllama`** instance — **no extra churn** on the default path).
- **Stability & anti-thrashing**: **stickiness** + **switch cooldown** (tunable) + **social continuity resistance** — the previous effective Ollama tag is kept when the new mode’s **fit gain** is small, the **top-two mode margin** is weak, or the engine was switched very recently; **urgent** coding/reasoning modes and a **strong margin** can bypass cooldown.
- **Live discovery**: **`/api/tags`** with **`ollama list`** CLI fallback; **capability registry** = `config` **profiles** (`ModelCapabilityProfileDef` + `DEFAULT_MODEL_CAPABILITY_PROFILES`) **∪** any **discovered** tag (neutral profile) **×** `available` bit. **Warm fallbacks** never require a specific name to exist in Ollama; best **fit** among available models is used when the config tag is missing.
- **Metadata / light inspection**: optional digest from **`/api/show`** (non-blocking) for explainability; full registry slice in **`routing_meta`**.

### Phase 26 — Bounded curiosity & exploration *(live)*

- **Goal**: Notice **anomalies**, **gaps**, and **unfinished threads** with **structured internal questions** and **soft exploration hints** — **no automatic interrogation**, **no tool/file execution**, **no override** of voice turn-taking, workbench approval, or routing safety.
- **`brain/curiosity.py`**: **`build_curiosity_result_safe`** ingests pattern learning, memory refinement, reflection, contemplation, social continuity, proactive trigger, self-tests, workbench, model routing, identity, interpretation, scene summary — outputs **`CuriosityResult`** with **`exploration_mode`**, **`should_observe` / `should_clarify` / `should_defer`**, **dedup** via **`g["_curiosity_sig_history"]`**, dampening under **voice** or **quiet** preference.
- **`brain/perception_types.py`**: **`CuriosityQuestion`**, **`ExplorationSuggestion`**, **`CuriosityResult`**; **`PerceptionPipelineBundle.curiosity`**.
- **`brain/perception_pipeline.py`**: Runs **after model routing**; **`[perception_pipeline] curiosity=...`** log line plus **`[curiosity]`** detail lines (bounded).
- **`PerceptionState`**: **`curiosity_*`** surface fields + **`curiosity_meta`** (exploration suggestions, boundedness flags, score snapshot).

### Phase 27 — Outcome learning & behavior adjustment *(live)*

- **Goal**: Track **bounded, evidence-backed** hints about **what tended to work vs fail**, **blocked actions**, **suppressed initiative**, **noisy memory routing**, **perception uncertainty**, **voice interruption pressure**, **curiosity churn**, and related patterns — emitting **soft adjustment suggestions only** (**no silent config rewrite**, **no bypass of approvals/safety**, **no autonomous file changes**).
- **`brain/outcome_learning.py`**: **`build_outcome_learning_result_safe`** merges proactive, workbench globals (`_last_workbench_execution_result` / `_last_workbench_command_result`), self-tests, reflection/contemplation, curiosity meta, routing meta, vision trust, interruption timing, memory refinement/importance — maintains **`g["_outcome_learning_tally"]`** for repetition-weighted confidence.
- **`brain/perception_types.py`**: **`OutcomeObservation`**, **`BehaviorAdjustmentSuggestion`**, **`OutcomeLearningResult`**; **`PerceptionPipelineBundle.outcome_learning`**.
- **`brain/perception_pipeline.py`**: Runs **after curiosity**; **`[perception_pipeline] outcome_learning=...`** plus **`[outcome_learning]`** detail lines.
- **`PerceptionState`**: **`outcome_learning_*`**, **`suggested_behavior_adjustment`**, **`adjustment_confidence`**, **`adjustment_target`**, **`outcome_learning_meta`**.

### Phase 28 — Human-style emotional and conversational nuance *(live)*

- **Goal**: Make interaction feel **more naturally human** via **bounded**, **evidence-based** guidance — **warmth**, **practicality/directness**, **quiet restraint**, **softness**, **seriousness**, **humor tolerance**, **verbosity**, **emotional pacing**, and **restraint** — **without** inventing emotions, **without** rewriting replies in this phase, and **without** unstable personality swings or overrides of safety, approvals, or user control.
- **`brain/conversational_nuance.py`**: **`build_conversational_nuance_safe`** consumes Phase 22–27 structured outputs (voice **`VoiceConversationResult`** when present, social continuity, reflection, contemplation, proactive suppression, pattern unusualness, interpretation/scene confidence, outcome learning, curiosity, routing meta, memory refinement social relevance, etc.) → **`ConversationalNuanceResult`** + **`ToneGuidanceProfile`**. **Prior-tone blending** and **mixed-evidence penalties** keep shifts conservative; humor/lightness requires **positive aggregate evidence**.
- **`brain/perception_types.py`**: **`NuanceSignal`**, **`ToneGuidanceProfile`**, **`ConversationalNuanceResult`**; **`PerceptionPipelineBundle.conversational_nuance`**.
- **`brain/perception_pipeline.py`**: Runs **after outcome learning**, before **`PackageOutput`**; concise **`[perception_pipeline] nuance=... tone=...`** plus **`[conversational_nuance]`** lines (two lines max per turn).
- **`brain/perception_state_adapter.py`**: **`apply_conversational_nuance_to_perception_state`** in **`_finalize_perception_runtime_context`** **after** **`apply_outcome_learning_to_perception_state`**.
- **`PerceptionState`**: **`nuance_tone`**, **`nuance_summary`**, **`nuance_confidence`**, scalar levels, **`nuance_meta`** (pacing hint, signal snapshot, tone profile subset) — safe defaults match idle **`ConversationalNuanceResult`** when bundle field is absent.

### Phase 29 — Multi-session strategic continuity *(live)*

- **Goal**: Carry **grounded** cross-session context — **unfinished threads**, **strategic goals**, **maintenance/repair** state, **outcome-learning adjustments**, **relationship/profile** lines, and **style/nuance** hints — as **short structured threads**, not memory dumps. **No** invented continuity, **no** auto workbench actions, **no** prompt bloating.
- **Identity anchors (primary):** **`ava_core/IDENTITY.md`** (core self), **`ava_core/SOUL.md`** (values / boundaries / self-guidance), **`ava_core/USER.md`** (durable user relationship) load **first** every tick — bounded excerpts as **`identity_anchor_thread`** rows **before** goals / reflection / social layering. **`BOOTSTRAP.md`** is **first-run scaffolding only**: omitted once IDENTITY/SOUL have substantive content. **No** conflicting invented self vs these files — downstream should treat anchors as authoritative over speculative reflection. Runtime **never writes** these files here; IDENTITY/SOUL edits assume **elevated approval**; USER.md **reviewable** flows (see project conventions).
- **`brain/session_continuity.py`**: **`build_strategic_continuity_safe`** reads **durable** anchors + `state/goal_system.json`, `profiles/<person>.json`, `memory/self reflection/self_model.json` (small slices) and merges **Phase 16–18, 23–28** pipeline results (social continuity, memory refinement link hints, workbench/self-tests, outcome learning, curiosity, nuance, reflection/contemplation when confident).
- **`brain/perception_types.py`**: **`ContinuityThread`**, **`SessionCarryoverSummary`**, **`StrategicContinuityResult`**; **`PerceptionPipelineBundle.strategic_continuity`**.
- **`brain/perception_pipeline.py`**: Runs **after conversational nuance**, before **`PackageOutput`**; **`[perception_pipeline] continuity_session=... conf=...`** plus two-line **`[session_continuity]`** cap.
- **`PerceptionState`**: **`strategic_continuity_summary`**, **`strategic_continuity_confidence`** (distinct from Phase 7 temporal **`continuity_confidence`**), **`active_threads`**, **`strategic_priorities`**, **`relationship_carryover`**, **`maintenance_carryover`**, **`continuity_scope`**, **`continuity_meta`**.

### Phase 30 — Supervised self-improvement loop *(live)*

- **Goal**: One **structured**, **supervised** snapshot linking **self-tests**, **workbench proposals**, **`g`** execution/rollback hooks, **reflection**, **contemplation**, **outcome learning**, and **strategic continuity** — issue → proposal → approval → execution → reflection → carry-forward. **No** auto-approval, **no** auto-execute, **no** bypass of allowlists or elevated rules; **ava_core** identity anchors (Phase 29) remain **above** maintenance framing.
- **`brain/self_improvement_loop.py`**: **`build_supervised_self_improvement_loop_safe`** → **`ImprovementLoopResult`** with **`ImprovementStepStatus`** stages; concise **`[self_improvement_loop]`** logs and **`[perception_pipeline] improvement_loop=...`**.
- **`brain/perception_types.py`**: **`ImprovementCycle`**, **`ImprovementLoopResult`**, **`ImprovementStepStatus`**; **`PerceptionPipelineBundle.improvement_loop`**.
- **`brain/perception_pipeline.py`**: Runs **after strategic continuity**, before **`PackageOutput`**.
- **`PerceptionState`**: **`improvement_loop_*`** surface fields + **`improvement_loop_meta`** (rollback/await flags, identity-anchor respect bit).

### Phase 31 — Continuous heartbeat runtime & bounded adaptive learning *(live)*

- **Goal**: Move Ava from **pure turn-based** perception toward a **quiet resident loop** — each **`run_perception_pipeline`** tick can advance **heartbeat continuity**, observe **meaningful deltas** (self-tests, workbench, strategic carryover, voice floor, curiosity, outcomes), and apply **evidence-weighted preference drift** — **without** chatting autonomously, **without** approving workbench actions, **without** rewriting **`ava_core/IDENTITY.md`**, **`SOUL.md`**, or **`USER.md`**, and **without** bypassing supervision.
- **Heartbeat (`brain/heartbeat.py`)**: **`run_heartbeat_tick_safe`** → **`HeartbeatTickResult`** (`HeartbeatMode`: `idle_monitoring`, `active_presence`, `conversation_active`, `maintenance_watch`, `learning_review`, `quiet_recovery`, `no_heartbeat`). Wall-clock **cadence** skips heavy work when idle; **`g["_heartbeat_force_tick"]`** / **`g["_heartbeat_event_reason"]`** allow **event-driven** wakeups. Persisted counters in **`state/heartbeat/heartbeat_state.json`**. **`bootstrap_heartbeat_runtime(globals())`** from **`avaagent.py`** loads carryover once at startup (one concise log). **`[heartbeat]`** lines are **throttled** (not every camera frame).
- **Adaptive learning (`brain/adaptive_learning.py`)**: **`run_adaptive_learning_safe`** → **`AdaptiveLearningResult`**; bounded **EWMA** scores per **`LearningFocus`** (pacing, interruption/yield, curiosity, memory, proactive triggers, repair proposals, social continuity, response-style tendency, user comfort). Reads Phase 27–28 / social / voice evidence — **structured aggregation**, not trial-and-error autonomy. Preferences in **`state/learning/adaptive_preferences.json`** (lightweight, rebuild-safe). **`[adaptive_learning]`** logs only on meaningful updates.
- **`brain/perception_types.py`**: **`HeartbeatEvent`**, **`HeartbeatState`**, **`HeartbeatTickResult`**, **`AdaptiveLearningResult`**, **`HeartbeatMode`**; **`PerceptionPipelineBundle.heartbeat`** + **`adaptive_learning`**.
- **`brain/perception_pipeline.py`**: Runs **after Phase 30**, before **`PackageOutput`** / **`record_calibration_tick`**.
- **`PerceptionState`**: **`heartbeat_*`**, **`learning_*`**, and **`heartbeat_meta`** (includes nested **`learning`** summary from adaptive pass when present).

---

## Post-foundation phase index (Phases 21–31) — shipped

Work after Phase 20 **extended** the shipped architecture (calibration, voice, relationship depth, memory quality, routing, curiosity, outcomes, nuance, multi-session strategy, supervised improvement, heartbeat/adaptive preferences)—**not** a parallel rewrite. The per-phase subsections above are authoritative; this table is an index.

| Phase | Theme |
|---|---|
| **21** | **Real-world calibration and tuning** *(live)* — measurement, watchlists, safer iteration on `config/ava_tuning.py` (`brain/calibration.py`) |
| **22** | **Natural voice conversation and turn-taking** *(live)* — turn state, pause/readiness hints, interruption overlap signals, continuity; record-stop UX (not full streaming) |
| **23** | **Social continuity and relationship modeling** *(live)* — soft familiarity/tone/style hints, unfinished-thread signal, recurring topics; bounded evidence |
| **24** | **Long-term memory refinement** *(live)* — refined class/worthy/retention/retrieval + link hints on top of Phase 12; selective, bounded |
| **25** | **Dynamic cognitive / model routing** *(live)* — switch among **available Ollama models** as different reasoning “brains” while **identity, memory, values, and continuity stay unified** (interchangeable inference layers under one mind) |
| **26** | **Curiosity and bounded exploration** *(live)* — anomaly / gap awareness, structured internal prompts, non-intrusive exploration hints |
| **27** | **Outcome learning and behavior adjustment** *(live)* — repeated success/failure pattern hints; **advisory** adjustment signals only — **no automatic behavior override** |
| **28** | **Human-style emotional and conversational nuance** *(live)* — bounded tone guidance; pacing/restraint; warmth/practicality/seriousness balancing; **no unstable personality swings** |
| **29** | **Multi-session strategic continuity** *(live)* — unfinished-thread carryover; strategic and maintenance carryover; bounded relationship continuity across sessions; **concise summaries, not memory dumps** |
| **30** | **Supervised self-improvement loop** *(live)* — issue → proposal → approval → execution → reflection → continuity; **bounded and reviewable**; **no unsafe autonomous override** |
| **31** | **Heartbeat runtime & adaptive learning** *(live)* — resident cadence inside the perception pipeline; event-aware wakeups; bounded preference drift; **identity anchors preserved**; **no autonomous speech or approval bypass** |

**Phase 2 (Prospective Memory)** and other sections below describe **additive / future** capabilities on top of the completed baseline—not missing phases 1–30.

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

## Phase 6 — Better Eyes / Human-Like Vision

**Intent:** Make camera-backed behavior **trustworthy**, **stable across frames**, **honest about uncertainty**, and **continuous** before adding heavy detectors. This complements Phases 1–5 (memory, prospective, threads): continuity in *conversation* only lands if vision does not lie about the present.

**Design rule:** Do **not** lead with YOLO / generic object detection. Trust, freshness, recovery, quality, and identity continuity come first. All later visual claims must pass through the same gates.

### Implementation order (file targets)

| Sub-phase | Focus | Primary files |
|-----------|--------|---------------|
| **E1** | Visual trust foundation: resolved-frame metadata, `vision_status`, trust flags, first-class workspace logging | `brain/camera.py`, `brain/camera_live.py` (timestamps), `brain/perception.py`, `brain/workspace.py`, `avaagent.py` (prompt guards / camera copy) |
| **E2** | Recovery gating + confidence suppression after obstruction/stale/missing | `brain/camera.py`, `brain/perception.py`, `avaagent.py` |
| **E3** | Frame quality subsystem (blur, light, exposure, optional motion/occlusion hints) | `brain/camera.py` or `brain/frame_quality.py`, `brain/perception.py` |
| **E4** | Identity continuity (last confirmed, decay, same-person likelihood, hierarchy) | `brain/perception.py`, `brain/camera.py`, optional `brain/identity_continuity.py` |
| **E5** | Short-term visual memory + compact scene summaries | `brain/workspace.py`, `brain/perception.py`, `avaagent.py`, initiative hooks |
| **E6** | Attention / salience (centered face, sudden change, scene delta) | `brain/attention.py`, `brain/perception.py`, initiative |
| **E7** | Show-and-tell / minimal object layer (still trust-gated) | new thin module + `avaagent.py`; **after** E1–E6 |
| **E8** | Visual-to-memory linking (recurrence + relevance + confidence) | `brain/memory.py`, camera initiative, guards |

### E1 — Visual trust foundation *(in progress in repo)*

- Resolved frames carry: freshness age (from `camera_live` wall capture time + UI fingerprint aging), source, sequence, quality score/reasons (minimal OpenCV heuristic), `recovery_state`, streak, `last_stable_identity` snapshot.
- States: `no_frame`, `stale_frame`, `recovering`, `stable`, `low_quality`.
- Perception sets real `identity_confidence` / `continuity_confidence` (E1-level; E4 deepens continuity).
- Face identity, emotion, and present-tense scene only when `visual_truth_trusted`.
- Prompts: uncertainty wording; **no** invented UI/snapshot refresh diagnoses without an explicit `UI_HEALTH` signal.

### E2 — Recovery gating and confidence suppression

- After dropout/stale/low-quality, require consecutive fresh, good-quality frames before `stable`.
- While `recovering`, treat identity/emotion as **provisional** (already suppressed until stable; E2 may add explicit “provisional” copy for post-stable soft landing).

### E3 — Frame quality system

- Expand heuristics: blur, darkness, overexposure, optional smear/occlusion; single `frame_quality` in `[0,1]` + reason strings; tie into initiative and autonomy thresholds.

### E4 — Identity continuity

- Track last confirmed identity, time since confirmation, decay; hierarchy: confirmed recognition → continuity likely → unknown face → no face; never instant amnesia when the same face likely persists.

### E5 — Short-term visual memory

- Rolling few-second buffer: who was present, what changed, entrants/exits, stable scene line; feed prompts, “what do you see?”, and initiative.

### E6 — Attention / salience

- Inputs: centered/nearest face, sudden change, held object (later), motion/scene change; drives summaries and initiative candidates.

### E7 — Show-and-tell / object layer

- Minimal object/spatial/color layer; **no** bypass of trust/quality/continuity; YOLO/MediaPipe only after E1–E6 are solid.

### E8 — Visual-to-memory linking

- Write visual memories only with sufficient salience, recurrence, relevance, and stable confidence.

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
| **6, E1** | **Better Eyes — visual trust foundation** | 🟢 Low–medium | **High** (honest vision) |
| 6, E2–E8 | Recovery, quality, continuity, visual memory, salience, objects, memory link | 🟡→🔴 | High (staged) |
