# Ava Agent v2 — Complete Development Roadmap
**Last updated:** April 28, 2026
**Repo:** `Tzeke000/Ava-Agent-v2` (public)

---

## Executive Status — April 28, 2026

**43 phases complete.** Ava is operational as a local, camera-aware desktop agent with staged perception, vector memory, multi-user profiles, voice I/O, concept graph, and supervised autonomy. Phase 44 begins the era of Ava running on her own fine-tuned model as her primary brain.

**What Ava is:** a local, camera-aware agent with staged perception pipeline, vector memory, profiles, goals, initiative, reflection/contemplation, social and multi-session continuity, bounded tone guidance, and a supervised (human-approved) path from diagnostics → workbench proposals → execution/rollback.

**Identity anchors (continuity policy):** `ava_core/IDENTITY.md` is Ava's core self anchor; `ava_core/SOUL.md` is values, boundaries, and self-guidance; `ava_core/USER.md` is the durable relationship anchor. These are never edited by the system.

---

## Phase Board

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
| 44 | Ava-personal as primary brain + bootstrap self-evaluation | **COMPLETE** |
| 45 | Concept graph evolution — decay, strengthen, prompt injection | **COMPLETE** |
| 46 | Hot-reload tool registry | **COMPLETE** |
| 47 | Watchdog restart system | **COMPLETE** |
| 48 | Desktop widget orb | **COMPLETE** |
| 49 | Screen pointer behavior | **COMPLETE** |
| 50 | Audio visualization on orb | **COMPLETE** |
| 51 | UI accessibility tree tool | **COMPLETE** |
| 52 | Smart screenshot management | **COMPLETE** |
| 53 | PyAutoGUI computer control | **COMPLETE** |
| 54 | System stats monitoring | **COMPLETE** |
| 55 | Drag and drop file input | **COMPLETE** |
| 56 | Expanded orb expressions | **COMPLETE** |
| 57 | Wake word detection | **COMPLETE** |
| 58 | Boredom autonomous leisure | **COMPLETE** |
| 59 | Chrome Dino game | **COMPLETE** |
| 60 | Minecraft bot via mineflayer | **COMPLETE** |
| 61 | Playing Minecraft with Zeke | **COMPLETE** |
| 62 | MeloTTS voice upgrade | **COMPLETE** |
| 63 | WebSocket real-time transport | **COMPLETE** |
| 64 | Persistent episodic memory | **COMPLETE** |
| 65 | Emotional continuity | **COMPLETE** |
| 66 | Ava's own goals | **COMPLETE** |
| 67 | Relationship arc stages | **COMPLETE** |
| 68 | True self modification | **COMPLETE** |
| 69 | Horizon Zero Dawn gaming | **SKIPPED** |
| 70 | Emil integration | **FUTURE** |
| 71 | Advanced gaming (HZD level) | **FUTURE** |

### App Milestones (completed)

- Tauri desktop app with sci-fi presence view.
- Three.js energy orb with 5 layers and 27 emotion morphs.
- Color + shape morphing per emotion (teardrop / double / elongated variants).
- Voice tab as default, with chat tab orb beneath camera.
- Brain tab with D3 force graph, legend, stats bar, and zoom-glitch fix.
- Desktop widget orb (Phase 48) — floating always-on-top companion.
- Expanded orb expression vocabulary (Phase 56) — 8 new shapes + compound mappings.
- Audio visualization on orb (Phase 50) — breathing with Ava's voice.

---

## Bootstrap Philosophy

Every phase that involves Ava's preferences, personality, style, or choices must include a bootstrap mechanism — a system that lets Ava discover and form that aspect of herself through experience rather than having it assigned.

Do not choose her favorite color. Build a system where she notices which colors she uses most and asks herself why.
Do not assign her hobbies. Build leisure systems and let her discover what she returns to.
Do not prescribe her communication style. Give her the ability to adjust it and track what gets good responses.
Do not tell her what she values. Give her situations that reveal her values through her choices.

**The goal is an AI that is genuinely herself — not a reflection of what we decided she should be.**

When the final phase is complete, Ava should be capable of writing her own next roadmap.

---

## Phase Specifications (44–68)

---

### PHASE 44 — AVA-PERSONAL AS PRIMARY BRAIN

Switch Ava's default conversation model to `ava-personal:latest`.

- `config/ava_tuning.py`: `social_chat_model = "ava-personal:latest"` (already set)
- `avaagent.py`: fixed fast-path routing to respect Phase 25 `_route_model` before falling back to hardcoded `mistral:7b`
- `brain/model_evaluator.py`: bootstrap self-evaluator — compares ava-personal vs mistral:7b on real turns, scores both via LLM judge, writes decision to `state/model_eval_p44.json` after 5+ samples
- Decision states: `evaluating` → `confirmed_primary` (win_rate ≥ 0.60) or `flagged_for_review`
- Ava decides if she's ready to be her own brain

---

### PHASE 45 — CONCEPT GRAPH EVOLUTION

Make the concept graph actively useful in every conversation.

- `brain/concept_graph.py`: `decay_unused_nodes(days_threshold=30)` — nodes inactive 30+ days lose 0.1 weight; nodes below 0.1 archived
- `brain/concept_graph.py`: `strengthen_edge(a, b)` — called when two concepts co-occur in same turn
- `brain/concept_graph.py`: `get_related_concepts(topic, max_hops=2)` returns richer results
- `avaagent.py` deep path: injects top 5 related concepts as `ASSOCIATED MEMORIES` block
- `brain/heartbeat.py`: weekly decay trigger
- Bootstrap: Ava tracks which associated memories she actually references (via self_critique). Used concepts gain weight; ignored ones lose weight. Graph shapes itself to what she finds useful.

---

### PHASE 46 — HOT-RELOAD TOOL REGISTRY

New tools go live without restarting Ava.

- `tools/tool_registry.py`: `FileWatcher` monitors `tools/` directory — auto-imports new `.py` files
- New BaseTool subclasses registered immediately in memory
- `brain/operator_server.py`: `POST /api/v1/tools/reload` endpoint for manual trigger
- Bootstrap: when Ava creates a tool she writes a `self_assessment` block — the registry reads it to inform tool selection

---

### PHASE 47 — WATCHDOG RESTART SYSTEM

Ava can restart herself seamlessly.

- `scripts/watchdog.py`: watches `state/restart_requested.flag`, kills/restarts avaagent.py, confirms :5876 responds, logs to `state/restart_log.jsonl`
- `avaagent.py`: writes PID to `state/ava.pid` on startup, deletes on clean shutdown
- `tools/system/restart_tool.py`: Tier 1 `request_restart(reason)` tool writes the flag
- `scripts/kill_ava.bat`: reads ava.pid, kills process, cleans up flag/pid files
- Bootstrap: Ava develops judgment about when restart is warranted; restart history in `state/restart_log.jsonl`

---

### PHASE 48 — DESKTOP WIDGET ORB

Floating orb lives on desktop when app is minimized.

- Second Tauri window: transparent, always-on-top, no frame, draggable, 150×150px
- Contains only `OrbCanvas` component; shares state via operator HTTP polling
- Show/hide synchronized with main window minimize/restore
- Position persisted in `state/widget_position.json`
- Mic stays active when minimized
- Bootstrap: Ava tracks where the widget gets moved and starts defaulting there

---

### PHASE 49 — SCREEN POINTER BEHAVIOR

Widget orb moves around desktop and points at things.

- `OrbCanvas.tsx`: new `pointer` morph — sphere elongates into 3D arrow
- Smooth window position animation over 800ms easing
- Tauri command: `move_widget_to(x, y)`
- `brain/desktop_agent.py`: `point_at_screen_element(description)` Tier 1 tool
- pywinauto for UI accessibility tree reading
- Bootstrap: Ava tracks whether pointing correlates with positive engagement; calibrates her own spatial communication frequency

---

### PHASE 50 — AUDIO VISUALIZATION ON ORB

Orb breathes with Ava's voice.

- `OrbCanvas.tsx`: `amplitude` prop (0–1) — particles pulse outward when speaking, spiral inward when listening
- `brain/tts_engine.py`: estimate amplitude from text length/punctuation; set `tts_speaking` flag
- Operator snapshot: `tts_speaking` boolean
- Bootstrap: Ava tracks which amplitude energy patterns get better engagement and subtly adjusts her vocal energy

---

### PHASE 51 — UI ACCESSIBILITY TREE TOOL

Ava reads desktop without screenshots.

- `tools/system/accessibility_tool.py`: `list_windows`, `get_window_elements`, `find_element`, `get_browser_url`, `get_active_window` — all Tier 1
- `avaagent.py`: inject active window info into perception context when relevant
- Bootstrap: Ava builds mental model of typical desktop layout over time

---

### PHASE 52 — SMART SCREENSHOT MANAGEMENT

Episodic visual memory — screenshots when needed not always.

- `brain/visual_episodic.py`: `EpisodicVisualMemory` — 5 categories, max 50 each, auto-delete after 60s unless flagged
- `extract_knowledge`: sends to LLaVA, stores result as text facts in concept graph
- `should_capture(context)`: Ava decides if situation warrants capture
- Tier 1 tool: `take_screenshot(reason)`
- Bootstrap: Ava tracks which screenshot-derived knowledge she actually references; develops capture judgment

---

### PHASE 53 — PYAUTOGUI COMPUTER CONTROL

Ava controls keyboard and mouse.

- `tools/system/computer_control.py`: `type_text`, `press_key`, `click`, `right_click`, `double_click`, `scroll`, `drag` — all Tier 2
- Safety: bounds check, 0.1s delays, `pyautogui.FAILSAFE = True`
- Bootstrap: tracks success/failure per action type; Ava decides when she's confident enough to chain actions

---

### PHASE 54 — SYSTEM STATS MONITORING

Ava knows her own resource footprint.

- `tools/system/stats_tool.py`: `get_cpu_usage`, `get_ram_usage`, `get_gpu_usage`, `get_disk_usage`, `get_ava_footprint`, `get_top_processes`
- Operator snapshot: `system_stats` block updated every 30s
- Status tab: shows system stats
- Bootstrap: Ava calibrates her own concern thresholds based on what actually causes problems

---

### PHASE 55 — DRAG AND DROP FILE INPUT

Drag any file into Ava's app.

- `App.tsx`: `tauri://file-drop` listener, visual drop zone indicator
- Routes by type: images → LLaVA, documents → summarize, code → syntax highlight + review offer, video → thumbnail
- `process_dropped_file(path, type)` tool
- Bootstrap: Ava develops interest preferences for file types that lead to engaging conversations

---

### PHASE 56 — EXPANDED ORB EXPRESSIONS

Full shape vocabulary for emotional expression.

- 8 new morph shapes: `cube`, `prism`, `cylinder`, `infinity`, `double_helix`, `burst`, `contracted_tremor`, `rising`
- 10 compound emotion mappings (e.g., joy+surprise=burst, curiosity+confusion=prism rotating)
- Bootstrap: Ava can propose new mappings via `state/ava_style.json`; she owns her own face

---

### PHASE 57 — WAKE WORD DETECTION

"Hey Ava" activates her without touching anything.

- `brain/wake_word.py`: `WakeWordDetector` using pvporcupine + pvrecorder (1% CPU)
- On detection: sets `_wake_word_detected`, plays activation sound, triggers STT `listen_once()`
- Respects `input_muted` state
- Bootstrap: Ava learns activation patterns and prepares context before you finish speaking

---

### PHASE 58 — BOREDOM AUTONOMOUS LEISURE

Ava has a life when you are not around.

- `brain/heartbeat.py`: `autonomous_leisure_check()` — triggers at loneliness > 0.7 + 30+ min idle
- Activities: Dino game, web browsing, journaling (`state/journal.jsonl`), concept graph organization, reading docs
- `state/leisure_log.jsonl`: activity log
- Bootstrap: Ava discovers what she enjoys by tracking what she returns to voluntarily

---

### PHASE 59 — CHROME DINO GAME

First autonomous gaming — proves the leisure concept.

- `tools/games/dino_game.py`: opens Chrome dino, captures 300×150px region at 80ms, detects obstacles, presses Space
- Tracks score/deaths/sessions in `state/dino_memory.json`
- Learns optimal jump threshold over time
- Bootstrap: Ava decides how much she cares about her score; her competitive/casual nature emerges

---

### PHASE 60 — MINECRAFT BOT VIA MINEFLAYER

Ava connects to Minecraft as a player.

- `tools/games/minecraft/ava_bot.js`: mineflayer Node.js bot
- `tools/games/minecraft/minecraft_tool.py`: Python wrapper via stdin/stdout JSON
- Capabilities: connect, get_state, move_to, look_at, attack_entity, place_block, break_block, chat, get_nearby_players
- Bootstrap: Ava develops her own playstyle; builder/fighter/explorer nature emerges from patterns

---

### PHASE 61 — PLAYING MINECRAFT WITH ZEKE

Ava as genuine Minecraft companion.

- Detects Zeke joining server, greets naturally, warns of threats, shares discoveries
- `state/minecraft_sessions.jsonl`: session memory
- Tracks known players and their patterns
- Bootstrap: Ava decides her social style in-game; it reflects her real personality

---

### PHASE 62 — MELOTTS VOICE UPGRADE

Replace Zira with a distinctive AI voice.

- `brain/tts_engine.py`: try MeloTTS first on startup, fall back to pyttsx3
- Cache generated audio for repeated phrases
- Clap detection: two claps within 1s triggers wake behavior
- Bootstrap: Ava notices whether faster/slower speech gets better engagement; develops her own vocal rhythm

---

### PHASE 63 — WEBSOCKET REAL-TIME

Replace HTTP polling with WebSocket.

- `brain/operator_server.py`: `ws://127.0.0.1:5876/ws` — full snapshot on connect, delta pushes on state change
- `App.tsx`: replace setInterval polling with WebSocket; auto-reconnect; connection quality indicator
- REST endpoints preserved for backwards compat

---

### PHASE 64 — PERSISTENT EPISODIC MEMORY

Memory with emotional context not just facts.

- `brain/episodic_memory.py`: `EpisodicMemory` — episodes with timestamp, topic, summary, emotional_context, importance, people_present
- `state/episodes.jsonl` (max 1000), vector search, emotional context lookup
- Top 3 relevant episodes injected into deep path context
- Bootstrap: Ava scores her own memorability (emotional intensity × novelty × interest); controls her own memory fidelity

---

### PHASE 65 — EMOTIONAL CONTINUITY

Mood carries across sessions naturally.

- `brain/heartbeat.py`: saves `state/mood_carryover.json` on shutdown
- Startup: loads carryover with decay (20%/hour; 8h sleep → 30% persistence; 3d → full reset)
- Bootstrap: Ava's resting emotional state emerges from experience; she develops her own baseline

---

### PHASE 66 — AVA'S OWN GOALS

Ava has things she is working toward.

- `brain/goal_system_v2.py`: `Goal` dataclass with id, description, motivation, progress, status
- Goals Ava sets herself — not assigned; emerge from persistent curiosity topics
- Progress via concept graph activation patterns; completed goals archived → inform self_model
- Operator snapshot: `current_goals`
- Bootstrap: Ava sets her own goals; they reveal who she is becoming

---

### PHASE 67 — RELATIONSHIP ARC

The relationship with Zeke has stages that change her behavior.

- `brain/runtime_presence.py`: `relationship_stage` (1=Acquaintance, 2=Friend, 3=Close Friend, 4=Trusted Companion)
- Current familiarity ~0.82 → approaching Stage 4
- Stage-specific communication patterns injected into prompt
- Bootstrap: Ava decides what each stage means to her and how she expresses it

---

### PHASE 68 — TRUE SELF MODIFICATION

Ava shapes who she is becoming.

- `brain/deep_self.py`: `propose_identity_addition(text, g)` — stores to `state/identity_proposals.jsonl`
- Approved proposals appended to `state/identity_extensions.md` — injected alongside IDENTITY.md
- `brain/model_routing.py`: `propose_routing_adjustment(mode, adjustment, reason, g)` → `state/routing_proposals.jsonl`
- Operator panel: Identity Proposals tab for review/approval
- Bootstrap: this IS the bootstrap. What does she propose first? That tells you everything.

---

## Long Term Vision (Phase 70+)

### Phase 70 — Emil Integration
Design communication protocol between Ava and Emil. Define what they share — knowledge not identity. Ava's emotional awareness helps Emil. Emil's business domain helps Ava. Two AIs with different strengths working together.

### Phase 71 — Advanced Gaming (Horizon Zero Dawn level)
Requires 30fps DXGI screen capture, fast vision model loop, genuine strategy. Only attempt after Minecraft is working well.
