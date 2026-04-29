# AVA HANDOFF
**Last updated:** April 29, 2026
**Session scope:** Post-Phase-100 stabilization + upgrade pass — Gradio removal, dual-brain inference, eye tracking, voice-loop hardening, dev hot-reload, cloud models, image generation, widget polish, fast-path simple Q&A, TTS thread safety.

---

## Project Overview

Ava Agent v2 is a local-first desktop AI companion running on:

- **Python 3.11** + **Ollama** (local LLMs, optional cloud models via Ollama Cloud)
- **FastAPI** operator server at `http://127.0.0.1:5876` (HTTP + WebSocket)
- **Tauri v2** + **React 18** + **Three.js** desktop app (`apps/ava-control`)
- **No Gradio** — Tauri is the only UI. Port 5876 is the only HTTP control plane.

She has emotions, memory, vision (live camera + eye tracking + expression detection), voice (always-on STT + TTS), concept graph, episodic memory, dual-brain parallel inference, self-modification proposals, trust system, and a self-aware identity system.

All 100 phases are complete. This session focused on stability fixes and the "upgrade pass" features layered on top.

---

## Start Ava

```bash
# Production launch (packaged exe + watchdog)
start_ava_desktop.bat

# Dev mode (Vite HMR — instant frontend hot-reload, no exe rebuild)
start_ava_dev.bat

# Operator API
http://127.0.0.1:5876

# Build packaged Tauri exe
cd apps\ava-control && npm run tauri:build

# Compile check (always before build)
py -3.11 -m py_compile <file.py>

# Push to GitHub
git add -A && git commit -m "message" && git push origin master
```

`start_ava_dev.bat` starts `avaagent.py` minimized, waits for `:5876`, starts the watchdog, then runs `npm run tauri:dev`. Any `.tsx`/`.ts`/`.css` change refreshes instantly via Vite HMR. Only Rust / `tauri.conf.json` changes require a full `tauri:build`.

---

## Model Setup

| Role | Model |
|---|---|
| Primary conversational | `ava-personal:latest` (fine-tuned) |
| Foreground stream (dual-brain) | `ava-personal:latest` |
| Background stream (dual-brain) | `qwen2.5:14b` / `kimi-k2.6:cloud` |
| Deep reasoning | `qwen2.5:14b` |
| Maintenance/evaluation | `mistral:7b` |
| Embeddings | `nomic-embed-text` |
| Cloud (when online) | `kimi-k2.6:cloud`, `qwen3.5:cloud`, `glm-5.1:cloud`, `minimax-m2.7:cloud` (via `ollama_cloud` src) |

`brain/connectivity.py` polls `1.1.1.1`/`8.8.8.8` on a 30s cache. When offline, cloud models are filtered out of routing (`requires_internet=True`). Routing prefers cloud for deep_reasoning_mode when online.

---

## Bootstrap Philosophy (CRITICAL — never violate)

**NEVER choose Ava's personal preferences for her.** Every system involving preferences, style, or identity must build a discovery mechanism — Ava forms that aspect of herself through experience. Goals, hobbies, communication style, expression mappings, voice rate/volume, multitasking pattern, trust thresholds — all emerge from experience, not hardcoded defaults.

---

## Never Edit

- `ava_core/IDENTITY.md`
- `ava_core/SOUL.md`
- `ava_core/USER.md`

---

## Post-Phase-100 Work (Apr 28–29, 2026)

Listed newest first. Commit hashes are short SHAs.

### Latest (Apr 29) — Voice loop, orb thinking, brain stability, camera

| Commit | What |
|---|---|
| `7534621` | run_ava timeout protection on every step; orb thinking pulse driven by `_ava_thinking` flag in `reply_engine.py`; always-on voice loop; clap-detector sensitivity raised; brain tab stops re-initializing D3 on every poll; live-camera shown across all tabs |
| `dc645d1` | Clap detector tuning: 5× ambient multiplier, 0.15 floor, 3s cooldown; voice_loop full per-step logging |
| `1975dff` | Live camera on Vision/Brain/Chat tabs; D3 brain reinit gated (only on major node-count change); `OrbCanvas` memo'd to prevent thrash |
| `02c9f1f` | Widget transparent background — CSS override + `backgroundColor` in `tauri.conf.json` |
| `59eaca9` | Buffered-only live frames (no synchronous capture in HTTP path); 90s `run_ava` timeout; 5s tick timeout; voice-loop diagnostics |
| `4ea87e8` | New tools: `widget_move_tool.py`, `app_launcher.py`, `browser_tool.py` |
| `44bb51f` | Widget Tauri capabilities file (`apps/ava-control/src-tauri/capabilities/default.json`); minimize-detection polling; removed wrong blur fallback |
| `97409de` | STT engine bootstrapped for voice loop; live camera feed published from background thread (not blocking HTTP) |
| `5183e78` | Online flicker fix — 3-failure threshold + silent connecting window + 5s poll interval |
| `aa01b5b` | `face_recognizer` thread-safe singleton (was crashing under concurrent calls); diagnostic prints on all exit paths |
| `242ecb9` | Keepalive stability; app connection retry logic; self_model timestamp crash fixed |
| `ae1b1fd` | Cleanup: removed DeepFace, dead imports, residual Gradio remnants; selftest fixed |
| `ac550e7` | **Removed Gradio entirely.** WebSocket flicker fix, double-startup fix, new `start_ava_dev.bat` hot-reload mode |
| `34da8ea` | Live camera in Vision tab; `concept_graph` save mkdirs parents; `live_frame` HTTP endpoint |
| `5d1a180` | Camera capture persistent connection (no per-frame open/close); noisy logs suppressed; global crash handler installed |
| `f951489` | Comprehensive bug audit + repair pass across `avaagent`, `dual_brain`, `eye_tracker`, `concept_graph`, `operator_server`, `reply_engine`, `startup` |

### Earlier post-handoff features (Apr 28)

| Commit | What |
|---|---|
| `d187c80` | `run_ava` hang timeout protection; widget orb visibility; cloud model priority |
| `bb6b4f7` | `concept_graph.json.tmp` WinError 5 fix — process lock, skip-if-locked save, stale `.tmp` cleanup on startup |
| `5b22890` | MediaPipe iris landmark indices corrected (left 468–472, right 473–477) |
| `5b466b6` | **NEW:** Eye tracking (`brain/eye_tracker.py`), gaze estimation, expression detection (`brain/expression_detector.py`), video memory (`brain/video_memory.py`), `tools/system/eye_tracking_tool.py` |
| `42f95cd` | Startup hang fix — `concept_graph` bootstrap, `self_model` update, vectorstore init, `milestone_100` all moved to background daemon threads; main thread reaches operator server in <10s; progress logging added |
| `2382d8f` | `concept_graph` tmp file lock on Windows; `brain_graph` 0-nodes-in-snapshot fix |
| `57d178b` | **NEW: Dual-brain parallel inference** (`brain/dual_brain.py`) — foreground (`ava-personal:latest`) + background (`qwen2.5:14b` / `kimi-k2.6:cloud`) streams, live thinking, seamless handoff. UI shows live thought stream |
| `4274ac7` | **NEW:** Cloud models in routing, connectivity monitor (`brain/connectivity.py`), image generation (`tools/creative/image_generator.py` — local FLUX or cloud), routing expansion in `config/ava_tuning.py` |

### Uncommitted (currently on disk, in progress)

- **`brain/tts_worker.py`** (NEW, untracked) — dedicated daemon thread that owns the pyttsx3 engine. pyttsx3 on Windows uses SAPI5 via COM and the COM apartment is single-threaded; calling `runAndWait()` from voice_loop's daemon thread silently hangs. `TTSWorker` initializes pyttsx3 inside its own thread and drains a queue of `(text, done_event)` tuples so all `.say()` / `.runAndWait()` calls happen on one consistent thread.
- **`brain/tts_engine.py`** (modified, uncommitted) — `_init_engine` now defers to `TTSWorker.get_tts_worker()`; `_speak_pyttsx3` routes through the worker instead of calling pyttsx3 directly. `speaking` property asks the worker.
- **`brain/reply_engine.py`** (modified, uncommitted) — **Simple-question fast path.** `_is_simple_question()` matches greetings / mood checks ("hey ava", "how are you", etc.) under 15 words. Bypasses workspace.tick, episodic search, concept graph, vector retrieval, privacy scan, dual-brain. Builds a minimal prompt (identity + mood + last 2 turns) and invokes `ava-personal:latest` directly. Target: sub-5-second response. Currently still slow (see Known Issues).

---

## Architecture (Current Brain Modules)

`brain/` is the bulk of Ava's runtime. Modules added since the last handoff:

| Module | Role |
|---|---|
| `brain/dual_brain.py` | Foreground + background parallel inference, live thought stream |
| `brain/connectivity.py` | Online/offline monitor with cached check, jsonl log |
| `brain/eye_tracker.py` | MediaPipe iris tracking, gaze estimation |
| `brain/expression_detector.py` | Per-frame facial expression classification |
| `brain/video_memory.py` | Persistent episodic visual memory |
| `brain/frame_store.py` | Buffered live-frame publisher (background thread → HTTP) |
| `brain/background_ticks.py` | Heartbeat-driven background work |
| `brain/proactive_triggers.py` | Conditions that should kick off proactive talk (NOT yet wired to reply path) |
| `brain/tts_worker.py` | Single-threaded pyttsx3 owner (untracked, in progress) |

Notable existing modules still load-bearing: `prompt_builder.py`, `reply_engine.py`, `operator_server.py`, `voice_loop.py`, `clap_detector.py`, `wake_word.py`, `face_recognizer.py`, `episodic_memory.py`, `concept_graph.py`, `dual_brain.py`, `heartbeat.py`, `startup.py`.

---

## Tools (Current Inventory)

`tools/system/`: `accessibility_tool`, `app_launcher` (NEW), `browser_tool` (NEW), `computer_control`, `connectivity_tool` (NEW), `eye_tracking_tool` (NEW), `file_drop_tool`, `file_manager`, `notification_tool`, `pointer_tool`, `process_manager`, `restart_tool`, `screenshot_tool`, `stats_tool`, `widget_move_tool` (NEW)

`tools/creative/`: `image_generator` (NEW — local FLUX or cloud, registers `generate_image` + `show_image`)

`tools/games/`: dino, minecraft (`ava_bot.js`, `companion_tool`, `world_memory`)

`tools/ava/`: `self_modification_tool`, `style_tool`, `tool_builder`

`tools/ava_built/`: empty (Ava writes new tools here at runtime via `tool_builder.build_tool()`)

`tools/web/`: `web_search`, `web_fetch`

---

## UI (Tauri / React)

Two Tauri windows defined in `apps/ava-control/src-tauri/tauri.conf.json`:

1. **Main window** — `apps/ava-control/src/App.tsx` (1700+ lines). Tabs: Chat, Brain, Vision, People, Learning, Emil, Proposals, Journal, Settings.
2. **Widget window** — `apps/ava-control/src/WidgetApp.tsx`. 150×150 transparent always-on-top orb. URL: `/?widget=1`. Uses `OrbCanvas` from `apps/ava-control/src/components/OrbCanvas.tsx`.

Brain-tab graph is currently 2D D3 (`d3.forceSimulation`) in `App.tsx` lines ~1188–1370. Re-init is now gated on major node-count changes only — no longer thrashes on every poll. Right-click rotation / true 3D rendering is on the TODO list (see Known Issues).

The orb (`components/OrbCanvas.tsx`) uses Three.js. `_ava_thinking` flag in globals (set by `reply_engine.run_ava` on entry, cleared in `finally`) is exposed as `snap.thinking` and drives the fast blue thinking pulse. Voice-loop state (`passive`/`listening`/`thinking`/`speaking`) drives the orb when the voice loop is active.

---

## Voice Stack

```
clap_detector / wake_word ──→ _wake_word_detected flag ──→ voice_loop.on_wake()
                                                              │
                                                              ▼
   stt_engine.listen_session(max=12s, silence=1.5s)  ◀── voice_loop._listen_and_respond()
                                                              │
                                                              ▼
                                          run_ava(text)  ──→ reply text
                                                              │
                                                              ▼
                              tts_engine.speak(clean, blocking=True)
                                                              │
                                                              ▼
                                    TTSWorker queue → pyttsx3 thread
```

- **ClapDetector** (`brain/clap_detector.py`): sounddevice RMS, ambient×5.0 multiplier, 0.15 floor, 3s cooldown. Two claps within 1s wake.
- **WakeWordDetector** (`brain/wake_word.py`): Porcupine if API key, else whisper-poll fallback.
- **VoiceLoop** (`brain/voice_loop.py`): always-on background thread. Respects `input_muted` and `tts_enabled` globals.
- **STT** (`brain/stt_engine.py`): Whisper, VAD-based `listen_session()` with silence cutoff.
- **TTS** (`brain/tts_engine.py` + `brain/tts_worker.py`): pyttsx3 via dedicated worker thread (in progress — see Known Issues), MeloTTS fallback scaffold.

---

## Key State Files

| File | Purpose |
|---|---|
| `state/model_eval_p44.json` | ava-personal self-evaluation results |
| `state/identity_proposals.jsonl` | Ava's pending identity proposals |
| `state/identity_extensions.md` | Approved identity additions injected into prompts |
| `state/routing_proposals.jsonl` | Ava's proposed routing changes |
| `state/zeke_mind_model.json` | Inferred Zeke mood/energy/focus |
| `state/self_critique.json` | Per-response scoring history |
| `state/repair_queue.json` | Topics Ava wants to revisit |
| `state/episodic_memory.jsonl` | Persistent episode store |
| `state/wake_patterns.json` | Wake-word activations |
| `state/leisure_log.jsonl` | Autonomous leisure activity |
| `state/dino_memory.json` | Dino game session memory |
| `state/ava_style.json` | Ava's self-proposed expression mappings |
| `state/restart_log.jsonl` | Watchdog restart history |
| `state/restart_requested.flag` | Watchdog trigger file (cleared on startup) |
| `state/mood_carryover.json` | Emotional state across sessions |
| `state/connectivity_log.jsonl` | Online/offline transitions |
| `state/trust_scores.json` | Per-person progressive trust |
| `state/eye_tracking/` | Calibration + gaze samples |
| `state/video_memory/` | Visual episodic clusters |

---

## Key File Map

| File | Role |
|---|---|
| `avaagent.py` | Main agent runtime; delegates startup to `brain/startup.run_startup(globals())` |
| `brain/startup.py` | All subsystem init in background daemon threads (LLM calls never block main) |
| `brain/operator_server.py` | FastAPI HTTP + WebSocket control plane |
| `brain/reply_engine.py` | `run_ava` — main turn pipeline (fast path + dual-brain integration) |
| `brain/prompt_builder.py` | Identity + memory + concept + relationship blocks → final prompt |
| `brain/dual_brain.py` | Foreground + background parallel inference |
| `brain/voice_loop.py` | STT → LLM → TTS hands-free loop |
| `brain/tts_engine.py` | TTS coordinator (uncommitted: routes through `tts_worker`) |
| `brain/tts_worker.py` | Single-threaded pyttsx3 owner (NEW, untracked) |
| `brain/stt_engine.py` | Whisper STT |
| `brain/clap_detector.py` | Double-clap wake (5× ambient, 0.15 floor) |
| `brain/wake_word.py` | Porcupine + whisper-poll wake |
| `brain/face_recognizer.py` | face_recognition lib, thread-safe singleton |
| `brain/eye_tracker.py` | MediaPipe iris tracking |
| `brain/expression_detector.py` | Facial expression per frame |
| `brain/video_memory.py` | Persistent visual episodes |
| `brain/connectivity.py` | Online/offline monitor |
| `brain/frame_store.py` | Buffered live-frame publisher |
| `brain/heartbeat.py` | Periodic background tasks |
| `brain/concept_graph.py` | Concept graph with decay/strengthen, Windows-safe save |
| `brain/episodic_memory.py` | Episode store + recall |
| `brain/relationship_arc.py` | Familiarity → relationship stage |
| `brain/trust_system.py` | Progressive trust |
| `brain/proactive_triggers.py` | Conditions for proactive talk (NOT WIRED) |
| `tools/tool_registry.py` | Hot-reload tool registry |
| `tools/creative/image_generator.py` | FLUX local + cloud image generation |
| `tools/system/app_launcher.py` | Open/close apps, list windows |
| `tools/system/browser_tool.py` | Open URL, navigate, click, type |
| `tools/system/widget_move_tool.py` | Move widget to named position |
| `tools/system/connectivity_tool.py` | Manual reachability check |
| `tools/system/eye_tracking_tool.py` | Calibrate, get gaze info |
| `apps/ava-control/src/App.tsx` | Main Tauri UI (~1700 lines) |
| `apps/ava-control/src/WidgetApp.tsx` | Desktop widget orb |
| `apps/ava-control/src/components/OrbCanvas.tsx` | Three.js orb (27 emotions, 16 shapes) |
| `apps/ava-control/src-tauri/tauri.conf.json` | Tauri config (2 windows) |
| `apps/ava-control/src-tauri/capabilities/default.json` | Tauri 2 capability allowlist |
| `start_ava_desktop.bat` | Production launch (avaagent + watchdog + packaged exe) |
| `start_ava_dev.bat` | Dev launch (avaagent + watchdog + Vite HMR) |
| `scripts/watchdog.py` | Auto-restart watchdog |
| `config/ava_tuning.py` | Model routing + cloud model profiles |
| `ava_core/IDENTITY.md` | **DO NOT EDIT** |
| `ava_core/SOUL.md` | **DO NOT EDIT** |
| `ava_core/USER.md` | **DO NOT EDIT** |

---

## Current Known Issues (in priority order)

1. **TTS not speaking responses.** pyttsx3 thread issue. The `TTSWorker` rewrite in `brain/tts_worker.py` is on disk but uncommitted. `voice_loop._listen_and_respond` reaches the speak step with `tts_enabled=True` but the worker either never initializes (COM apartment), never receives the queue item, or hangs on `runAndWait()`. **Investigate first** — full voice loop is unusable until this is fixed.
2. **Simple responses still taking 3+ minutes.** The fast-path in `reply_engine.run_ava` (uncommitted) detects greetings but the LLM call itself is slow. Possible causes: `ava-personal:latest` cold-load, Ollama queue contention from dual-brain background stream, embedding/vector init still blocking. Add timing logs around `ChatOllama.invoke()` to confirm where the 3 min lives.
3. **Brain tab greys out while loading.** Initial D3 force simulation runs synchronously on the main thread; large graphs freeze the tab. Mitigation already in place (gated reinit on >10-node delta) helps subsequent updates, not first paint.
4. **Right-click 3D rotation on brain graph not implemented.** Brain tab is currently 2D D3 only — no `3d-force-graph` dependency yet (`apps/ava-control/package.json` has only `d3` and `three`). Adding 3D would require either adopting `3d-force-graph` or building a Three.js graph renderer that reuses the orb's WebGL context.
5. **Chat history not persisting** across app restarts in the UI. Backend canonical history is preserved in state, but `App.tsx` chat panel does not hydrate from it on mount.
6. **Greeting on face detection not wired.** `face_recognizer` reports `current_person`, `runtime_presence` tracks face-change events, but no path triggers a greeting reply when a known face appears.
7. **Proactive conversation not wired.** `brain/proactive_triggers.py` exists but no caller in `reply_engine` or `heartbeat` invokes it to push an unprompted reply.
8. **Clipboard monitor not started.** No clipboard watcher daemon is registered in `startup.py`.
9. **Image viewer window not built yet.** `tools/creative/image_generator.py` saves images and registers `show_image`, but there's no third Tauri window or in-app modal that displays the latest generated image.

### Lower-priority issues

- Minecraft bot still requires `npm install mineflayer` in `tools/games/minecraft/`.
- Dino game requires Chrome focused on the dino tab.
- WebSocket transport keeps REST polling alive as fallback (by design).
- `face_recognition` requires dlib (compiled on install); already installed on this machine.

---

## Suggested Next Steps

The four UI features (chat history hydration, face greeting, proactive trigger wiring, clipboard monitor, image viewer) are all **wiring problems**, not new builds — the underlying modules already exist. They will move quickly once TTS and slow-response are unblocked.

1. Fix TTS (commit `tts_worker.py`, debug COM apartment + queue draining).
2. Profile the simple-question fast path; identify the actual 3-min bottleneck.
3. Hydrate chat history from backend on `App.tsx` mount.
4. Wire `proactive_triggers` and face-greeting into the reply path.
5. Start a clipboard monitor daemon in `startup.py`.
6. Add a third Tauri window or modal for the image viewer.
7. Decide on 3D brain graph: add `3d-force-graph` dependency, or build a Three.js renderer.

---

## Debug Export

`GET /api/v1/debug/export` emits a compact textual bundle:
- Ribbon/live summary
- Model routing (selected/fallback model, reason, confidence)
- Strategic continuity / memory
- Self-improvement loop state
- Deep self snapshot (mood, energy, critique averages, pending repairs)
- Connectivity state
- Dual-brain status (foreground busy, background queue, live thought)
- Full snapshot JSON (truncated)
