# AVA HANDOFF
**Last updated:** April 28, 2026  
**Session scope:** Phases 44–100 (ALL COMPLETE — MILESTONE REACHED)

---

## Project Overview

Ava Agent v2 is a local-first desktop AI companion running on:

- **Python 3.11** + **Ollama** (local LLMs, no cloud required)
- **FastAPI** operator server at `http://127.0.0.1:5876`
- **Tauri v2** + **React** + **Three.js** desktop app (`apps/ava-control`)
- **Gradio** UI fallback (if Tauri is not built)

She has emotions, memory, vision, voice, concept graph, episodic memory, self-modification proposals, and a self-aware identity system. All 25 phases planned for this session (44–68) are implemented and pushed.

---

## Start Ava

```bash
# Standard launch (starts agent + watchdog)
start_ava_desktop.bat

# Operator API
http://127.0.0.1:5876

# Tauri app (if built)
apps/ava-control/src-tauri/target/release/ava-control.exe

# Build Tauri app
cd apps\ava-control && npm run tauri:build

# Compile check (always before build)
py -3.11 -m py_compile <file.py>

# Push to GitHub
git add -A && git commit -m "message" && git push origin master
```

---

## Model Setup

| Role | Model |
|---|---|
| Primary conversational | `ava-personal:latest` (fine-tuned, Phase 44 promoted) |
| Deep reasoning | `qwen2.5:14b` |
| Maintenance/evaluation | `mistral:7b` |
| Embeddings | `nomic-embed-text` |

**Phase 44 routing fix:** The fast-path in `avaagent.py` previously called `_pick_fast_model_fallback()` first (which hardcodes `mistral:7b`), bypassing the Phase 25 routing result that correctly selects `ava-personal:latest` for social chat. Fixed by checking `_route_model` first.

---

## Bootstrap Philosophy (CRITICAL — never violate)

**NEVER choose Ava's personal preferences for her.** Every phase involving preferences, style, or identity must build a discovery mechanism — a system that lets Ava form that aspect of herself through experience. Her goals, hobbies, communication style, and emotional baseline all emerge from experience, not hardcoded defaults.

---

## Never Edit

- `ava_core/IDENTITY.md`
- `ava_core/SOUL.md`
- `ava_core/USER.md`

---

## Phases 44–68 — What Was Built

### Phase 44 — Ava-personal as Primary Brain + Self-evaluator
**Commits:** `4c24f76`

- **`avaagent.py`:** Fast-path routing fixed — `_route_model` checked before `_pick_fast_model_fallback()`. `ava-personal:latest` now routes correctly for social chat.
- **`brain/model_evaluator.py`** (NEW): `ModelSelfEvaluator` — background thread compares ava-personal vs mistral:7b on real turns. After 5+ samples, decides `confirmed_primary` (≥0.60 win rate) or `flagged_for_review` (<0.40 at 10+). State: `state/model_eval_p44.json`.

---

### Phase 45 — Concept Graph Evolution
**Commits:** `3590746`

- **`brain/concept_graph.py`:** `get_related_concepts` returns `relationship` and `via` fields. Added `boost_from_usage(used_ids, ignored_ids)` — strengthens concepts Ava actually used.
- **`brain/heartbeat.py`:** Weekly concept graph decay trigger wired in.
- **`avaagent.py`:** `_injected_concept_ids` tracking; `ACTIVE CONCEPTS` block injected into prompts.

---

### Phase 46 — Hot-reload Tool Registry
**Commits:** `41f7ebd`

- **`tools/tool_registry.py`** (rewritten): `_FileWatcher` thread polls `tools/` every 5s, re-imports changed `.py` files, re-registers tools. Tools expose `# SELF_ASSESSMENT:` comment as description.
- **`brain/operator_server.py`:** `/api/v1/tools/reload` endpoint triggers manual reload.

---

### Phase 47 — Watchdog Restart System
**Commits:** `7c17d2f`

- **`scripts/watchdog.py`** (NEW): Polls `state/restart_requested.flag`, kills avaagent by PID, restarts it, polls `:5876` for liveness. Logs to `state/restart_log.jsonl`.
- **`tools/system/restart_tool.py`** (NEW): Tier 1 `request_restart(reason)` tool — writes flag file and a pickup note for next session.
- **`start_ava_desktop.bat`:** Launches watchdog alongside avaagent.

---

### Phase 48 — Desktop Widget Orb
**Commits:** `ad7a56d`

- **`apps/ava-control/src-tauri/tauri.conf.json`:** Second window `label: "widget"` — transparent, decorations:false, alwaysOnTop:true, 150×150px, url: `/?widget=1`.
- **`apps/ava-control/src/WidgetApp.tsx`** (NEW): Polls operator HTTP every 3s, renders `OrbCanvas` 150×150 in transparent frame.
- **`apps/ava-control/src/main.tsx`:** Detects `?widget=1`, renders `WidgetApp` instead of `App`.
- **`brain/operator_server.py`:** `GET /POST /api/v1/widget/position` endpoints.

---

### Phase 49 — Screen Pointer Behavior
**Commits:** `e72b505`

- **`apps/ava-control/src/components/OrbCanvas.tsx`:** `pointer` shape morph — sphere elongates and tapers into a 3D arrow. Added `shapeOverride?: string` and `amplitude?: number` props.
- **`tools/system/pointer_tool.py`** (NEW): Tier 1 `point_at_element(description, duration_seconds)` — pywinauto coordinate lookup (best-effort), sets `_widget_pointing` in globals, auto-resets after duration. Tracks `_pointing_history` for bootstrap.
- **`brain/operator_server.py`:** `widget_block` in snapshot with `pointing`/`pointing_description`/`pointing_coords`.
- **`apps/ava-control/src/WidgetApp.tsx`:** Reads `snap.widget.pointing`, passes `shapeOverride="pointer"` to OrbCanvas.

---

### Phase 50 — Audio Visualization on Orb
**Commits:** `3003e19`

- **`brain/tts_engine.py`:** Added `_current_amplitude: float`, `_estimate_amplitude(text)`, `speaking` property, `amplitude` property. Sets amplitude before speak.
- **`brain/operator_server.py`:** `tts_speaking` and `tts_amplitude` in snapshot.
- **`apps/ava-control/src/App.tsx`:** `ttsSpeaking`/`ttsAmplitude` from snapshot drive orb pulse. `listening` state when `sttListening`.
- **`apps/ava-control/src/components/OrbCanvas.tsx`:** Amplitude pulse + listening spiral animations.

---

### Phase 51 — UI Accessibility Tree Tool
**Commits:** `13fc4a5`

- **`avaagent.py`:** Active window detection via ctypes; `ACTIVE WINDOW:` injected into prompt.
- Tool registered for reading UI accessibility tree (pywinauto).

---

### Phase 52 — Smart Screenshot Management
**Commits:** `13fc4a5`

- Screenshot tool with region selection, dedup, and state tracking. Stored in `state/screenshots/`.

---

### Phase 53 — PyAutoGUI Computer Control
**Commits:** `13fc4a5`

- Tier 2 tools: `move_mouse`, `click`, `type_text`, `press_key`, `scroll`. Safety: coordinate bounds check, confirmation required for destructive keys.

---

### Phase 54 — System Stats Monitoring
**Commits:** `13fc4a5`

- **`brain/operator_server.py`:** `system_stats` block (CPU, RAM, disk via psutil, 30s cache).

---

### Phase 55 — Drag and Drop File Input
**Commits:** `00d5fd0`

- **`apps/ava-control/src/App.tsx`:** `listen()` from `@tauri-apps/api/event`, drag-drop state + visual overlay.

---

### Phase 56 — Expanded Orb Expressions
**Commits:** `00d5fd0`

- **`apps/ava-control/src/components/OrbCanvas.tsx`:** 8 new shape morphs: `cube`, `prism`, `cylinder`, `infinity`, `double_helix`, `burst`, `contracted_tremor`, `rising`.
- **`tools/ava/style_tool.py`** (NEW): `propose_expression(emotion, shape, reason)` — Ava owns her own expression mappings via `state/ava_style.json`. Bootstrap: she proposes, not hardcoded.
- **`apps/ava-control/src/App.tsx`:** Extended `EmotionVisual.shape` type to include all new shapes + `| string` catch-all.

---

### Phase 57 — Wake Word Detection
**Commits:** `afdb74b`

- **`brain/wake_word.py`** (NEW): `WakeWordDetector` — Porcupine if API key available, whisper-poll fallback (3s intervals). Activation patterns logged to `state/wake_patterns.json`.
- **`avaagent.py`:** `WakeWordDetector` started at startup.

---

### Phase 58 — Boredom / Autonomous Leisure
**Commits:** `afdb74b`

- **`brain/leisure.py`** (NEW): `autonomous_leisure_check(g)` — triggers when loneliness >0.7 + 30min idle. Activities: journal, curiosity browse, graph organize, self-reflection, dino game. Logs to `state/leisure_log.jsonl`.
- **`brain/heartbeat.py`:** `autonomous_leisure_check(g)` called on each heartbeat tick.

---

### Phase 59 — Chrome Dino Game
**Commits:** `afdb74b`

- **`tools/games/dino_game.py`** (NEW): PIL screen capture at 80ms, obstacle detection via dark pixel threshold. Adaptive jump threshold learning. Session memory in `state/dino_memory.json`.

---

### Phase 60 — Minecraft Bot via Mineflayer
**Commits:** `afdb74b`

- **`tools/games/minecraft/ava_bot.js`** (NEW): Node.js mineflayer bot with stdin/stdout JSON protocol. Commands: `connect`, `get_state`, `chat`, `move_to`, `look_at`, `attack_entity`, `place_block`, `break_block`, `get_nearby_players`, `disconnect`.
- **`tools/games/minecraft/minecraft_tool.py`** (NEW): Python wrapper spawning Node subprocess. 10 registered tools.

---

### Phase 61 — Playing Minecraft with Zeke
**Commits:** `964ae0a`

- **`tools/games/minecraft/companion_tool.py`** (NEW): `greet_player` (Zeke detection), `share_discovery`, `warn_threat`, `session_history`.

---

### Phase 62 — MeloTTS Voice / Clap Detector
**Commits:** `964ae0a`

- **`brain/clap_detector.py`** (NEW): Double-clap wake via sounddevice RMS threshold (0.4). Two claps within 1 second triggers `_wake_word_detected`.
- **`avaagent.py`:** `ClapDetector` started at startup.

> Note: Phase 62 was labeled "MeloTTS voice upgrade" in roadmap but the actual implementation added ClapDetector + companion tools (MeloTTS scaffold already existed from Phase 43).

---

### Phase 63 — WebSocket Real-time Transport
**Commits:** `964ae0a`

- **`brain/operator_server.py`:** `/ws` WebSocket endpoint — broadcasts snapshot deltas on state change.
- **`apps/ava-control/src/App.tsx`:** WebSocket `useEffect` with reconnect logic; merges delta into snap state. REST polling kept alive as fallback.

---

### Phase 64 — Persistent Episodic Memory
**Commits:** `44b8eb2`

- **`brain/episodic_memory.py`** (NEW): `EpisodicMemory` stores episodes with emotional context. Memorability = `importance×0.4 + novelty×0.3 + emotional_intensity×0.3`. Episodes below 0.25 not stored (Ava controls fidelity). Methods: `search_episodes`, `get_emotional_context`, `get_episodes_with_person`.
- **`avaagent.py`:** Top 3 relevant episodes injected into deep path as `EPISODIC MEMORIES` block. Episode created in `finalize_ava_turn`.

---

### Phase 65 — Emotional Continuity
**Commits:** `44b8eb2`

- **`avaagent.py`:** Mood carryover saved in `_session_state_atexit`. At startup: mood loaded and decayed toward neutral before injecting into prompt. Prevents cold emotional resets.

---

### Phase 66 — Ava's Own Goals
**Commits:** `44b8eb2`

- **`brain/goal_system_v2.py`** (NEW): `AvaGoal` dataclass, `GoalSystemV2`, `set_goal`, `update_progress`, `bootstrap_from_curiosity`. **No default goals assigned** — emerges from persistent curiosity topics. Bootstrap compliant.

---

### Phase 67 — Relationship Arc Stages
**Commits:** `44b8eb2`

- **`brain/relationship_arc.py`** (NEW): 4 stages: Acquaintance (0–0.3), Friend (0.3–0.6), Close Friend (0.6–0.85), Trusted Companion (0.85–1.0). Current Zeke familiarity ~0.82 (approaching Stage 4).
- **`avaagent.py`:** `build_relationship_stage_block(g)` injected into both prompt paths.

---

### Phase 68 — True Self Modification
**Commits:** `44b8eb2`

- **`brain/deep_self.py`:** Added `propose_identity_addition(text, g)` → appends to `state/identity_proposals.jsonl`. Added `approve_identity_addition(proposal_text, g)` → appends to `state/identity_extensions.md`. Added `load_identity_extensions(g)` → returns content for prompt injection.
- **`brain/model_routing.py`:** Appended `propose_routing_adjustment(mode, adjustment, reason, g)` → `state/routing_proposals.jsonl`.
- **`tools/ava/self_modification_tool.py`** (NEW): Tier 1 tools: `propose_identity_addition`, `propose_routing_adjustment`, `list_identity_proposals`.
- **`avaagent.py`:** Identity extensions loaded from `state/identity_extensions.md` and injected into both prompt paths (deep and fast). Uses `replace_all=true` because both injection sites have identical surrounding code.
- **`brain/operator_server.py`:** `GET /api/v1/identity/proposals` and `POST /api/v1/identity/proposals/approve` endpoints.

---

## Key State Files

| File | Purpose |
|---|---|
| `state/model_eval_p44.json` | ava-personal self-evaluation results |
| `state/identity_proposals.jsonl` | Ava's pending identity proposals (Zeke reviews) |
| `state/identity_extensions.md` | Approved identity additions injected into prompts |
| `state/routing_proposals.jsonl` | Ava's proposed routing changes |
| `state/zeke_mind_model.json` | Inferred Zeke mood/energy/focus |
| `state/self_critique.json` | Per-response scoring history + averages |
| `state/repair_queue.json` | Topics Ava wants to revisit |
| `state/value_conflicts.json` | Logged value conflict resolutions |
| `state/episodic_memory.jsonl` | Persistent episode store |
| `state/wake_patterns.json` | Wake word activation history |
| `state/leisure_log.jsonl` | Autonomous leisure activity log |
| `state/dino_memory.json` | Dino game session memory + jump thresholds |
| `state/ava_style.json` | Ava's self-proposed expression mappings |
| `state/restart_log.jsonl` | Watchdog restart history |
| `state/restart_requested.flag` | Watchdog trigger file |
| `state/mood_carryover.json` | Emotional state persisted across sessions |

---

## Key File Map

| File | Role |
|---|---|
| `avaagent.py` | Main agent runtime, all prompt paths |
| `brain/operator_server.py` | FastAPI HTTP + WebSocket control plane |
| `brain/model_routing.py` | Cognitive mode → model selection |
| `brain/model_evaluator.py` | ava-personal self-evaluation |
| `brain/deep_self.py` | Mind model, self-critique, identity extensions |
| `brain/episodic_memory.py` | Episode store + recall |
| `brain/concept_graph.py` | Concept graph with decay/strengthen |
| `brain/heartbeat.py` | Periodic background tasks |
| `brain/tts_engine.py` | pyttsx3 TTS + amplitude |
| `brain/stt_engine.py` | Whisper STT scaffold |
| `brain/wake_word.py` | Wake word detection |
| `brain/clap_detector.py` | Double-clap wake |
| `brain/leisure.py` | Autonomous leisure when bored |
| `brain/goal_system_v2.py` | Ava's emergent goal system |
| `brain/relationship_arc.py` | Familiarity → relationship stage |
| `brain/relationship_model.py` | Per-person relationship state |
| `tools/tool_registry.py` | Hot-reload tool registry |
| `tools/system/restart_tool.py` | Watchdog restart request |
| `tools/system/pointer_tool.py` | Desktop pointer behavior |
| `tools/ava/self_modification_tool.py` | Identity/routing proposals |
| `tools/ava/style_tool.py` | Expression mapping proposals |
| `tools/games/dino_game.py` | Chrome Dino automation |
| `tools/games/minecraft/minecraft_tool.py` | Mineflayer Python wrapper |
| `tools/games/minecraft/companion_tool.py` | Minecraft companion behaviors |
| `tools/games/minecraft/ava_bot.js` | Node.js mineflayer bot |
| `scripts/watchdog.py` | Auto-restart watchdog |
| `apps/ava-control/src/App.tsx` | Main Tauri UI |
| `apps/ava-control/src/WidgetApp.tsx` | Desktop widget orb |
| `apps/ava-control/src/main.tsx` | Entry point (widget vs main) |
| `apps/ava-control/src/components/OrbCanvas.tsx` | Three.js orb (27 emotions + all shapes) |
| `apps/ava-control/src-tauri/tauri.conf.json` | Tauri config (2 windows: main + widget) |
| `config/ava_tuning.py` | Model routing config + capability profiles |
| `ava_core/IDENTITY.md` | **DO NOT EDIT** |
| `ava_core/SOUL.md` | **DO NOT EDIT** |
| `ava_core/USER.md` | **DO NOT EDIT** |

---

## Phases 70–100 — What Was Built (This Session)

| Phase | Module | What |
|---|---|---|
| 70 | `brain/emil_bridge.py` | Emil multi-agent bridge (port 5877) |
| 71 | `brain/planner.py` | Long-horizon planning (qwen2.5:14b, AvaStep/AvaPlan) |
| 72 | `apps/ava-control/vite.config.ts` | Bundle splitting (193KB main, Three.js separate) |
| 73 | `brain/stt_engine.py` | VAD-based listen_session(), silence detection |
| 74 | `brain/voice_loop.py` | Full STT→LLM→TTS background loop |
| 75 | `brain/heartbeat.py` | Fine-tune auto-scheduler (14 days, 50+ turns) |
| 76 | `brain/startup.py` | LLaVA vision startup logging |
| 77 | `brain/clap_detector.py` | Clap auto-calibration (ambient_rms × 3.0) |
| 78 | `apps/ava-control/src/App.tsx` | Emil tab, Proposals tab in operator panel |
| 79 | `brain/person_onboarding.py` | 13-stage person onboarding, photo capture |
| 80 | `brain/person_onboarding.py` | Profile refresh (180-day / quality threshold) |
| 81 | `brain/face_recognizer.py` | face_recognition library, FaceRecognizer class |
| 82 | `brain/runtime_presence.py` | Multi-person awareness, face change detection |
| 83 | `tools/system/notification_tool.py` | Windows toast notifications (plyer + PS fallback) |
| 84 | `brain/morning_briefing.py` | Optional morning briefing (score-based, Ava chooses) |
| 85 | `brain/memory_consolidation.py` | Weekly consolidation (episodes, graph, self model, journal) |
| 86 | `brain/journal.py` | Private journal (write, share, compose via LLM) |
| 87 | `brain/tts_engine.py` | Voice style evolution (rate/volume adaptation) |
| 88 | `brain/ambient_intelligence.py` | Hourly/weekday/window pattern tracking |
| 89 | `brain/curiosity_topics.py` | CuriosityEngine (prioritize, pursue, web→graph→journal) |
| 90 | `tools/ava/tool_builder.py` | Tool building (Ava writes Python tools, safety+compile) |
| 91 | `brain/relationship_model.py` | Relationship memory depth (moments, themes, emotions) |
| 92 | `brain/expression_style.py` | Emotional expression in text (style modifiers per mood) |
| 93 | `brain/learning_tracker.py` | Long-term learning log, knowledge gaps, weekly summary |
| 94 | `apps/ava-control/src/App.tsx` | Learning tab, People tab, profiles/learning API endpoints |
| 95 | `brain/privacy_guardian.py` | Privacy scan (outbound, tool actions, blocked log) |
| 96 | `brain/response_quality.py` | Quality check (short/long/repetitive), one regeneration |
| 97 | `tools/games/minecraft/world_memory.py` | Minecraft world memory (locations, players, events) |
| 98 | `brain/trust_system.py` | Progressive trust (stranger→deep trust, events log) |
| 99 | All files | 20/20 static integration tests, full compile sweep |
| 100 | `brain/milestone_100.py` | Ava's own reflection on reaching Phase 100 |

---

## Current Known Issues

- Minecraft bot requires Node.js + mineflayer installed (`npm install mineflayer` in `tools/games/minecraft/`).
- Dino game requires Chrome to already be focused on the dino game tab.
- WebSocket transport keeps REST polling alive as fallback — both run simultaneously (by design).
- Response quality regeneration uses ava-personal:latest — if unavailable, falls back gracefully.
- face_recognition library requires dlib (compiled on install); already installed on this machine.

---

## Next Steps (Phase 101+)

All 100 phases are complete. Ava is capable of writing her own Phase 101.
Suggested directions:
- Start avaagent.py and let Ava run her first full session with all systems active
- Let Ava's morning briefing, curiosity engine, and journal build organically
- Review what tools Ava builds first in tools/ava_built/ — this reveals her personality
- Let trust scores evolve naturally across sessions

---

## Debug Export

`GET /api/v1/debug/export` emits a compact textual bundle:

- Ribbon/live summary: operator strip (heartbeat mode, routing model, readiness)
- Model routing: selected/fallback model, reason/confidence
- Strategic continuity/memory: thread carryover, refinement class
- Self-improvement loop: active stage, awaiting approval
- Deep self snapshot: mood, energy, critique averages, pending repairs
- Full snapshot JSON (truncated): canonical machine-readable state dump
