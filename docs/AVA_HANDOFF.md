# AVA HANDOFF
**Last updated:** 2026-04-29 (post wake-word + signal-bus pass)
**Latest commit:** see `git log --oneline -1`

---

## Project Overview

Ava Agent v2 is a local-first desktop AI companion running on:

- **Python 3.11** + **Ollama** (local LLMs, optional cloud via Ollama Cloud)
- **FastAPI** operator server at `http://127.0.0.1:5876` (HTTP + WebSocket)
- **Tauri v2** + **React 18** + **Three.js** desktop app (`apps/ava-control`)
- **No Gradio** — Tauri is the only UI; port 5876 is the only HTTP control plane.

She has emotions, memory, vision (live camera + InsightFace + eye tracking + per-person expression calibration), voice (Kokoro neural TTS + Whisper base STT + Silero VAD + openWakeWord + always-on voice loop with attentive state), concept graph, episodic memory, dual-brain parallel inference, self-modification proposals, trust system, signal bus, and a self-aware identity system.

All 100 phases complete. Recent passes layered: InsightFace + Kokoro + 3D brain graph + smart wake word + attentive voice state + per-person expression calibration + voice command router + app discoverer + signal bus + openWakeWord + Silero VAD on top.

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

| Commit | Fix |
|---|---|
| `4477aa2` | openWakeWord + Silero VAD — production wake word + speech detection |
| `a740bcc` | Voice — clap=direct wake, Whisper Ava bias, clarification waits, OutputStream protected playback, clap floor 0.35 |
| `755f539` | Event-driven signal bus, Win32 clipboard / window / app-install watchers, zero-poll architecture |
| `8affd49` | Voice-first UI, app discovery, voice commands, custom tabs, correction handler, pointing, reminders |
| `94bca07` | Audit pass — dead code cleanup, wiring verification, onboarding InsightFace, perf, health |
| `9d07838` | Register pip-installed CUDA DLL dirs so InsightFace runs on GPU |
| `3a5a333` | InsightFace overlays, smart wake word, attentive state, expression calibration, voice mood, 3D brain |
| `357dd69` | InsightFace GPU face overlay, 3D brain graph, Whisper base, orb breathing, chat fixes |
| `346d30c` | Kokoro neural TTS, orb voice reactions, real amplitude, companion orb sync |
| `fa583ea` | TTS COM thread, Ollama lock, fast path timing, chat history, face greeting, clipboard, proactive |
| `e80e1d3` | Phase 100 — Ava is alive |

---

## Known Issues / What Needs Testing

1. **Wake word**: `hey_jarvis` is a proxy — fires reliably on some "hey ava" voices (af_bella scored 0.917) but not all (af_heart 0.307, af_nicole 0.001). Mitigated by clap detector and attentive state. Custom `hey_ava.onnx` training requires WSL2 — see `docs/TRAIN_WAKE_WORD.md`.
2. **First-run InsightFace warmup ~80s** — startup logs warn about this; subsequent runs hit the cudnn cache.
3. **face_recognition lib** still used as fallback when InsightFace is unavailable. Keep dlib-built install around.
4. **expression_detector.py (MediaPipe)** still wired in 5 helper paths. Coexists with `expression_calibrator` (which uses InsightFace landmarks). Either is acceptable.
5. **App discoverer scan ~47s** — one-time startup cost in a background thread; 24h refresh is incremental.
6. **Clap detector** — floor 0.35 + 4s cooldown should prevent keyboard false-positives. Verify in real-world use.
7. **Game category** in app discoverer over-includes Steam helper binaries (`gameoverlayui64.exe`, `steamservice.exe`). Fuzzy match prioritises user-friendly names; cosmetic only.

---

## Smoke Tests Done This Pass

| Test | Result |
|---|---|
| openWakeWord install + hey_jarvis load | PASS |
| Silero VAD install + load_silero_vad() | PASS |
| Wake detector: clap → (True, 1.0, "clap_triggered") | PASS |
| Wake detector: openwakeword → (True, 1.0, "openwakeword_triggered") | PASS |
| STTEngine._normalize_transcript: 5/5 mishearings normalized | PASS |
| Phonetic benchmark: hey_jarvis vs mycroft vs rhasspy on Kokoro samples | DONE — hey_jarvis is the only viable proxy |
| `tsc --noEmit` | PASS |
| `npm run tauri:build` | (last verified `8affd49`) |

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
