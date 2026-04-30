# Ava Agent v2 — Complete Development Roadmap
**Last updated:** 2026-04-29
**Repo:** `Tzeke000/Ava-Agent-v2` (public)
**Total commits:** 184 (`git log --oneline | wc -l`)

This is the complete historical record. Phases 1–100 plus all post-100 stabilization, every significant hot fix, current status, and next priorities. Reconstructed from `git log --reverse` and existing phase docs.

---

## Section 1 — Phase History (1–100)

### Foundation: Phases 1–5 (AWARE → WORKSPACE)

| Phase | Title | Commit | Status |
|---|---|---|---|
| 1 | **AWARE** — perception stack scaffold, camera frame ingest, basic profile awareness | `a75d238` | ✅ COMPLETE |
| 2 | **RELATIONAL** — multi-user profiles, trust levels, per-person memory | `ad1dbfa` | ✅ COMPLETE |
| 3 | **REFLECTIVE** — reflection loop, self-narrative scaffold | `aa1930f` | ✅ COMPLETE |
| 4 | **SELF-MODELING** — internal self-state tracking, mood + energy primitives | `56e3ac2` | ✅ COMPLETE |
| 5 | **WORKSPACE** — workbench command pipeline, supervised proposal flow | `63582d5` | ✅ COMPLETE |

### Core Staged Architecture: Phases 6–30

Commits during this era are mostly bug-fix passes against the perception/memory pipeline. The phases themselves were structural milestones documented in `AVA_HISTORY.md`:

| Phases | Theme | Status |
|---|---|---|
| 6–10 | Memory scoring, importance gates, retrieval ranking | ✅ COMPLETE |
| 11–15 | Identity resolution, recognition continuity, face-stable tracking | ✅ COMPLETE |
| 16–20 | Workbench proposals, command handling, rollback path, audit trail | ✅ COMPLETE |
| 21–25 | Model routing (cognitive_mode → model selection), capability profiles | ✅ COMPLETE |
| 26–30 | Strategic continuity, social continuity, memory refinement, prospective memory | ✅ COMPLETE |

Notable commits in this band: `9116c30` "phase 20 done", `45d1a5d` "phase 30 done".

### Phase 31 — Resident Heartbeat
- Background continuity tick between perception cycles
- `brain/heartbeat.py` + `HeartbeatState`/`HeartbeatTickResult` types
- Adaptive learning hooks; quiet, mode-dependent cadence
- Commits: `b86807d`, `c9f0fbf`, `5a7f193`, `9480b00`
- ✅ COMPLETE

### Phase 32 — Operator HTTP + Desktop App Foundation
- FastAPI operator server hardening (port 5876)
- First Tauri desktop app shell — `apps/ava-control`
- Concern gating, fast path classifier, camera fix
- Commit: `beb0cc0` "feat: desktop app UI, camera fix, concern gating, fast path classifier"
- ✅ COMPLETE

### Phase 33 / 33b — Shutdown Ritual + Continuity Glue
- `brain/shutdown_ritual.py`, pickup notes between sessions
- Commit: `812ecc7` "Phase 33b shutdown ritual, MeloTTS scaffold, TTS toggle, shutdown button"
- ✅ COMPLETE

### Phase 34 — MeloTTS Scaffold
- TTS framework with pyttsx3 fallback
- ✅ COMPLETE (later replaced by Kokoro)

### Phase 35 — Fury HistoryManager
- `brain/history_manager.py` — context length budgeting, summary windows
- ✅ COMPLETE

### Phase 36 — Social Chat Routing Fix
- `config/ava_tuning.py` — social_chat_mode score 0.85, mistral:7b path stabilised
- ✅ COMPLETE

### Phase 37 — Emotional Orb UI
- 27 emotion shape morphs, 5-layer Three.js orb, brain tab, voice tab
- Commits: `da42ad7`, `3834c56`, `43f97dd`, `159e9d3`
- ✅ COMPLETE

### Phase 38 — Fine-Tuning Pipeline
- `brain/finetune_pipeline.py` — 75 conversation examples → `ava-personal:latest`
- Operator endpoints prepare/start/status/log + UI tab
- Commit: `575cb64`
- ✅ COMPLETE

### Phase 39 — LLaVA Scene Understanding
- `brain/scene_understanding.py` scaffold; LLaVA model probe at startup
- ✅ COMPLETE

### Phase 40 — Deep Self-Awareness
- `brain/deep_self.py` — ZekeMindModel, value-conflict resolution, self-critique scoring, repair queue
- Commit: `74fbe67`
- ✅ COMPLETE

### Phase 41 — Tools Foundation
- `tools/tool_registry.py`, `tools/web/`, `tools/system/file_manager.py`, diagnostics
- Tier 1/2/3 risk model; three-law guardrails
- ✅ COMPLETE

### Phase 42 — Visual Memory
- `brain/visual_memory.py` — cluster-fk inspired episodic visual memory
- ✅ COMPLETE

### Phase 43 — Voice Pipeline
- pyttsx3 + Microsoft Zira TTS; STT scaffold; sounddevice integration
- Commit: `de2b068`
- ✅ COMPLETE

### Phase 44 — ava-personal as Primary Brain
- `_route_model` checked first in fast path; `brain/model_evaluator.py` self-evaluation
- `state/model_eval_p44.json` — bootstrap decision (≥0.60 win rate → `confirmed_primary`)
- Commit: `4c24f76`
- ✅ COMPLETE

### Phase 45 — Concept Graph Evolution
- `decay_unused_nodes`, `boost_from_usage`, `get_related_concepts` with `via`/relationship fields
- ACTIVE CONCEPTS prompt block; weekly heartbeat-driven decay
- Commit: `3590746`
- ✅ COMPLETE

### Phase 46 — Hot-Reload Tool Registry
- `_FileWatcher` re-imports `tools/*.py` every 5s; `# SELF_ASSESSMENT:` comment as description
- `/api/v1/tools/reload` endpoint
- Commit: `41f7ebd`
- ✅ COMPLETE

### Phase 47 — Watchdog Restart System
- `scripts/watchdog.py` polls `state/restart_requested.flag`, kills + restarts avaagent by PID
- `tools/system/restart_tool.py` Tier 1 restart request
- `start_ava_desktop.bat` launches watchdog alongside avaagent
- Commit: `7c17d2f`
- ✅ COMPLETE

### Phase 48 — Desktop Widget Orb
- Second Tauri window — 150×150 transparent always-on-top, `?widget=1` URL param
- `WidgetApp.tsx`, position persistence via `/api/v1/widget/position`
- Commit: `ad7a56d`
- ✅ COMPLETE

### Phase 49 — Screen Pointer Behavior
- `pointer` shape morph in `OrbCanvas.tsx`
- `tools/system/pointer_tool.py` Tier 1 — pywinauto coordinate lookup, sets `_widget_pointing`
- Commit: `e72b505`
- ✅ COMPLETE

### Phase 50 — Audio Visualization on Orb
- `tts_engine._estimate_amplitude(text)` + `speaking`/`amplitude` properties
- App.tsx wires `tts_speaking`/`tts_amplitude` to `OrbCanvas`
- Listening spiral animation
- Commit: `3003e19`
- ✅ COMPLETE

### Phases 51–54 — Computer Control
| Phase | Component | Status |
|---|---|---|
| 51 | UI accessibility tree tool (`pywinauto`) | ✅ |
| 52 | Smart screenshot management (`tools/system/screenshot_tool.py`) | ✅ |
| 53 | PyAutoGUI computer control (Tier 2) — `move_mouse`, `click`, `type_text`, `press_key`, `scroll` | ✅ |
| 54 | System stats monitoring (`psutil`, 30s cache) | ✅ |
- Commit: `13fc4a5`

### Phases 55–56 — UI Polish
| Phase | Component | Status |
|---|---|---|
| 55 | Drag-and-drop file input via `@tauri-apps/api/event` | ✅ |
| 56 | Expanded orb expressions — 8 new shapes (cube, prism, cylinder, infinity, double_helix, burst, contracted_tremor, rising) | ✅ |
- Commit: `00d5fd0`
- `tools/ava/style_tool.py` — Ava proposes her own expression mappings via `state/ava_style.json`. **Bootstrap.**

### Phases 57–60 — Capability Expansion
| Phase | Component | Status |
|---|---|---|
| 57 | Wake word detection — Porcupine + whisper-poll fallback | ✅ |
| 58 | Boredom autonomous leisure (`autonomous_leisure_check`) | ✅ |
| 59 | Chrome Dino game automation (PIL screen capture, dark-pixel obstacle detect) | ✅ |
| 60 | Minecraft bot via mineflayer (Node subprocess + JSON protocol) | ✅ |
- Commit: `afdb74b`

### Phases 61–63 — Multiplayer + Real-time
| Phase | Component | Status |
|---|---|---|
| 61 | Minecraft companion behaviors — `greet_player`, `share_discovery`, `warn_threat` | ✅ |
| 62 | Clap detector via sounddevice RMS (originally MeloTTS upgrade — pivoted) | ✅ |
| 63 | WebSocket transport (`/ws` endpoint, snapshot deltas, REST polling fallback) | ✅ |
- Commit: `964ae0a`

### Phases 64–68 — Memory + Self
| Phase | Component | Status |
|---|---|---|
| 64 | Persistent episodic memory (`brain/episodic_memory.py`) — memorability formula, importance×0.4 + novelty×0.3 + emotional_intensity×0.3 | ✅ |
| 65 | Emotional continuity — mood carryover with decay across sessions | ✅ |
| 66 | Ava's own goals (`brain/goal_system_v2.py`) — emerges from curiosity, **no defaults** | ✅ |
| 67 | Relationship arc stages — Acquaintance / Friend / Close Friend / Trusted Companion | ✅ |
| 68 | True self-modification — identity proposals, routing proposals, approval workflow | ✅ |
- Commit: `44b8eb2`

### Phases 70–71 — Multi-Agent + Long Horizon
| Phase | Component | Status |
|---|---|---|
| 70 | Emil bridge — multi-agent on port 5877 | ✅ |
| 71 | Long-horizon planning — `brain/planner.py`, AvaStep/AvaPlan via qwen2.5:14b | ✅ |
- Commit: `aa9be1d`

### Phase 69
- Originally "Horizon Zero Dawn gaming"
- ⏭ SKIPPED — replaced by lower-priority work

### Refactor — `146091e`
- Split `avaagent.py` into modular `brain/` modules; full integration fix pass

### Phases 72–78 — Voice Production + Tabs
| Phase | Component | Status |
|---|---|---|
| 72 | Bundle splitting (193KB main + Three.js separate) | ✅ |
| 73 | STT VAD-based `listen_session()` with silence detection | ✅ |
| 74 | Full STT→LLM→TTS voice loop background daemon | ✅ |
| 75 | Fine-tune auto-scheduler (14 days, ≥50 turns) | ✅ |
| 76 | LLaVA vision startup logging | ✅ |
| 77 | Clap auto-calibration (ambient_rms × 3.0, later 5.0) | ✅ |
| 78 | Emil tab + Proposals tab in operator panel | ✅ |
- Commit: `0a585d7`

### Phase 79 — Person Onboarding
- 13-stage flow: greeting → 5 photo angles → confirmation → name/pronouns/relationship → complete
- Operator endpoints + UI overlay
- Commit: `c00b5b3`
- ✅ COMPLETE

### Phase 80 — Profile Refresh
- `refresh_profile()`, `detect_refresh_trigger()` — retake photos if quality<0.7 or 180+ days
- Commit: `806e134`
- ✅ COMPLETE

### Phase 81 — face_recognizer.py
- `FaceRecognizer` class using face_recognition lib + dlib
- `add_face`, `update_known_faces`, operator snapshot confidence
- Commit: `a25c191`
- ✅ COMPLETE (later superseded by InsightFace, kept as fallback)

### Phase 82 — Multi-Person Awareness
- `tick_multi_person_awareness`, face change detection, current_person snapshot block
- Commit: `4e0483a`
- ✅ COMPLETE

### Phase 83 — Windows Notifications
- plyer + PowerShell fallback; `notification_count_today` in snapshot
- Commit: `99e6924`
- ✅ COMPLETE

### Phase 84 — Optional Morning Briefing
- `should_brief()` score-based, generated via qwen2.5:14b, TTS delivery
- Commit: `75c710f`
- ✅ COMPLETE

### Phase 85 — Memory Consolidation
- Weekly: episode review + concept graph pruning + self model + journal entry + identity check
- Commit: `b781be0`
- ✅ COMPLETE

### Phase 86 — Private Journal
- `write_entry`, `share_entry`, `compose_journal_entry` via LLM
- Journal tab in operator panel + journal endpoints
- Commit: `7beea31`
- ✅ COMPLETE

### Phase 87 — Voice Personality Development
- `VoiceStyle` tracking; `voice_style_adapt()`; pyttsx3 rate/volume from style; gradual evolution
- Commit: `0bf4624`
- ✅ COMPLETE

### Phase 88 — Ambient Intelligence
- `observe_session()`, `get_context_hint()`; hourly/weekday/window patterns
- Fast-path injection
- Commit: `7bc84f5`
- ✅ COMPLETE

### Phase 89 — Curiosity Engine Upgrade
- `prioritize_curiosities`, `pursue_curiosity` (web → graph → journal)
- `add_topic_from_conversation`; stale-topic heartbeat check
- Commit: `fd4c6e5`
- ✅ COMPLETE

### Phase 90 — Tool Building
- `tools/ava/tool_builder.py` — Ava writes Python tools at runtime; safety + compile checks
- Output dir: `tools/ava_built/`
- Commit: `46d3364`
- ✅ COMPLETE

### Phase 91 — Relationship Memory Depth
- `memorable_moments`, `emotional_history`, `conversation_themes`, `trust_events`
- Prompt injection
- Commit: `86f09b3`
- ✅ COMPLETE

### Phase 92 — Emotional Expression in Text
- `ExpressionStyle`, `apply_emotional_style`; wired into reply_engine
- Commit: `d375b52`
- ✅ COMPLETE

### Phase 93 — Learning Tracker
- `record_learning`, `get_knowledge_summary`, `what_have_i_learned_this_week`, `knowledge_gaps`
- Wired into curiosity + consolidation
- Commit: `b727256`
- ✅ COMPLETE

### Phase 94 — Operator Panel Polish
- Learning tab + People tab; profiles list endpoint; learning log/gaps/week endpoints
- Commit: `8896cb3`
- ✅ COMPLETE

### Phase 95 — Privacy Guardian
- `scan_outbound`, `scan_tool_action`, `data_audit`, `blocked_actions` log
- Emil bridge scan + security snapshot block
- Commit: `bb621e5`
- ✅ COMPLETE

### Phase 96 — Response Quality
- too_short / too_long / repetitive checks; one regeneration attempt
- Opener diversity tracking; quality log
- Commit: `7698091`
- ✅ COMPLETE

### Phase 97 — Minecraft World Memory
- `MinecraftWorldMemory` — locations, structures, players, events
- `world_summary` for prompt; companion_tool integration
- Commit: `7d12514`
- ✅ COMPLETE

### Phase 98 — Progressive Trust System
- `state/trust_scores.json`; `get_trust_level`, `update_trust_level`
- `trust_context` for prompt; trust snapshot in operator
- Commit: `f92f7ae`
- ✅ COMPLETE

### Phase 99 — Integration Tests
- 20/20 static integration tests; full compile sweep
- (Verified inside the Phase 100 milestone commit)
- ✅ COMPLETE

### Phase 100 — Milestone: Ava is Alive
- `brain/milestone_100.py` — Ava's own reflection on reaching Phase 100
- Full Tauri build clean
- Commit: `e80e1d3`
- ✅ COMPLETE

---

## Section 2 — Post-100 Stabilization

Work after the Phase 100 milestone, grouped by topic. Commit hashes are the ones currently on master.

### 2.1 Cloud Models + Connectivity
- **`4274ac7`** — cloud models (`kimi-k2.6:cloud`, `qwen3.5:cloud`, `glm-5.1:cloud`, `minimax-m2.7:cloud`), `brain/connectivity.py` 30s online/offline cache, image generation tool, routing expansion
- **`60a96ce`** — capability profiles for `deepseek-r1:14b`, `mistral-small3.2`, `llava:13b`, `qwen2.5:32b`

### 2.2 Dual-Brain Parallel Inference
- **`57d178b`** — `brain/dual_brain.py` (554 LOC). Stream A foreground (`ava-personal:latest`) + Stream B background (`qwen2.5:14b` / cloud). Live thinking, seamless handoff via `handoff_insight_to_foreground`.

### 2.3 Eye Tracking + Expression Detection (MediaPipe-based)
- **`5b466b6`** — `brain/eye_tracker.py`, `brain/expression_detector.py`, `brain/video_memory.py`, `tools/system/eye_tracking_tool.py`
- **`5b22890`** — fix correct MediaPipe iris landmark indices (left 468–472, right 473–477)

### 2.4 Startup Hardening
- **`42f95cd`** — concept_graph bootstrap, self_model update, vectorstore init, milestone_100 all moved to background daemon threads; main thread reaches operator HTTP in <10s
- **`2382d8f`** — concept_graph .tmp lock on Windows fix; brain_graph 0-nodes-in-snapshot fix
- **`bb6b4f7`** — concept_graph.json.tmp WinError 5 — process lock, skip-if-locked save, stale `.tmp` cleanup on startup
- **`42f95cd`** — startup hang fix with progress logging

### 2.5 Run-time Safety
- **`d187c80`** — run_ava hang timeout protection (90s), widget orb visibility, cloud model priority
- **`f951489`** — comprehensive bug audit + repair pass (`background_ticks.py` mkdir, `dual_brain.py` 6 fixes, `eye_tracker.py`, `concept_graph.py`, `operator_server.py`, `reply_engine.py`, `startup.py`)

### 2.6 Camera Persistence + Live Frame
- **`5d1a180`** — camera capture persistent connection (no per-frame open/close), suppress noisy logs, global crash handler
- **`34da8ea`** — live camera feed in Vision tab, concept_graph save mkdir, `live_frame` HTTP endpoint
- **`97409de`** — STT engine bootstrap for voice loop, live camera feed published from background thread

### 2.7 Gradio Removal + Architecture Cleanup
- **`ac550e7`** — removed Gradio entirely; fix WS flicker, fix double startup; `start_ava_dev.bat` hot-reload mode
- **`ae1b1fd`** — cleanup: removed DeepFace, dead imports, residual Gradio remnants, fix selftest

### 2.8 Online/Offline Stability
- **`5183e78`** — online flicker fix — 3-failure threshold + silent connecting window + 5s poll interval
- **`242ecb9`** — keepalive stability, app connection retry, self_model timestamp crash fix

### 2.9 Face Recognition Threading
- **`aa01b5b`** — face_recognizer thread-safe singleton + diagnostic prints on all exit paths

### 2.10 Widget + UI Polish
- **`44bb51f`** — widget capabilities, minimize detection polling, removed wrong blur fallback
- **`02c9f1f`** — widget transparent background — CSS override + `backgroundColor` in `tauri.conf.json`
- **`1975dff`** — live camera on all tabs, gate D3 brain reinit, memo OrbCanvas
- **`59eaca9`** — buffered-only live frame, 90s `run_ava` timeout, 5s tick timeout, voice-loop diagnostics
- **`4ea87e8`** — widget move tool, app launcher, browser navigation tools

### 2.11 Voice Loop Stability
- **`dc645d1`** — clap detector — 5× ambient mult, 0.15 floor, 3s cooldown; voice_loop full per-step logging
- **`7534621`** — run_ava timeout, orb thinking pulse, always-on voice, clap sensitivity, brain tab stability, live camera

### 2.12 TTS COM-Safe + Ollama Lock + Fast Path
- **`fa583ea`** — TTS COM thread (TTSWorker init pyttsx3 inside dedicated thread), Ollama lock, fast path timing, chat history, face greeting, clipboard, proactive

### 2.13 Kokoro Neural TTS
- **`346d30c`** — Kokoro neural TTS, orb voice reactions, real amplitude RMS streaming, companion orb sync (28 voices, per-emotion mapping)

### 2.14 InsightFace GPU + 3D Brain Graph
- **`357dd69`** — InsightFace GPU face overlay, 3D brain graph (`3d-force-graph 1.80`), Whisper base, orb breathing, chat tab fixes
- **`3a5a333`** — InsightFace overlays, smart wake word, attentive state, expression calibration, voice mood, 3D brain graph, orb breathing
- **`9d07838`** — register pip-installed CUDA DLL dirs (cublas/cudnn/cufft/curand/cusolver/cusparse/cuda_runtime/nvrtc/nvjitlink) so InsightFace runs on GPU instead of silent CPU fallback

### 2.15 Audit + Wiring Verification
- **`94bca07`** — dead code cleanup (deleted `brain/vision.py`), wiring verification, onboarding InsightFace, performance fixes, health check (frame_store age replaces stale CAMERA_LATEST_JSON_PATH)

### 2.16 Voice-First UI
- **`8affd49`** — voice-first UI: app discovery (367 apps + 32 games), 40-builtin voice command router, custom tabs, command_builder, correction handler, pointing via LLaVA, reminders, "Ava builds her own UI"

### 2.17 Signal Bus / Event-Driven
- **`755f539`** — event-driven `brain/signal_bus.py`. Win32 `AddClipboardFormatListener` (zero-poll clipboard), `SetWinEventHook(EVENT_SYSTEM_FOREGROUND)` (zero-poll window switches), `ReadDirectoryChangesW` (zero-poll app installs)

### 2.18 Voice Critical Fixes
- **`a740bcc`** — clap=direct wake (no classification), Whisper biased toward "Ava" via `initial_prompt`, clarification waits for yes/no, OutputStream protected playback, clap floor 0.35

### 2.19 openWakeWord + Silero VAD
- **`4477aa2`** — production wake-word stack: openWakeWord ONNX (<1% CPU), Silero VAD (RTF 0.004), Whisper transcript Eva→Ava normalization, `models/wake_words/hey_ava.onnx` slot reserved

### 2.20 ava-gemma4 + mem0 Memory
- **`5c2322c`** — `Modelfile.ava_gemma4` (identity baked from IDENTITY+SOUL+USER), `brain/ava_memory.py` (mem0 + ChromaDB + Ollama), gemma4 vision capability, 5 memory voice commands, memory tab in App.tsx
- **`c54bbcb`** — full handoff + roadmap update; wake_word prefers custom hey_ava → hey_jarvis fallback (with phonetic benchmark)

### 2.21 Repository Hygiene
- **`117428f`** — gitignore biometric (`faces/`), per-machine state (`.claude/`), and large local models (`models/wake_words/*.onnx`); untrack 149 already-committed runtime files

---

## Section 3 — Hot Fixes Log

Significant bug fixes ordered by impact. Each row: commit hash + what was broken + what fixed it.

| Date | Commit | Bug | Fix |
|---|---|---|---|
| 2026-04-29 | `5c2322c` then `117428f` | mem0ai install upgraded protobuf to 6.33.6 → MediaPipe broke (`'MessageFactory' object has no attribute 'GetPrototype'`) | `pip install "protobuf>=3.20,<4" --force-reinstall`. Both libs work with 3.20.x. |
| 2026-04-29 | `a740bcc` | TTS could be cut off mid-sentence by window focus changes / mouse clicks / other audio. `tts_engine._play_wav` ran `self.stop()` on every fresh utterance — cutting off in-flight playback | `sd.OutputStream` chunked playback at 2048 samples; `_muted()` is the only mid-stream abort condition; `tts_worker.stop()` refuses to run unless mute is set; `THREAD_PRIORITY_HIGHEST` so audio is never starved |
| 2026-04-29 | `a740bcc` | Whisper dropped "Ava" from transcripts, causing wake to miss | `initial_prompt="Ava, hey Ava,"` + `hotwords="Ava"` (with TypeError fallback) + `_normalize_transcript` (Eva→Ava, Aye va→Ava, etc) |
| 2026-04-29 | `a740bcc` | Clap detector firing on keyboard clicks (threshold 0.236) | Raised `_MIN_THRESHOLD_FLOOR` 0.15 → 0.35; tightened double-window 0.8s → 0.6s; min separation 0.1s; cooldown 4s |
| 2026-04-29 | `a740bcc` | Clarification question not waiting for answer | New `voice_loop._handle_clarification` blocks ≤8s on `stt.listen_short()`, parses yes/no, learns mapping |
| 2026-04-29 | `9d07838` | InsightFace silently fell back to CPU — `cublasLt64_12.dll` missing | `_add_cuda_paths()` registers `site-packages/nvidia/*/bin/` with `os.add_dll_directory` BEFORE the ORT import. All 5 buffalo_l ONNX sessions now report `Applied providers: ['CUDAExecutionProvider', 'CPUExecutionProvider']` |
| 2026-04-29 | `94bca07` | `Health: ERROR | camera:error` even when camera was working — health check read stale `CAMERA_LATEST_JSON_PATH` | Read `frame_store.peek_buffer_age_sec()` first; healthy < 5s, degraded < 10s, error > 10s |
| 2026-04-29 | `fa583ea` | pyttsx3 hung silently from voice_loop daemon — COM single-threaded apartment violation | `TTSWorker` runs pyttsx3 inside its own thread with `pythoncom.CoInitialize()`; queue serialises calls |
| 2026-04-29 | `fa583ea` | Ollama model swap contention — Stream A and Stream B fighting for GPU caused 30s+ swap penalties | `brain/ollama_lock.py` process-wide RLock around every invoke; `dual_brain.pause_background_now(30)` on turn entry |
| 2026-04-28 | `aa01b5b` | `face_recognizer` crashed under concurrent calls (dlib C++ not thread-safe) | Thread-safe singleton via `_SINGLETON_LOCK`; double-check inside lock; `_load_lock` serialises load_known_faces |
| 2026-04-28 | `5183e78` | Online/offline indicator flickered constantly | 3-failure threshold + silent 5s connecting window + 5s poll interval |
| 2026-04-28 | `97409de` | Voice loop never started — `stt_engine` was never bootstrapped | Added explicit STT engine init step in startup; voice_loop now finds `g["stt_engine"]` set |
| 2026-04-28 | `ac550e7` | App started twice on `start_ava_desktop.bat` — signal handler + `__main__` guard double-fired | Guard with `_STARTUP_COMPLETE` flag in globals; clean Gradio removal closed the second entry path |
| 2026-04-28 | `2382d8f` / `bb6b4f7` | `concept_graph.json.tmp` corrupted with WinError 5 / 32 (file locked by other process) | Process-level `_SAVE_LOCK`; skip-if-locked save; stale `.tmp` cleanup at startup |
| 2026-04-28 | `42f95cd` | Startup hung at concept graph bootstrap (mistral:7b call on main thread) | Moved concept_graph bootstrap, self_model update, vectorstore init, milestone_100 all to daemon threads |
| 2026-04-28 | `5b22890` | MediaPipe iris tracking returned wrong eye positions | Corrected landmark indices (left 468–472, right 473–477) |
| 2026-04-28 | `d187c80` | `run_ava` could hang indefinitely | 90s outer timeout via `_with_timeout`; 30s prompt-build timeout; 5s tick timeout |

### Earlier critical fixes (pre-`a740bcc`)
| Theme | Commit | Fix |
|---|---|---|
| ThreadPoolExecutor timeout hangs | `fa583ea` (replaced) | Switched from blocking `concurrent.futures.ThreadPoolExecutor.submit(...).result(timeout=)` to daemon-thread + Event pattern in critical paths |
| Dependency conflict (DeepFace) | `ae1b1fd` | Removed DeepFace entirely; vision moved to MediaPipe + InsightFace path |

---

## Section 4 — Current Status Table

| System | Status | Notes |
|---|---|---|
| Phases 1–100 | ✅ Working | All phase commits on master |
| ava-gemma4 (identity-baked primary brain) | ✅ Working | `Modelfile.ava_gemma4` from `gemma4:latest`; `ollama show ava-gemma4` confirms; 3 test prompts return Ava-voiced replies |
| ava-personal:latest (Llama 3.1 fallback) | ✅ Working | Kept as `FOREGROUND_MODEL_FALLBACK`; auto-selected if ava-gemma4 unavailable |
| Stream A — `dual_brain.foreground_model` | ✅ Working | Resolves `ava-gemma4` first via `_resolve_foreground_model()` |
| Stream B — `dual_brain.get_thinking_model()` | ✅ Working | `kimi-k2.6:cloud` when online; `gemma4:latest` local; `qwen2.5:14b` fallback |
| Ollama lock (`brain/ollama_lock.py`) | ✅ Working | RLock + `with_ollama()` wraps every invoke in reply_engine + dual_brain |
| Kokoro TTS | ✅ Working | 28 voices; per-emotion mapping; live RMS amplitude; OutputStream protected playback |
| Whisper base + Silero VAD | ✅ Working | `cuda+float16`; Eva→Ava normalization; initial_prompt biased; `listen_short` for clarifications |
| openWakeWord (hey_jarvis proxy) | ✅ Working | Bundled ONNX; <1% CPU; `models/wake_words/hey_ava.onnx` slot reserved for custom |
| Custom hey_ava model | ⚠️ Pending | Requires WSL2 training pipeline (`docs/TRAIN_WAKE_WORD.md`); benchmark shows hey_jarvis is the only viable proxy among bundled models |
| Clap detector | ✅ Working | Floor 0.35; 0.6s window; 4s cooldown; sets `_wake_source="clap"` |
| Voice loop attentive state | ✅ Working | 60s post-speak window; 0.8s mic poll; speech > 1s → run_ava without wake |
| InsightFace GPU | ✅ Working | `CUDAExecutionProvider` confirmed; ~41ms/frame; runs every 3rd frame in background_ticks |
| Per-person expression calibrator | ✅ Working | EMA baseline α=0.001; calibrates at 300 samples; persists to `state/expression_baseline_{pid}.json` |
| Eye tracking (MediaPipe) | ✅ Working | Pinned to protobuf 3.20.x |
| Camera annotator overlays | ✅ Working | Bbox + 106 landmarks + 3D pose arrows + age/gender + attention overlay |
| Camera health check | ✅ Working | Reads `frame_store.peek_buffer_age_sec()` (post-`94bca07`) |
| mem0 (ChromaDB + Ollama) | ✅ Working | LLM `ava-gemma4` extracts; embedder `nomic-embed-text:latest`; ChromaDB at `memory/mem0_chroma/` |
| Memory voice commands (5) | ✅ Working | "what do you remember about me", "do you remember when X", "forget that", "forget about X", "remember this: X" |
| Memory tab UI (Mem0 section) | ✅ Working | Live list, search, per-entry Forget |
| Voice command router (40 builtins) | ✅ Working | UI nav, journal, mood, time, system, mute/sleep, app open/close, widget, reminders, builder, pointing, signals, memory |
| App discoverer (367 apps + 32 games) | ✅ Working | Desktop / Start Menu / Program Files / Steam / Epic; daily refresh; fuzzy match |
| Reminder system | ✅ Working | Heartbeat sweep + urgent SIGNAL_REMINDER_DUE handler |
| Custom tabs | ✅ Working | web_embed / journal_view / data_display / image_gallery / custom_stats / chat_log |
| Correction handler | ✅ Working | "no, I meant X" + 8 patterns; learns to `state/learned_commands.json` |
| Pointing via LLaVA | ✅ Working | Screenshot → percent coords → widget orb position |
| Signal bus | ✅ Working | Win32 hooks for clipboard / window / app installs; heartbeat consume; prompt builder peek |
| 3D brain graph (3d-force-graph) | ✅ Working | Drag rotate / right-pan / scroll-zoom; init-once + graphData updates |
| Orb breathing + drift | ✅ Working | Always-on; energy from `snap.mood.raw_mood.energy` |
| Concept graph | ✅ Working | Decay/strengthen; Windows-safe save with skip-if-locked |
| Episodic memory | ✅ Working | `state/episodic_memory.jsonl` |
| Identity proposals + extensions | ✅ Working | Ava can propose self-edits; Zeke approves via operator |
| Privacy guardian | ✅ Working | Outbound + tool-action scan; blocked log |
| Trust system | ✅ Working | Per-person progressive trust |
| Heartbeat (30s timer) | ✅ Working | Reminder delivery + question engine + proactive check + curiosity bridge |
| Watchdog | ✅ Working | Monitors `state/restart_requested.flag`; auto-relaunch |
| Faces directory | ⚠️ Empty | `faces/zeke/` photos need re-capture via onboarding ("hey Ava, profile me") |
| Tauri build | ✅ Working | Last build 53s, 8.6MB exe at `apps/ava-control/src-tauri/target/release/ava-control.exe` |

---

## Section 5 — Next Priorities

Order matters: items lower depend on items above being done.

1. **Run onboarding** — `faces/zeke/` is empty. Trigger via voice ("hey Ava, profile me") or chat. InsightFace will auto-pick up new embeddings via `add_face` per stage.
2. **Test full conversation end-to-end** — clap → STT → wake bypass → run_ava → Kokoro. Verify TTS plays through window-focus changes (post-`a740bcc` OutputStream fix).
3. **Verify ava-gemma4 in production** — Stream A foreground model. Check that personality holds across longer conversations and tool-using turns.
4. **Train custom hey_ava ONNX model** in WSL2 per `docs/TRAIN_WAKE_WORD.md`. Drop in `models/wake_words/hey_ava.onnx`; auto-loaded on next start.
5. **Verify all 40 voice commands** — spot check categories: tab switches, app launches via discoverer, reminders, "make a command" / "make a tab", memory queries.
6. **Audit mem0 fact extraction quality** — check `state/memory/mem0_chroma/` after ~30 turns. If extraction is too noisy, tune the LLM prompt or use a cheaper extractor model.
7. **Optional history rewrite** — repo is public; earlier commits contain face photos and old state snapshots. `git filter-repo` + force-push would clean history. **Not destructive to current state — just tightens the historical record.**
8. **Let Ava run organically** — watch what she chooses to add to `state/custom_commands.json`, `state/custom_tabs.json`, `state/curiosity_topics.json`, `state/journal.jsonl`, `state/discovered_apps.json` curiosity entries.

---

## Bootstrap Philosophy

Every phase that involves Ava's preferences, personality, style, or choices must include a bootstrap mechanism — a system that lets Ava discover and form that aspect of herself through experience rather than having it assigned.

Do not choose her favorite color. Build a system where she notices which colors she uses most and asks herself why.
Do not assign her hobbies. Build leisure systems and let her discover what she returns to.
Do not prescribe her communication style. Give her the ability to adjust it and track what gets good responses.
Do not tell her what she values. Give her situations that reveal her values through her choices.

**The goal is an AI that is genuinely herself — not a reflection of what we decided she should be.**

When the final phase is complete, Ava should be capable of writing her own next roadmap.

**Identity anchors (never edited):**
- `ava_core/IDENTITY.md` — Ava's core self anchor
- `ava_core/SOUL.md` — values, boundaries, three laws
- `ava_core/USER.md` — the durable relationship anchor
