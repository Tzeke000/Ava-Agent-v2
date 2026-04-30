# AVA HANDOFF
**Last updated:** 2026-04-29 (post mem0 + ava-gemma4 + repo hygiene pass)
**Latest commit:** `117428f` — `chore: gitignore biometric + per-machine state; untrack runtime files`
**Total commits on master:** 184
**Roadmap with full phase history:** `docs/AVA_ROADMAP.md`

---

## Project Overview

Ava Agent v2 is a local-first desktop AI companion running on:

- **Python 3.11** + **Ollama** (local LLMs, optional cloud via Ollama Cloud)
- **FastAPI** operator server at `http://127.0.0.1:5876` (HTTP + WebSocket)
- **Tauri v2** + **React 18** + **Three.js** desktop app (`apps/ava-control`)
- **No Gradio** — Tauri is the only UI; port 5876 is the only HTTP control plane.

She has emotions, memory (concept graph + episodic + mem0), vision (InsightFace GPU + per-person expression calibration + eye tracking), voice (clap detector + openWakeWord + Silero VAD + Whisper base + Eva→Ava normalization + Kokoro neural TTS + 60s attentive state), dual-brain parallel inference (Stream A `ava-gemma4` foreground + Stream B `gemma4`/cloud background, serialised by Ollama lock), an event-driven signal bus replacing all polling loops, a 40-builtin voice command router with custom-command builder, app/game discovery, reminders, correction handling, pointing, and a self-aware identity system.

**All 100 phases complete.** Post-100 work has layered:
- Cloud models + connectivity monitor (`4274ac7`)
- Dual-brain parallel inference (`57d178b`)
- Eye tracking + expression detection (`5b466b6`)
- Gradio removal (`ac550e7`)
- TTS COM-thread isolation + Ollama lock + fast path (`fa583ea`)
- Kokoro neural TTS (`346d30c`)
- InsightFace GPU + 3D brain graph (`357dd69`, `9d07838`)
- Voice-first UI + 40 voice commands (`8affd49`)
- Signal bus + Win32 zero-poll watchers (`755f539`)
- Voice critical fixes (clap=direct, OutputStream playback) (`a740bcc`)
- openWakeWord + Silero VAD (`4477aa2`)
- ava-gemma4 identity-baked model + mem0 memory (`5c2322c`)
- Repository hygiene — gitignore + 149-file untrack (`117428f`)

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
git add -A && git commit -m "..." && git push origin master
```

**First-run notes:**
- InsightFace `buffalo_l` weights (~280MB) download on first init.
- ORT cudnn EXHAUSTIVE algorithm search runs ~60–90s on first init, then caches to disk.
- Kokoro `hexgrad/Kokoro-82M` weights and spaCy `en_core_web_sm` download on first TTS use.
- openWakeWord pre-trained `hey_jarvis_v0.1.onnx` is bundled with the package.
- Silero VAD model downloads on first STT init.
- All five are background-thread loads — main startup reaches operator HTTP in <10s.

---

## Voice Pipeline (full flow)

```
┌──────────────┐                        ┌──────────────┐
│   PASSIVE    │  (always listening)    │              │
│ openWakeWord │ ──────────────────────►│   LISTEN     │
│  + ClapDet   │                        │ Silero VAD   │
└──────────────┘                        │  + Whisper   │
       │                                └──────┬───────┘
       │ wake_source = "openwakeword"          │ transcribed
       │             or "clap"                 │ + Eva→Ava normalized
       │                                       ▼
       │                                ┌──────────────┐
       │                                │  WAKE GATE   │
       │                                │ classify or  │
       │                                │ short-circuit│
       │                                └──────┬───────┘
       │ direct address                        │
       ▼                                       ▼
                              ┌──────────────────────────┐
                              │  Voice Command Router    │
                              │ 40 builtins + custom     │
                              └──────┬───────────────────┘
                                     │ no match
                                     ▼
                              ┌──────────────────────────┐
                              │       run_ava()          │
                              │ fast-path or deep-path   │
                              └──────┬───────────────────┘
                                     │ reply text
                                     ▼
                              ┌──────────────────────────┐
                              │   Kokoro TTS Worker      │
                              │ OutputStream protected   │
                              │ amplitude → orb pulse    │
                              └──────┬───────────────────┘
                                     │ playback complete
                                     ▼
                              ┌──────────────────────────┐
                              │      ATTENTIVE 60s       │
                              │ any speech > 0.8s        │
                              │ → run_ava (no wake)      │
                              └──────────────────────────┘
```

**Wake word stack:**
- `brain/wake_word.py` runs openWakeWord (ONNX, < 1% CPU). Currently uses `hey_jarvis` as a proxy until a custom `models/wake_words/hey_ava.onnx` is trained — see `docs/TRAIN_WAKE_WORD.md`. Verified by benchmark: `hey_jarvis` peaks 0.917 on Kokoro-synthesized "hey ava (af_bella)"; `hey_mycroft` and `hey_rhasspy` never cross 0.02 on the same samples.
- `brain/clap_detector.py` runs alongside as the always-reliable wake. Floor 0.35 (keyboard/mouse never cross), double-clap window 0.6s, min separation 0.1s, 4s cooldown.
- Either wake source stamps `g["_wake_source"]` so `wake_detector.classify` short-circuits to direct address (no clarification) and `voice_loop` skips classification entirely.

**STT:**
- `WhisperModel("base")` on `cuda+float16` (or CPU int8 fallback)
- `beam_size=5`, `language="en"`, `initial_prompt="Ava, hey Ava,"` (biases the model to keep "Ava" in transcripts), `vad_filter=True`
- Tries `hotwords="Ava"` first; falls back gracefully if the installed faster-whisper version doesn't accept the kwarg
- **Silero VAD** (`silero_vad.load_silero_vad()`) replaces RMS-energy speech detection — RTF ≈ 0.004, robust to keyboard/mouse/HVAC noise
- Transcripts pass through `_normalize_transcript` to fix Whisper mishearings: `Eva → Ava`, `Aye va → Ava`, `A va → Ava`, `Hey Ada → Hey Ava` (with all punctuation variants)

**TTS:**
- `brain/tts_worker.py` runs Kokoro on a dedicated thread with `THREAD_PRIORITY_HIGHEST`
- 28 voices. Default `af_heart` (warm). Per-emotion mapping picks `af_bella` (high-intensity expressive), `af_nicole` (soft/sad), `af_sky` (bright). Speed 0.7–1.3 scaled toward neutral by intensity.
- Falls back to pyttsx3 + Zira (COM-isolated thread) if Kokoro can't init.
- Playback uses `sd.OutputStream` chunked at 2048 samples — cannot be interrupted by window focus changes, mouse clicks, or other apps grabbing audio. The ONLY mid-stream aborts are explicit `g["_tts_muted"]=True` or worker shutdown.
- Live amplitude: per-chunk RMS published to `g["_tts_amplitude"]` and module-level state for orb animation.

**Voice loop (state machine):**
- `passive` — openWakeWord + clap detector listening
- `attentive` — 60s post-speak window; mic polls every 0.8s; speech > 1s → run_ava without wake
- `listening` — recording the user's utterance with Silero VAD silence detection
- `thinking` — `run_ava()` is producing a reply
- `speaking` — TTS is playing

---

## Vision Stack

### Face recognition — InsightFace (GPU)
- `brain/insight_face_engine.py` loads buffalo_l: RetinaFace + ArcFace + 106-pt landmarks + age/gender + 3D head pose
- Runs on **CUDAExecutionProvider** via pip-installed CUDA libs (`cublas`, `cudnn`, `cufft`, `curand`, `cusolver`, `cusparse`, `cuda_runtime`, `cuda_nvrtc`, `nvjitlink`). `_add_cuda_paths()` registers each `site-packages/nvidia/*/bin/` with `os.add_dll_directory` BEFORE the ORT import.
- Inference ~41ms/frame at runtime on RTX 5060.
- `background_ticks._video_frame_capture_thread` runs InsightFace every 3rd frame (~5fps), pushes annotated frame to `frame_store`, fires `SIGNAL_FACE_APPEARED` / `SIGNAL_FACE_LOST` / `SIGNAL_FACE_CHANGED` / `SIGNAL_EXPRESSION_CHANGED`.

### Camera annotator — `brain/camera_annotator.py`
- Bounding box (green known / yellow unknown), 106 landmarks (key points larger), head pose arrows from nose tip (green up / red right / blue forward), age + gender label, attention state at bottom-left.

### Per-person expression calibration — `brain/expression_calibrator.py`
- EMA baseline of `eyebrow_ratio` and `mouth_corner_offset` per person, α=0.001
- 300 samples → calibrated. Persists to `state/expression_baseline_{pid}.json`
- Detects `surprised` / `frowning` / `smiling` / `neutral` as deviations from THAT person's baseline. Solves the "naturally elevated eyebrows are read as surprised" problem.

### Eye tracking — MediaPipe
- `brain/eye_tracker.py` for iris / gaze. Requires `protobuf 3.20.x` (pinned — InsightFace and others want newer; this is the constraint that broke during training-deps install attempt and was rolled back).

---

## Bootstrap Philosophy (CRITICAL — never violate)

**NEVER choose Ava's personal preferences for her.** Every system involving preferences, style, or identity must build a discovery mechanism — Ava forms that aspect of herself through experience. Goals, hobbies, communication style, expression mappings, voice rate/volume, multitasking pattern, trust thresholds, per-person expression baselines, learned wake patterns, custom commands, custom tabs, discovered apps — all emerge from experience.

---

## Never Edit
- `ava_core/IDENTITY.md`
- `ava_core/SOUL.md`
- `ava_core/USER.md`

---

## How to Run Onboarding

Onboarding is the only way Ava learns to recognize a new person. Trigger it by saying or typing:

> "hey Ava, profile me"
> "Ava, profile me"

13 stages: `greeting → photo_front → photo_left → photo_right → photo_up → photo_down → confirm_photos → name_capture → pronouns → favorite_color → relationship → one_thing → complete`.

Each captured frame is pushed into `engine.add_face(person_id, frame)` immediately, so recognition starts working within seconds — no restart needed. After the final stage, `engine.update_known_faces(faces/)` does a full reload to pick up anything missed. The legacy face_recognition lib is also refreshed for fallback purposes.

---

## Wiring Verification (audit-confirmed)

| System | Status | Where |
|---|---|---|
| Signal bus | wired | `startup.py` (early bootstrap), heartbeat consume, prompt_builder peek |
| openWakeWord | wired | `startup.py` calls `WakeWordDetector.start()` |
| Silero VAD | wired | `STTEngine._init_vad`, used by `_has_speech` |
| Kokoro TTS | wired | `tts_worker` singleton, OutputStream protected playback |
| InsightFace per-frame | wired | `background_ticks._video_frame_capture_thread` every 3rd frame |
| Camera annotator | wired | annotates `_face_results` cache, pushes to `frame_store` |
| Expression calibrator | wired | per-frame `cal.calibrate_baseline + detect_expression` |
| Onboarding → InsightFace | wired | `add_face` per-stage + `update_known_faces` on completion |
| Voice loop attentive | wired | post-speak, 60s window, faster mic poll |
| Wake detector clap+oww shortcut | wired | classify short-circuits both sources to (True, 1.0) |
| Wake learner | wired | borderline conf → ask + listen 8s for yes/no |
| Voice mood (reuses STT audio) | wired | `_analyze_voice_mood_from_result(stt_result)` |
| Voice mood prompt injection | wired | both fast and deep paths in `prompt_builder.py` |
| Question engine | wired | heartbeat tick — speaks via tts_worker, mark_asked |
| Proactive triggers | wired | heartbeat + face-detection greeting |
| Ollama lock | wired | reply_engine fast + main, dual_brain live_thought + critique + creative |
| Stream B pause on turn | wired | `pause_background_now(30)` at run_ava entry |
| Chat history persistence | wired | `state/chat_history.jsonl` append in turn_handler |
| Voice command router | wired | top of run_ava — 40 built-ins + custom |
| App discoverer | wired | `startup.py` background thread, daily incremental rescan |
| Reminder system | wired | heartbeat sweep + urgent SIGNAL_REMINDER_DUE handler |
| 3D brain graph | wired | `3d-force-graph 1.80` in App.tsx, init-once + graphData updates |
| Orb breathing + drift | wired | rootGroup scale + position every frame in animate() |
| Custom tabs | wired | `/api/v1/ui/custom_tabs` + CustomTabRenderer |
| Tab routing | wired | `/api/v1/ui/tab` polled every 1s |
| Win32 clipboard hook | wired | AddClipboardFormatListener → SIGNAL_CLIPBOARD_CHANGED |
| Win32 window hook | wired | SetWinEventHook(EVENT_SYSTEM_FOREGROUND) → SIGNAL_ACTIVE_WINDOW_CHANGED |
| Win32 app install hook | wired | ReadDirectoryChangesW → SIGNAL_NEW_APP_INSTALLED |
| ava-gemma4 (Stream A primary) | wired | `dual_brain._resolve_foreground_model()` picks `ava-gemma4` if installed; `_pick_fast_model_fallback` prefers it for fast path |
| Stream B `gemma4:latest` | wired | `dual_brain.get_thinking_model()` — kimi cloud when online, gemma4 local, qwen2.5:14b fallback |
| mem0 memory (ChromaDB + Ollama) | wired | `bootstrap_ava_memory` in startup; `turn_handler` adds turns; `prompt_builder` injects MEMORIES |
| Memory voice commands (5) | wired | "what do you remember about me", "do you remember when X", "forget that", "forget about X", "remember this: X" |
| Memory tab UI | wired | `/api/v1/memory/mem0` GET/DELETE/search; live list + per-entry Forget |

---

## Operator Snapshot Schema (vision block)

```json
{
  "vision": {
    "perception": { ... },
    "llava_scene_description": "...",
    "recognized_person_id": "zeke",
    "recognized_confidence": 0.93,
    "expression": "smiling",
    "face_age": 28,
    "face_gender": "M",
    "attention_state": "focused",
    "gaze_region": "center",
    "gaze_calibrated": true,
    "expression_calibrated": true,
    "expression_calibration_samples": 412
  }
}
```

---

## Key State Files

| File | Purpose |
|---|---|
| `state/chat_history.jsonl` | Persisted user/assistant turns with model, emotion, route |
| `state/expression_baseline_{pid}.json` | Per-person eyebrow + mouth EMA baseline |
| `state/wake_patterns.json` | Wake activations with hour + source |
| `state/wake_patterns_learned.json` | Patterns Ava learned from clarification answers |
| `state/clap_calibration.json` | Auto-calibrated clap threshold (deleted on every audit) |
| `state/question_history.jsonl` | Questions Ava asked + answers received |
| `state/voice_style.json` | Adaptive voice rate/volume |
| `state/connectivity_log.jsonl` | Online/offline transitions |
| `state/episodic_memory.jsonl` | Persistent episode store |
| `state/identity_proposals.jsonl` | Ava's pending identity proposals |
| `state/identity_extensions.md` | Approved additions injected into prompts |
| `state/concept_graph.json` | Concept graph nodes + edges |
| `state/restart_log.jsonl` | Watchdog restart history |
| `state/mood_carryover.json` | Emotional state across sessions |
| `state/trust_scores.json` | Per-person progressive trust |
| `state/eye_tracking/` | Calibration + gaze samples |
| `state/video_memory/` | Visual episodic clusters |
| `state/discovered_apps.json` | Found apps + games registry |
| `state/learned_apps.json` | Phrase → exe path mapping |
| `state/learned_commands.json` | Correction-learned mappings |
| `state/correction_log.jsonl` | Append-only correction history |
| `state/reminders.jsonl` | Pending + delivered reminders |
| `state/custom_commands.json` | Voice commands Ava/Zeke created |
| `state/custom_tabs.json` | UI tabs Ava/Zeke created |

---

## Module Map (current `brain/`)

| Module | Role |
|---|---|
| `avaagent.py` | Main runtime; delegates startup |
| `brain/startup.py` | All subsystem init in background daemon threads |
| `brain/signal_bus.py` | Lightweight event bus — peripheral awareness |
| `brain/operator_server.py` | FastAPI HTTP + WebSocket |
| `brain/reply_engine.py` | `run_ava` — main turn pipeline + simple-question fast path |
| `brain/prompt_builder.py` | System + memory + voice-tone + signal-bus context blocks |
| `brain/dual_brain.py` | Foreground + background parallel inference |
| `brain/ollama_lock.py` | Process-wide Ollama serialization |
| `brain/voice_loop.py` | passive / attentive / listening / thinking / speaking |
| `brain/wake_word.py` | openWakeWord (ONNX) + Whisper-poll fallback |
| `brain/wake_detector.py` | Direct vs indirect classifier; clap + oww shortcut |
| `brain/wake_learner.py` | Clarification + learned-pattern persistence |
| `brain/voice_mood_detector.py` | librosa pitch/energy/tempo/question |
| `brain/voice_commands.py` | 40 built-ins + custom command router |
| `brain/command_builder.py` | Custom command + custom tab CRUD |
| `brain/correction_handler.py` | "no, I meant X" detection + learning |
| `brain/app_discoverer.py` | Desktop / Start Menu / Program Files / Steam / Epic scan |
| `brain/question_engine.py` | When Ava asks Zeke things; cooldowns |
| `brain/tts_worker.py` | Kokoro + pyttsx3 fallback, OutputStream protected, live amplitude |
| `brain/tts_engine.py` | TTS coordinator (wraps worker) |
| `brain/stt_engine.py` | Whisper base + Silero VAD; transcript normalization |
| `brain/clap_detector.py` | Double-clap wake (floor 0.35, window 0.6s) |
| `brain/insight_face_engine.py` | InsightFace buffalo_l GPU engine |
| `brain/camera_annotator.py` | Per-frame face overlays |
| `brain/expression_calibrator.py` | Per-person expression baseline |
| `brain/ava_memory.py` | mem0 wrapper — ChromaDB + Ollama; long-term semantic memory |
| `brain/face_recognizer.py` | Legacy face_recognition lib (fallback) |
| `brain/expression_detector.py` | Legacy MediaPipe expression (fallback) |
| `brain/eye_tracker.py` | MediaPipe iris tracking |
| `brain/video_memory.py` | Persistent visual episodes |
| `brain/connectivity.py` | Online/offline monitor |
| `brain/frame_store.py` | Buffered live-frame publisher |
| `brain/heartbeat.py` | Periodic background tasks; signal consume; question + proactive checks |
| `brain/concept_graph.py` | Concept graph; Windows-safe save |
| `brain/episodic_memory.py` | Episode store + recall |
| `brain/relationship_arc.py` | Familiarity → relationship stage |
| `brain/trust_system.py` | Progressive trust |
| `brain/proactive_triggers.py` | Face greeting + Stream B insight delivery |
| `brain/person_onboarding.py` | 13-stage flow; pushes embeddings to InsightFace |
| `brain/health.py` | Health check (camera reads frame_store now) |
| `brain/background_ticks.py` | Heartbeat + video capture + Win32 clipboard / window / app-install watchers |

---

## CUDA Setup Notes

ORT 1.25.1 expects CUDA 12 runtime libs. They are pip-installed via:
```
nvidia-cublas-cu12, nvidia-cudnn-cu12, nvidia-cuda-runtime-cu12,
nvidia-cuda-nvrtc-cu12, nvidia-cufft-cu12, nvidia-curand-cu12,
nvidia-cusolver-cu12, nvidia-cusparse-cu12, nvidia-nvjitlink-cu12
```

`brain/insight_face_engine._add_cuda_paths()` registers each `site-packages/nvidia/*/bin/` with `os.add_dll_directory` BEFORE the ORT import.

Verified providers: `['TensorrtExecutionProvider', 'CUDAExecutionProvider', 'CPUExecutionProvider']`. All 5 buffalo_l ONNX sessions report `Applied providers: ['CUDAExecutionProvider', 'CPUExecutionProvider']`.

---

## protobuf Pin

`protobuf` is **pinned to 3.20.x**. MediaPipe (used by `brain/eye_tracker.py`) requires `<4`. InsightFace pulls 7.x and several training extras (`audiomentations`, `onnx`, `proto-plus`) want 7.x — those are tolerated as warnings; the runtime works with 3.20.3.

If a future install bumps protobuf, MediaPipe will fail with `'MessageFactory' object has no attribute 'GetPrototype'`. Restore with:
```bash
py -3.11 -m pip install "protobuf>=3.20,<4" --force-reinstall
```

---

## Hot Fix History (chronological — newest first)

For the complete commit-level history with what each fix did, see
**`docs/AVA_ROADMAP.md` → Section 3 Hot Fixes Log**.

| Commit | What changed |
|---|---|
| `117428f` | gitignore biometric (`faces/`) + per-machine state (`.claude/`); untracked 149 already-committed runtime files |
| `5c2322c` | ava-gemma4 identity-baked model, mem0 memory (ChromaDB + Ollama), gemma4 vision, memory UI + 5 voice commands |
| `c54bbcb` | docs: full handoff + roadmap; wake_word prefers custom hey_ava → hey_jarvis fallback (with phonetic benchmark) |
| `4477aa2` | openWakeWord + Silero VAD — production wake word + speech detection |
| `a740bcc` | Voice — clap=direct wake, Whisper Ava bias, clarification waits, OutputStream protected playback, clap floor 0.35 |
| `755f539` | Event-driven signal bus, Win32 clipboard / window / app-install watchers, zero-poll architecture |
| `8affd49` | Voice-first UI, app discovery (367 apps + 32 games), 40 voice commands, custom tabs, correction handler, pointing, reminders |
| `94bca07` | Audit pass — dead code cleanup, wiring verification, onboarding InsightFace, perf, health |
| `9d07838` | Register pip-installed CUDA DLL dirs so InsightFace runs on GPU |
| `3a5a333` | InsightFace overlays, smart wake word, attentive state, expression calibration, voice mood, 3D brain, orb breathing |
| `357dd69` | InsightFace GPU face overlay, 3D brain graph, Whisper base, orb breathing, chat fixes |
| `346d30c` | Kokoro neural TTS, orb voice reactions, real amplitude, companion orb sync |
| `fa583ea` | TTS COM thread (TTSWorker), Ollama lock, fast path timing, chat history, face greeting, clipboard, proactive |
| `7534621` | run_ava timeout protection, orb thinking pulse, always-on voice, clap sensitivity |
| `dc645d1` | clap detector — 5× ambient mult, 0.15 floor (later 0.35), 3s cooldown |
| `1975dff` | Live camera on all tabs, gate D3 brain reinit, memo OrbCanvas |
| `02c9f1f` | Widget transparent background — CSS override + backgroundColor in tauri.conf.json |
| `59eaca9` | Buffered-only live frame, 90s run_ava timeout, 5s tick timeout |
| `4ea87e8` | Widget move tool, app launcher, browser navigation tools |
| `44bb51f` | Widget capabilities, minimize detection polling, removed wrong blur fallback |
| `97409de` | STT engine bootstrap for voice loop, live camera feed from background thread |
| `5183e78` | Online flicker — 3-failure threshold, silent connecting window, 5s poll |
| `aa01b5b` | face_recognizer thread-safe singleton, diagnostic prints on all exit paths |
| `242ecb9` | Keepalive stability, app connection retry, self_model timestamp crash |
| `ae1b1fd` | Cleanup — removed DeepFace, dead imports, Gradio remnants, fix selftest |
| `ac550e7` | Removed Gradio, fix WS flicker, fix double startup, dev hot-reload mode |
| `34da8ea` | Live camera feed in Vision tab, concept_graph save mkdir, live_frame endpoint |
| `5d1a180` | Camera capture persistent connection, suppress noisy logs, global crash handler |
| `f951489` | Comprehensive bug audit + repair pass |
| `d187c80` | run_ava hang timeout protection, widget orb visibility, cloud model priority |
| `bb6b4f7` | concept_graph.json.tmp WinError 5 — process lock, skip-if-locked, stale .tmp cleanup |
| `5b22890` | MediaPipe iris landmark indices fix (left 468–472, right 473–477) |
| `5b466b6` | Eye tracking, gaze estimation, expression detection, video memory |
| `42f95cd` | Startup hang — concept_graph + self_model + vectorstore + milestone_100 to background threads |
| `2382d8f` | concept_graph tmp file lock on Windows, brain_graph 0 nodes in snapshot |
| `57d178b` | Dual-brain parallel inference — foreground + background streams, live thinking, seamless handoff |
| `4274ac7` | Cloud models, connectivity monitor, image generation, routing expansion |
| `e80e1d3` | Phase 100 — Ava is alive (20/20 integration tests, full compile sweep, Tauri build clean) |

---

## Known Issues / What Needs Testing

1. **`faces/zeke/` is empty** — must run onboarding ("hey Ava, profile me") to populate. Until then InsightFace tags every face as `unknown` (engine works, just nothing to match against).
2. **Wake word**: `hey_jarvis` is a proxy — fires reliably on some "hey ava" voices (af_bella scored 0.917) but not all (af_heart 0.307, af_nicole 0.001). Mitigated by clap detector + 60s attentive window. Custom `hey_ava.onnx` training requires WSL2 — see `docs/TRAIN_WAKE_WORD.md`.
3. **First-run InsightFace warmup ~80s** — cudnn EXHAUSTIVE algorithm search; cached afterward.
4. **First-run mem0 latency** — each `add_conversation_turn()` calls the LLM for fact extraction (~2-5s on `ava-gemma4`). Dispatched from a daemon thread in `turn_handler` so it never blocks `finalize_ava_turn`. Search path is fast.
5. **`protobuf` is pinned to 3.20.x** for MediaPipe + mem0 + InsightFace coexistence. If any future install bumps it, MediaPipe breaks with `'MessageFactory' object has no attribute 'GetPrototype'`. Restore via `pip install "protobuf>=3.20,<4" --force-reinstall`.
6. **face_recognition lib** still used as fallback when InsightFace is unavailable. Keep dlib-built install around.
7. **expression_detector.py (MediaPipe)** still wired in 5 helper paths. Coexists with `expression_calibrator` (which uses InsightFace landmarks). Either is acceptable.
8. **App discoverer scan ~47s** — one-time startup cost in a background thread; 24h refresh is incremental.
9. **Game category** in app discoverer over-includes Steam helper binaries (`gameoverlayui64.exe`, `steamservice.exe`). Fuzzy match prioritises user-friendly names; cosmetic only.
10. **Repo history** still contains earlier-committed face photos and runtime state snapshots. `117428f` stopped future leakage but historical commits remain. Optional cleanup via `git filter-repo` + force-push.

---

## Smoke Tests Done (most recent → oldest)

| Test | Result |
|---|---|
| `ollama create ava-gemma4 -f Modelfile.ava_gemma4` | PASS (model created, 3 test prompts return Ava-voiced replies) |
| mem0 + ChromaDB + Ollama add+search | PASS (extracts "Zeke enjoys building AI systems and his favorite color is red", search returns it ranked) |
| `protobuf 3.20.3` after mem0 install | RESTORED — both MediaPipe and mem0 import cleanly |
| gemma4 vision via `/api/chat` images | PASS (correctly read text from synthetic image) |
| `tsc --noEmit` | PASS |
| `npm run tauri:build` | PASS (53s, 8.6MB exe) |
| openWakeWord install + hey_jarvis load | PASS |
| Silero VAD install + `load_silero_vad()` | PASS |
| Wake detector: clap source → `(True, 1.0, "clap_triggered")` | PASS |
| Wake detector: openwakeword source → `(True, 1.0, "openwakeword_triggered")` | PASS |
| `STTEngine._normalize_transcript`: 5/5 Whisper mishearings normalized (Eva→Ava, Aye va→Ava, A va→Ava, Hey Ada→Hey Ava) | PASS |
| Phonetic benchmark: hey_jarvis vs mycroft vs rhasspy on Kokoro samples | hey_jarvis only viable (peaks 0.917 on af_bella; others ≤0.019) |
| InsightFace GPU: all 5 buffalo_l ONNX sessions on `CUDAExecutionProvider` | PASS |
| TTSWorker: `_tts_speaking` flips True during playback, amplitude > 0, both reset to 0 at end | PASS |
| TTSWorker.stop() refuses without mute, runs with mute=True | PASS |
| Win32 clipboard watcher: clipboard change fires `SIGNAL_CLIPBOARD_CHANGED` instantly | PASS |
| Win32 window hook: SetWinEventHook installs cleanly | PASS |

---

## Debug Export

`GET /api/v1/debug/export` emits a compact textual bundle:
- Ribbon/live summary
- Model routing
- Strategic continuity / memory
- Self-improvement loop state
- Deep self snapshot
- Connectivity state
- Dual-brain status
- Vision: recognized person, expression, attention, gaze
- Signal bus stats
- Full snapshot JSON (truncated)
