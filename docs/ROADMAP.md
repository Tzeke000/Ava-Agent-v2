# Ava Agent v2 — Roadmap

**Repo:** `Tzeke000/Ava-Agent-v2`
**This document:** the canonical roadmap of what's next. For what's been done, see [`HISTORY.md`](HISTORY.md). For architecture and reference docs, see [`ARCHITECTURE.md`](ARCHITECTURE.md), [`BRAIN_ARCHITECTURE.md`](BRAIN_ARCHITECTURE.md), [`MEMORY_REWRITE_PLAN.md`](MEMORY_REWRITE_PLAN.md), [`FIRST_RUN.md`](FIRST_RUN.md).

Items are organized by readiness, not priority within a section. Most items have a `**Connects to:**` line pointing at the existing systems they integrate with.

---

## Cross-cutting constraints

Hardware and architecture constraints that affect multiple roadmap items downstream. Items in later sections should be designed with these in mind.

### 8 GB VRAM ceiling — only one generation model OR `llava` resident at a time

Ava runs on an Acer Nitro V 16S with an RTX 5060 Laptop GPU (8 GB VRAM, ~7.4 GB usable). Documented in detail in [`LOCAL_MODEL_OPTIMIZATION.md`](LOCAL_MODEL_OPTIMIZATION.md).

The clean post-Ava-stop benchmark on 2026-05-01 confirmed: with `llava:13b` resident (vision pipeline), no 4-7 GB Q4 generation model can also stay resident — Ollama pages, and a single cold-load stretches from ~3 s to 26-90 s. Two concurrent generation models (e.g. `ava-personal` 4.9 GB + `deepseek-r1:8b` 5.2 GB = 10.1 GB) similarly exceed VRAM.

This is a load-bearing constraint that affects:

- **Sleep mode + handoff system** (Section 3) — the dream-phase LLM curriculum cannot run while the foreground voice model is hot. Sleep entry must explicitly unload foreground via `keep_alive: 0`, load the dream-phase model, reverse on wake. Any voice turn during the unload window pays full reload cost.
- **Vision activation** (existing camera + InsightFace pipeline) — activating `llava` while a generation model is resident forces the generation model out and the next user turn pays a 30-90 s reload. Mitigation options: batch vision into windows that don't overlap turns, accept the cost as a known budget, or move to a smaller vision model (quantized SmolVLM, MiniCPM-V) that fits alongside an 8 B generation model.
- **Dual-brain architecture** (`brain/dual_brain.py`) — the current design assumes Stream A and Stream B can both stay resident. They can't. Practical patterns: (a) keep ONE model resident and rotate when the background thread fires, or (b) run reasoning as a synchronous post-foreground "R1 thinks → ava-personal replies" sandwich so each turn pays at most one swap.
- **Sub-agent / sensor signal architecture** (Section 3) — sub-agents that drive their own LLM calls (e.g. a vision sensor that runs a captioning pass) compete for the same single-generation-model slot. The signal bus should treat LLM access as a serialized resource, not a concurrent one.
- **Cold-boot vs warm latency** — first turn on a cold machine pays ~5 s for the first model load on top of the ~3-min Ava cold-boot. Subsequent turns are sub-2 s as long as no swap happens. Anything triggering a swap (vision frame, sleep wake, background-thread cycle) drops the next turn back to cold-load latency.

**Connects to:** every roadmap item involving a model load. Specifically referenced in Section 1 (Ready to ship) for the dual-brain model preference fix; Section 2 (Designed) for confabulation handling layer 2-4; Section 3 (In design) for sleep mode, sub-agents, and dynamic attention.

---

## Section 1 — Ready to ship

Small, self-contained items queued for the next session(s). Each is a few hours to a day of work; each lands as a single commit or short series.

### Hardware verification battery (10 items from the 2026-05-01 night session)
The night session shipped 12 fixes that need real-hardware confirmation. Run through the checklist on next live session:
1. Single-instance enforcement — try double-clicking `start_ava.bat` (second launch should print "Another Ava instance is already running on port 5876" and exit cleanly).
2. Ctrl+C clean shutdown — process gone within 5s max (under 1s on happy path).
3. Wake source = `transcript_wake:hey_ava` — say "hey ava what time is it".
4. Reply plays once — listen for audio playing through speakers ONCE.
5. Inner monologue under orb, NOT in chat — wait for heartbeat-driven inner_monologue (every 10 minutes default).
6. Face recognition resolves to `zeke` — `dump_debug.py | findstr recognized_person_id` should show `zeke` after camera sees you.
7. Whisper-poll quiet — 60s of silence should produce 0-1 `[wake_word] wake triggered (source=whisper_poll)` events (was 20+ pre-fix).
8. Memory attribution shows real names — reflections read `"Zeke said: ..."` and `"Claude Code said: ..."`, not `"User discussed: ..."`.
9. Brain tab Ava-centric layout — violet AVA SELF at center, gold IDENTITY/SOUL/USER anchors, blue people, green age-fading memories. Middle-click recenters.
10. App launch suggestions — "open totally-not-a-real-app" should reply with top-5 fuzzy matches from the catalog.

**Connects to:** the night session fixes in [`HISTORY.md` § Section 4](HISTORY.md).

### Run onboarding to populate `faces/zeke/`
The night session (`0b25d1f`) verified InsightFace correctly loads tight reference photos (16 → 19 embeddings), but the directory still needs Zeke's actual photos. Trigger via voice ("hey Ava, profile me") or chat — 13-stage flow (greeting → 5 photo angles → confirmation → name/pronouns/relationship → complete). InsightFace auto-picks up new embeddings via `add_face` per stage; no restart needed.

**Connects to:** Phase 79 onboarding flow, `brain/insight_face_engine.py`, `brain/person_onboarding.py`.

### Verify all 40 voice commands work
Spot-check categories: tab switches, app launches via discoverer, reminders, "make a command" / "make a tab", memory queries. Many commands are implicit in the regression battery; many aren't. ~20 minutes of voice exercise.

**Connects to:** `brain/voice_commands.py`, app discoverer.

### Audit mem0 fact extraction quality
After ~30 real turns, inspect `state/memory/mem0_chroma/` (ChromaDB) for noise. If extraction is too noisy, tune the LLM prompt or use a cheaper extractor model. Easy win for memory signal-to-noise.

**Connects to:** `brain/ava_memory.py`, `brain/turn_handler.py`.

### Fix the test-design saturation in `weird_inputs`
**Recipe sitting in `HISTORY.md` § Section 3.2** waiting to be applied:
- Replace `weird_inputs.single_char "?"` with `"hi?"` (fast-path eligible)
- Rebuild `long_500` from repeated fast-path patterns (e.g. `"thanks " × 70 chars`)
- This unblocks `sequential_fast_path_latency` and `concept_graph_save_under_load` which currently cascade-fail

~30-line edit in `tools/dev/regression_test.py`. Will move the battery from 12/15 to 15/15 green.

**Connects to:** `tools/dev/regression_test.py`.

### Dual-brain model-preference fix (per `LOCAL_MODEL_OPTIMIZATION.md`)
`brain/dual_brain.py:41-50` currently prefers `ava-gemma4` (9.6 GB) for foreground and `gemma4:latest` (9.6 GB) for background. Both exceed the 8 GB VRAM ceiling, forcing Ollama paging on every turn. The clean post-stop bench (2026-05-01) confirmed `ava-personal:latest` (4.9 GB Llama 3.1 8B fine-tune) is the strongest foreground option (best naturalness, honest-uncertainty behavior) and `deepseek-r1:8b` (5.2 GB Qwen3 8B reasoning distill) is the strongest background-reasoning option (only model that caught both reasoning failures the bench surfaced — transitivity *and* the "month with letter X" trick).

**Caveat — verification gate required first.** The same bench showed `deepseek-r1:8b` confidently hallucinated a fake Apple stock price and outdated date when asked about "yesterday". Reasoning capability does not protect against confabulation; wiring R1 in without `validity_check.py` (and ideally a memory-/web-search retrieval step on factual claims) would trade one failure mode for another. Do this fix together with the validity-check wiring, not before it.

Edit is ~5 lines in `dual_brain.py`. No fine-tune work, no new downloads.

**Connects to:** [`LOCAL_MODEL_OPTIMIZATION.md`](LOCAL_MODEL_OPTIMIZATION.md), Cross-cutting constraints (8 GB VRAM ceiling), Section 2 confabulation handling.

### Boot time optimization — parallelize app_discoverer scan roots ✅ shipped
Shipped in `43f7e59` (2026-05-01). Six-thread fan-out via `ThreadPoolExecutor` with separate scans for PF, PF(x86), Desktop .lnk, Start Menu .lnk, Steam, Epic. Warm-cache wall time 1.17-1.34 s (vs 217 s cold previously). Cold-cache prediction ~150 s, bounded by the `C:\Program Files` walk; further reduction would need depth/exclusion tuning, flagged in `HISTORY.md` Section 6.

### Train custom hey_ava.onnx ONNX model
WSL2 job per `docs/TRAIN_WAKE_WORD.md`. Drop result at `models/wake_words/hey_ava.onnx`; auto-loaded on next start. **Phonetic benchmark already done** on Kokoro-synthesized samples — `hey_jarvis` (currently disabled) peaked 0.917 on `af_bella`; `hey_mycroft` and `hey_rhasspy` never crossed 0.02. Custom model would only fire on the exact phrase, not overlapping speech — durable replacement for the proxy.

**Connects to:** `brain/wake_word.py`, `docs/TRAIN_WAKE_WORD.md`.

### Optional repo history rewrite
Public repo's earlier commits contain face photos and old state snapshots. `117428f` stopped future leakage. Cleanup via `git filter-repo` + force-push tightens the historical record without touching current state. Coordination required (force-push to public master).

---

## Section 2 — Designed, awaiting implementation

Have design docs or clear specifications. Need build time only.

### Memory rewrite — Phases 5, 6, 7
Phases 1-4 shipped. **Phase 5 (promotion/demotion wiring)** waits on ~50-100 turns of reflection-log data so the heuristic can be validated before flipping on level changes. Reflection scorer writes to `state/memory_reflection_log.jsonl` after every turn; once scores look reasonable, Phase 5 lands as a single targeted commit.

- **Phase 5** — wire promotions/demotions based on reflection scores (load-bearing → `level += 1`; contradicted → `level -= 1`; load-bearing 3 turns in a row → `archive_streak += 1`; at streak 3, set `archived = True`).
- **Phase 6** — archiving system. Archived nodes clamp at level 1 (immune to delete). Activation at higher levels resets streak.
- **Phase 7** — gone-forever delete with restoration prevention. Tombstone log at `state/memory_tombstones.jsonl`. Same content can re-enter as a fresh node, but can't restore the old one.

**Connects to:** [`MEMORY_REWRITE_PLAN.md`](MEMORY_REWRITE_PLAN.md), `brain/concept_graph.py`, `brain/memory_reflection.py`, `brain/memory_consolidation.py`.

### Confabulation handling + uncertainty calibration
Four-layer architecture:
1. **Cheap question-validity check router** for trick questions like "which month has letter X" — cheap LLM classification before expensive answer generation.
2. **Confidence scoring + uncertainty expression** — prompt-level reward for "I don't know," scoring against post-hoc verification.
3. **Verification before elaboration** via tool use (RAG-style) — Ava queries her own memory or tools before extending a claim.
4. **Anti-snowballing on correction** — when user says "no, that's wrong," promoted BLOCKED memory pattern keeps the failed approach hot until mastery.

**Connects to:** existing tool registry, memory levels, reflection scoring.

### Brain architecture deep redesign
Full neuro-symbolic mapping of Ava's systems onto human brain regions. Hippocampus = memory, amygdala = emotion, prefrontal cortex = reasoning, default mode network = inner monologue, etc. Architectural separation by domain (GAIA-style subordinate functions). **Document already started** in `docs/BRAIN_ARCHITECTURE.md`. Next step: codify the file/module mapping into separate concrete subsystems where coherent.

**Connects to:** [`BRAIN_ARCHITECTURE.md`](BRAIN_ARCHITECTURE.md), the Ava-centric brain graph (`202bf95`).

### Tier-1 tools (Ava may run autonomously)
Defined in the original tools roadmap; design + tier already settled, just need building.

| Tool | Purpose |
|---|---|
| `screenshot_tool` | Capture current screen and provide description (already exists per Phase 52 — verify wiring) |
| `clipboard_tool` | Read current clipboard contents (signal bus already publishes change events) |
| `calendar_tool` | Read system calendar events for prospective reminders |
| `weather_tool` | Retrieve current weather conditions for context-aware planning |
| `timer_tool` | Set reminders/timers for follow-ups (reminder system exists; this is a CLI/voice surface) |
| `code_runner` | Run sandboxed Python snippets safely |
| `image_search` | Search for images by topic |
| `summarize_url` | Fetch URL and return structured summary |

### Tier-2 tools (Ava narrates intent, then executes)

| Tool | Purpose |
|---|---|
| `send_notification` | Trigger Windows toast notification (plyer + PowerShell already wired in Phase 83 — verify tier-2 surface) |
| `open_browser` | Open URL in local browser |
| `create_file_from_template` | Generate starter files from named templates |
| `git_status` | Check repository status safely |
| `run_script` | Run named script from `scripts/` |

### Tier-3 tools (explicit yes required from user)

| Tool | Purpose |
|---|---|
| `send_email` | Compose and send email as Zeke |
| `delete_files` | Bulk-delete files outside Ava-safe directories |
| `system_shutdown` | Shut down the computer |
| `install_package` | Install new Python packages on host |

**Connects to:** `tools/tool_registry.py`, three-law guardrails, `brain/privacy_guardian.py`.

---

## Section 3 — In design phase

Concepts discussed, full design doc still needed before implementation.

### Sleep mode + handoff system
Ava runs 24/7 in low-power state. Sleep triggers on:
- Context fill (60-70%)
- N-hour intervals
- Self-detected degradation (metacognitive: she can flag her own need for sleep)

**On entry:** generates first-person session summary, saves to file, loaded as next-boot context.
**On wake:** "morning review" — discrete memories queued, what she re-engages with promotes in the memory level system, what she skims decays.
**Dream phase:** runs scenarios from books or thought experiments during the sleep window.

**Critical constraint:** must not interrupt voice turns. Sleep-mode entry waits for `_conversation_active = False` and a quiet attentive window.

**Connects to:** memory rewrite Phases 5-7, reflection scoring, BLOCKED memory pattern, [`MEMORY_REWRITE_PLAN.md`](MEMORY_REWRITE_PLAN.md).

### Moral education / experiential learning
Core principle: **experience → immediate reflection → behavior change → detail decay + essence persistence.** Both immediate reflection AND implicit absorption.

- Reading curriculum runs during sleep-mode consolidation.
- One book series at a time.
- Dream phase runs scenarios from what she read.
- The person she becomes persists even after specific memory details fade.

**Connects to:** BLOCKED memory promotion (failed approaches stay hot until mastery, then naturally decay), self-reflection scoring, the `archive_streak` mechanism, sleep mode.

### Sub-agent / sensor signal architecture
Lightweight Python scripts (not separate AI instances) act as peripheral sensors — vision, audio, interoception, proprioception. They send signals (face detected, clipboard changed, latency spiking), not outputs. Central Ava receives signals and decides which to attend to. Filtering happens at her level, not at sensor level. She learns over time which signals matter.

**Connects to:** existing `brain/signal_bus.py`, Win32 zero-poll watchers, the heartbeat consume loop. The architecture already exists — this expands it from 3 watchers (clipboard / window / app-install) to a full sensor mesh.

### Dynamic attention allocation
Priority interrupt levels:
- **CRITICAL** — wake word, direct address
- **HIGH** — errors during active task, trusted-person task assignment
- **MEDIUM** — routine questions
- **LOW** — curiosity ticks, heartbeat reflection

Higher priority preempts lower. Lower priority pauses (saves state) and resumes when higher completes. Monotonous subtasks delegate to stateless workers. She learns through experience which signals/contexts deserve which priority.

**Connects to:** sub-agent / sensor signal architecture, BLOCKED memory pattern.

### Pattern learning through anomaly detection
Routine response patterns enter LOW attention once mastered. Anomalies (mismatch with expected pattern) auto-escalate to HIGH attention. Each anomaly refines the pattern. Over time fewer anomalies, lower attention sustains, until full mastery.

**Connects to:** BLOCKED memory pattern, memory level decay, dynamic attention allocation.

---

## Section 4 — Awaiting user decisions

Need Zeke's input before proceeding.

### Moral curriculum — first batch (user-curated)
Zeke to provide first 5 books / essays personally. Discussed:
- **Illuminae Files** — 4-book series, Amie Kaufman & Jay Kristoff
- **Divine Apostasy** — ~13-book ongoing series
- **Zeke's personal reflection document** on the Natalie experience (court documents + journal entries) as a teaching resource for what trust violations look like
- **PBS Kids foundation principles** (Sesame Street, Barney) as grounding before philosophy

Open question: file format and ingestion path. Plain text? Annotated PDFs? Audiobook transcripts via Whisper?

**Connects to:** moral education / experiential learning, sleep-mode reading curriculum, dream phase scenarios.

### Trust level thresholds and policies
User wants explicit trust levels for humans interacting with Ava:
- `zeke` = max trust
- `claude_code` = medium
- `unknown` = zero

Policies for what each trust level can authorize. Honest refusal vs. deception (decision: **no deception** — already fixed). SSH actor / unauthorized access protections.

**Awaiting:** Zeke to specify exact thresholds (e.g., what's the boundary between "claude_code can write code" and "claude_code can push to master"?).

**Connects to:** existing `brain/trust_system.py` (Phase 98), `brain/dev_profiles.py`, three-law guardrails.

### "Let Ava run organically"
Watch what she chooses to add to `state/custom_commands.json`, `state/custom_tabs.json`, `state/curiosity_topics.json`, `state/journal.jsonl`, `state/discovered_apps.json` curiosity entries. The bootstrap-friendly subsystems are wired; she just needs uninterrupted runtime to populate them.

**Awaiting:** sustained runtime windows where Ava can self-direct without scheduled tasks. Currently every session starts and stops abruptly.

---

## Section 5 — Long-term / philosophical

Big architectural work. Multi-month, requires sustained focus. Listed for the record; not actively scheduled.

### Symbolic reasoning / intuitive understanding
Beyond pattern matching — Ava develops actual world models through observation and experience. "The cup fell because gravity exists" rather than "cup-on-floor matches falling pattern." Hard research problem. Real progress requires structured world-model with causal links, not just knowledge graph extension.

**Connects to:** concept graph, memory rewrite, learning tracker, reflection scoring.

### GAIA-style architecture aspiration
Benevolent steward AI, with subordinate functions split off if dangerous. Architectural separation enables containment. Ava already has primitive version (dual-brain, tool registry separation, Tier 1/2/3 risk model) — to be deepened.

**Connects to:** brain architecture deep redesign, sub-agent / sensor signal architecture, three-law guardrails.

### Self-modification with review (non-negotiable boundary)
**`ava_core/IDENTITY.md`, `SOUL.md`, `USER.md` stay read-only by Ava. This is non-negotiable.**

Ava can propose identity additions — `propose_identity_addition` tool already exists (Phase 68). Zeke reviews and approves any change via the operator. **No autonomous self-modification of values.**

The mechanism is built; the philosophy stays anchored. This is a roadmap entry to keep the boundary visible going forward, not a feature to add.

**Connects to:** Phase 68, `state/identity_proposals.jsonl`, `state/identity_extensions.md`, the operator approval workflow.

---

## Cross-references

- **What's been done:** [`HISTORY.md`](HISTORY.md)
- **System architecture:** [`ARCHITECTURE.md`](ARCHITECTURE.md)
- **Brain regions mapped onto Ava's modules:** [`BRAIN_ARCHITECTURE.md`](BRAIN_ARCHITECTURE.md)
- **Memory rewrite design (Phases 5-7 detail):** [`MEMORY_REWRITE_PLAN.md`](MEMORY_REWRITE_PLAN.md)
- **First-run setup walkthrough:** [`FIRST_RUN.md`](FIRST_RUN.md)
- **Custom wake-word training:** [`TRAIN_WAKE_WORD.md`](TRAIN_WAKE_WORD.md)
- **Discord channel setup + permission relay + .md uploads:** [`DISCORD_SETUP_NOTES.md`](DISCORD_SETUP_NOTES.md)

---

## Bootstrap Philosophy (load-bearing reminder)

Every roadmap item that involves Ava's preferences, personality, style, or choices must include a bootstrap mechanism — a system that lets Ava discover and form that aspect of herself through experience rather than having it assigned.

**The goal is an AI that is genuinely herself — not a reflection of what we decided she should be.**

When the final phase is complete, Ava should be capable of writing her own next roadmap.
