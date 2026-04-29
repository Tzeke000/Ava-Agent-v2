# AVA HANDOFF
**Last updated:** April 29, 2026 (audit pass — pre-launch)
**Latest commit on master:** see `git log --oneline -1`

---

## Project Overview

Ava Agent v2 is a local-first desktop AI companion running on:

- **Python 3.11** + **Ollama** (local LLMs, optional cloud models via Ollama Cloud)
- **FastAPI** operator server at `http://127.0.0.1:5876` (HTTP + WebSocket)
- **Tauri v2** + **React 18** + **Three.js** desktop app (`apps/ava-control`)
- **No Gradio** — Tauri is the only UI. Port 5876 is the only HTTP control plane.

She has emotions, memory, vision (live camera + InsightFace + eye tracking + expression calibration), voice (Kokoro neural TTS + Whisper base STT + always-on voice loop with attentive state), concept graph, episodic memory, dual-brain parallel inference, self-modification proposals, trust system, and a self-aware identity system.

All 100 phases complete. Recent passes have layered InsightFace + Kokoro + 3D brain graph + smart wake word + attentive voice state + per-person expression calibration on top.

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
- ORT cudnn EXHAUSTIVE algorithm search runs ~60–90s on first init, then caches to disk; subsequent inits are fast.
- Kokoro `hexgrad/Kokoro-82M` weights and spaCy `en_core_web_sm` download on first TTS use.
- All three are background-thread loads — main startup reaches operator HTTP in <10s.

---

## Model Setup

| Role | Model |
|---|---|
| Primary conversational | `ava-personal:latest` (fine-tuned) |
| Foreground stream (dual-brain) | `ava-personal:latest` |
| Background stream (dual-brain) | `qwen2.5:14b` / `kimi-k2.6:cloud` (when online) |
| Deep reasoning | `qwen2.5:14b` |
| Maintenance/evaluation | `mistral:7b` |
| Embeddings | `nomic-embed-text` |
| Cloud (when online) | `kimi-k2.6:cloud`, `qwen3.5:cloud`, `glm-5.1:cloud`, `minimax-m2.7:cloud` |

`brain/connectivity.py` polls `1.1.1.1` / `8.8.8.8` on a 30s cache. Cloud models are filtered out of routing when offline.

**Ollama lock**: `brain/ollama_lock.py` provides a process-wide RLock around every Ollama invocation. Stream A and Stream B can't fight for the GPU. Stream B also calls `dual_brain.pause_background_now(30s)` on every turn entry so Zeke's request goes through cleanly.

---

## Voice Stack

### TTS — Kokoro neural (CPU/GPU)
- `brain/tts_worker.py` runs Kokoro on a dedicated thread.
- Voices: 28 total. Default `af_heart`. Per-emotion mapping picks `af_bella` (high intensity expressive), `af_nicole` (soft / sad), `af_sky` (bright). Speed 0.7–1.3 scaled toward neutral by intensity.
- Falls back to pyttsx3 + Zira if Kokoro can't init.
- Live amplitude: RMS computed in 50ms windows during playback, exposed via `get_live_amplitude()` and `/api/v1/tts/state`.

### STT — Whisper base
- `brain/stt_engine.py` loads `WhisperModel("base")` on `cuda+float16` if available, falls back to `cpu+int8`.
- `beam_size=5`, `language="en"`, `vad_filter=True`.
- VAD threshold 0.008 RMS, min speech 0.3s, default silence 2.5s.
- `listen_session()` returns `audio_array` and `sample_rate` so voice_mood_detector can reuse it (no extra recording).

### Voice loop — passive / attentive / listening / thinking / speaking
- `brain/voice_loop.py` state machine.
- After speaking, drops into **attentive** for 60s: mic polls every 0.8s; speech > 1s treated as direct address (no wake word).
- Wake word (passive only): `brain/wake_detector.py` regex DIRECT vs INDIRECT classifier; ambiguous → `brain/wake_learner.py` asks for clarification (5-min cooldown) and records the answer.
- After STT, runs `brain/voice_mood_detector.py` on the audio array (reused, not re-recorded).
- Word-count-aware silence: <3 words → 4s additional listening; ≥10 words → 1.5s end.

### Voice mood
- librosa-based pitch / energy / tempo / question detection.
- Result `{label, energy, speed, is_question, avg_pitch}` stored in `g["_voice_mood"]` with `ts`.
- `prompt_builder.py` injects `VOICE TONE: {label}` into both fast and deep paths when fresh (<60s).

---

## Vision Stack

### Face recognition — InsightFace (GPU)
- `brain/insight_face_engine.py` loads buffalo_l: RetinaFace + ArcFace + 106-pt landmarks + age/gender + 3D head pose.
- Provider: `CUDAExecutionProvider`. Pip-installed CUDA libs (`nvidia-cublas-cu12`, `nvidia-cufft-cu12`, `nvidia-curand-cu12`, `nvidia-cusolver-cu12`, `nvidia-cusparse-cu12`, `nvidia-cudnn-cu12`, `nvidia-cuda-runtime-cu12`, `nvidia-cuda-nvrtc-cu12`, `nvidia-nvjitlink-cu12`) are auto-registered with `os.add_dll_directory` before ORT import.
- Inference ~41ms/frame at runtime on RTX 5060.
- `background_ticks._video_frame_capture_thread` runs InsightFace every 3rd frame (~5fps), pushes annotated frame to `frame_store`.

### Camera annotator — `brain/camera_annotator.py`
- Bounding box (green known / yellow unknown).
- 106 landmarks (key points larger).
- Head pose arrows from nose tip (green up / red right / blue forward).
- Age + gender label.
- Attention state at bottom-left (default "focused").

### Per-person expression calibration — `brain/expression_calibrator.py`
- EMA baseline of `eyebrow_ratio` and `mouth_corner_offset` per person, α=0.001.
- 300 samples → calibrated. Persists to `state/expression_baseline_{person_id}.json`.
- `detect_expression(person_id, landmarks)` returns deviation-from-baseline label: `surprised`, `frowning`, `smiling`, `neutral`. Solves the "naturally elevated eyebrows are read as surprised" problem.

### Eye tracking — MediaPipe (still used)
- `brain/eye_tracker.py` for iris / gaze. Requires `protobuf 3.20.x` (downgraded from the 7.x InsightFace pulls).

### Expression detector (legacy, fallback)
- `brain/expression_detector.py` MediaPipe-based 468-pt detector. Still imported by some helper paths (`avaagent.analyze_expression`, `brain/camera.py`, `tools/system/eye_tracking_tool.py`). Useful when InsightFace is unavailable.

---

## Bootstrap Philosophy (CRITICAL — never violate)

**NEVER choose Ava's personal preferences for her.** Every system involving preferences, style, or identity must build a discovery mechanism — Ava forms that aspect of herself through experience. Goals, hobbies, communication style, expression mappings, voice rate/volume, multitasking pattern, trust thresholds, and now per-person expression baselines + learned wake patterns all emerge from experience.

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

For each photo stage, Ava waits for "ready", then captures 3 frames from the camera. Photos saved to `faces/{person_id}/{stage}_{n}.jpg`.

**InsightFace integration** (post-audit): each captured frame is pushed into `engine.add_face(person_id, frame)` immediately, so recognition starts working within seconds — no restart needed. After the final stage, `engine.update_known_faces(faces/)` does a full reload to pick up anything missed. The legacy face_recognition lib also gets refreshed for fallback.

---

## Wiring Verification (audit-confirmed)

| System | Status | Where |
|---|---|---|
| InsightFace init | wired | `startup.py` background thread + status print |
| InsightFace per-frame | wired | `background_ticks._video_frame_capture_thread` every 3rd frame |
| Camera annotator | wired | annotates `_face_results` cache, pushes to `frame_store` |
| Expression calibrator | wired | per-frame `cal.calibrate_baseline + detect_expression` |
| Onboarding → InsightFace | wired | `add_face` per-stage + `update_known_faces` on completion |
| Voice loop attentive | wired | post-speak, 60s window, faster mic poll |
| Wake detector | wired | classifies every transcript in passive |
| Wake learner | wired | borderline conf → ask clarification |
| Voice mood (reuses STT audio) | wired | `_analyze_voice_mood_from_result(stt_result)` |
| Voice mood prompt injection | wired | both fast and deep paths in `prompt_builder.py` |
| Question engine | wired | heartbeat tick — speaks via tts_worker, mark_asked |
| Proactive triggers | wired | heartbeat + face-detection greeting |
| Ollama lock | wired | reply_engine fast + main, dual_brain live_thought + critique + creative |
| Stream B pause on turn | wired | `pause_background_now(30)` at run_ava entry |
| Chat history persistence | wired | `state/chat_history.jsonl` append in turn_handler |
| Clipboard monitor | wired | `background_ticks._clipboard_monitor_loop` 2s |
| TTS worker → main + widget orb | wired | `_tts_worker` singleton, live amplitude |
| 3D brain graph | wired | `3d-force-graph 1.80` in App.tsx, init-once + graphData updates |
| Orb breathing + drift | wired | rootGroup scale + position every frame in animate() |

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
| `state/wake_patterns_learned.json` | Patterns Ava learned from clarification answers |
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

---

## Module Map (current brain/)

| Module | Role |
|---|---|
| `avaagent.py` | Main runtime; delegates startup |
| `brain/startup.py` | All subsystem init in background daemon threads |
| `brain/operator_server.py` | FastAPI HTTP + WebSocket |
| `brain/reply_engine.py` | `run_ava` — main turn pipeline + simple-question fast path |
| `brain/prompt_builder.py` | System + memory + voice-tone block |
| `brain/dual_brain.py` | Foreground + background parallel inference |
| `brain/ollama_lock.py` | Process-wide Ollama serialization |
| `brain/voice_loop.py` | passive / attentive / listening / thinking / speaking |
| `brain/wake_detector.py` | Direct vs indirect address regex classifier |
| `brain/wake_learner.py` | Clarification + learned-pattern persistence |
| `brain/voice_mood_detector.py` | librosa pitch/energy/tempo/question |
| `brain/question_engine.py` | When Ava asks Zeke things; cooldowns |
| `brain/tts_worker.py` | Kokoro + pyttsx3 fallback, live amplitude |
| `brain/tts_engine.py` | TTS coordinator (wraps worker) |
| `brain/stt_engine.py` | Whisper base; returns audio_array for reuse |
| `brain/clap_detector.py` | Double-clap wake (5× ambient, 0.15 floor) |
| `brain/wake_word.py` | Porcupine + whisper-poll wake |
| `brain/insight_face_engine.py` | InsightFace buffalo_l GPU engine |
| `brain/camera_annotator.py` | Per-frame face overlays |
| `brain/expression_calibrator.py` | Per-person expression baseline |
| `brain/face_recognizer.py` | Legacy face_recognition lib (fallback) |
| `brain/expression_detector.py` | Legacy MediaPipe expression (fallback) |
| `brain/eye_tracker.py` | MediaPipe iris tracking |
| `brain/video_memory.py` | Persistent visual episodes |
| `brain/connectivity.py` | Online/offline monitor |
| `brain/frame_store.py` | Buffered live-frame publisher |
| `brain/heartbeat.py` | Periodic background tasks; question + proactive checks |
| `brain/concept_graph.py` | Concept graph; Windows-safe save |
| `brain/episodic_memory.py` | Episode store + recall |
| `brain/relationship_arc.py` | Familiarity → relationship stage |
| `brain/trust_system.py` | Progressive trust |
| `brain/proactive_triggers.py` | Face greeting + Stream B insight delivery |
| `brain/person_onboarding.py` | 13-stage flow; pushes embeddings to InsightFace |
| `brain/health.py` | Health check (camera reads frame_store now) |
| `brain/background_ticks.py` | Heartbeat + video capture + clipboard daemons |

---

## CUDA Setup Notes

ORT 1.25.1 expects CUDA 12 runtime libs. They are pip-installed via:
```
nvidia-cublas-cu12, nvidia-cudnn-cu12, nvidia-cuda-runtime-cu12, nvidia-cuda-nvrtc-cu12,
nvidia-cufft-cu12, nvidia-curand-cu12, nvidia-cusolver-cu12, nvidia-cusparse-cu12,
nvidia-nvjitlink-cu12
```

`brain/insight_face_engine._add_cuda_paths()` registers each `site-packages/nvidia/*/bin/` with `os.add_dll_directory` BEFORE the ORT import. This is the Python 3.8+ Windows-recommended way — `PATH` alone isn't enough for ORT's native loader on modern Windows.

Verified providers: `['TensorrtExecutionProvider', 'CUDAExecutionProvider', 'CPUExecutionProvider']`. All 5 buffalo_l ONNX sessions report `Applied providers: ['CUDAExecutionProvider', 'CPUExecutionProvider']`.

---

## Known Issues / Open Items (for testing)

1. **Voice mood now reuses STT audio** — no extra recording, no added latency. Verify in logs: `[voice_mood] ... (reused STT audio)`.
2. **Camera health check** — now reads `frame_store.peek_buffer_age_sec()` first; only reports `error` if no frames for >10s. Earlier "Health: ERROR | camera:error" should no longer fire when capture is running.
3. **First-run InsightFace warmup ~80s** — startup logs warn about this; subsequent runs hit the cudnn cache.
4. **Simple question fast path** — verified end-to-end in `reply_engine.run_ava`. Logs `[run_ava] FAST PATH: simple question` and `FAST PATH complete in {time}s`.
5. **face_recognition lib** still used as fallback when InsightFace is unavailable. Keep dlib-built install around.
6. **expression_detector.py (MediaPipe)** still wired in 5 helper paths. Coexists with `expression_calibrator` (which uses InsightFace landmarks). Either is acceptable.

---

## Smoke Tests Done This Pass

| Test | Result |
|---|---|
| `wake_detector` 10/10 cases | PASS |
| `expression_calibrator` neutral / surprised / smiling on synthetic 106-pt | PASS |
| `voice_mood_detector` excited / neutral / question on synthetic tones | PASS |
| `question_engine` cooldown + busy-mode skip | PASS |
| InsightFace GPU initialization | PASS (`provider=CUDAExecutionProvider`, ~41ms/frame) |
| `tts_worker` Kokoro speak with emotion + live amplitude RMS | PASS (45 non-zero amplitude samples / 50 chars) |
| Ollama lock serialization | PASS (concurrent calls serialize as expected) |
| `protobuf 3.20.3` — both mediapipe and insightface working | PASS |
| `tsc --noEmit` clean | PASS |
| `npm run tauri:build` | PASS |

---

## Debug Export

`GET /api/v1/debug/export` emits a compact textual bundle:
- Ribbon/live summary
- Model routing
- Strategic continuity / memory
- Self-improvement loop state
- Deep self snapshot (mood, energy, critique averages, pending repairs)
- Connectivity state
- Dual-brain status (foreground busy, background queue, live thought)
- Vision: recognized person, expression, attention, gaze
- Full snapshot JSON (truncated)
