# Ava Agent v2 — Claude Code Instructions

## What this project is

Ava is a local adaptive AI companion running on Python 3.11 and a Tauri desktop app. She has emotions, memory, vision (InsightFace + eye tracking), voice (Kokoro TTS + Whisper STT + openWakeWord + Silero VAD + clap detector), concept graph, signal bus event system, and a self-aware identity layer. Phases 1–100 are complete; the system has since been hardened with InsightFace GPU, neural TTS, voice command routing, app discovery, and a zero-poll Win32 event architecture.

---

## Key rules

- **NEVER edit `ava_core/IDENTITY.md`, `ava_core/SOUL.md`, or `ava_core/USER.md`**
- Always use `py -3.11` for Python commands (not `python`)
- Always run `py_compile` to verify changed files before building
- Development (hot-reload): `start_ava_dev.bat` — Vite HMR, no exe rebuild
- Production build: `cd apps\ava-control && npm run tauri:build`
- Push to GitHub with: `git add -A && git commit -m "..." && git push origin master`
- No Gradio — only port 5876 (operator HTTP). Tauri is the only UI.
- **`protobuf` is pinned to 3.20.x** for MediaPipe compatibility. If anything bumps it, restore: `py -3.11 -m pip install "protobuf>=3.20,<4" --force-reinstall`

---

## Standing Operating Rules

These apply to every work order in this repo without needing to be restated. Grouped into three concerns: **communication** (talking to the user), **real work** (doing the thing, not theatre), **hygiene** (avoiding silent foot-guns).

---

### Group A — Communication & visibility

#### 1. Progress pings via Discord

For any work order with **multiple discrete tasks or steps**, send a Discord DM before starting and after finishing each task:

- Before starting: `▶️ Starting task N of X: <short name>`
- After finishing: `✅ Finished task N of X: <short name>`
- At the very end: `🏁 <summary line>`

Send via:

```powershell
py -3.11 scripts\discord_dm_user.py 600008921008046120 "<message>"
```

When the session is already inside a Discord channel (inbound `<channel source="discord" ...>` is the trigger), the channel's `reply` tool is an acceptable substitute — same destination, no subprocess spawn.

This applies to every multi-step work order, **not just** ones that explicitly request pings. The user is frequently away from the terminal — Discord is their only real-time visibility into progress. Skipping pings is treated as a defect even if the work itself succeeds.

Single-task work orders (one quick fix, one diagnostic check) only need the final `🏁` status.

#### 2. Progress visibility on failure

When something fails or hits a problem mid-task, **ping immediately**. Don't silently struggle with a problem and only surface it at the end.

Format:

- `⚠️ Hit issue: <brief description>. Trying <approach>` — when problem starts.
- `✅ Resolved` or `🔧 Workaround: <description>` — when problem ends.

**Why:** the user is often AFK; silent struggle costs hours when a quick "stuck on X, trying Y" would let them help. A 2-line ping mid-task is far cheaper than 90 minutes of going down a wrong path.

**How to apply:** any time you change strategy because something didn't work the way you expected, that's a ping moment. Tool didn't behave as expected → ping. Build broke → ping. Test didn't reproduce the bug → ping.

---

### Group B — Real work, not theatre

#### 3. Don't reinvent the wheel

Before implementing any new feature, capability, or significant subsystem for Ava, do this research pass **first**:

1. Search whether a working open-source implementation already exists (`web_search`, GitHub search via `web_fetch`).
2. If found, clone or download it. Evaluate code quality, license, and fit for Ava's architecture.
3. Assess fit on this hardware: latency budget, impact on voice loop / vision pipeline / response latency, alignment with existing patterns (dual-brain, tool registry, memory levels, identity-anchored design).
4. **Good match at acceptable speed → integrate** (with attribution in the source). Don't write from scratch what's already been built and tested by others.
5. **Match exists but too slow / heavy / poor fit →** document why, then either optimize the existing implementation for Ava's constraints **or** build new with the existing implementation as reference. Don't re-derive techniques in a vacuum.
6. **No good match →** document the search results so future searches don't repeat the same dead ends.

**Applies to:** new tools, new perception modules, new memory mechanisms, new reasoning patterns, new UI components, new integrations.

**Does NOT apply to:** bug fixes on existing code, doc edits, config changes, one-line patches.

**Failure standard:** if the user can show a well-known open-source implementation existed that would have worked for Ava with reasonable adaptation, and Claude Code wrote new code without considering it, that's a violation of this rule.

#### 4. Verify fixes before claiming them as done

Don't claim a fix works without testing it. Multiple Discord setup attempts declared "should work now" without verifying the bot came online — that's a defect.

**Practice:**

- After every fix, run the smallest possible test that exercises the fixed path.
- For services: confirm the service actually starts and reaches its expected state.
- For configs: confirm the config loads in the **real** loader, not just a syntax check.
- For code: run the relevant unit/integration test or trigger the code path via an injection endpoint.
- Only claim "fixed" when the test passes **and** the original failure mode is reproducibly absent.
- If a fix is theoretical, **say so explicitly**: "I believe this fixes the issue but couldn't verify in this session — needs hardware test by user."

**Why:** "should work now" without verification is a wish, not a fix. The user has to discover the regression on their own time, often AFK, with no diagnostics ready.

#### 5. Workarounds are not fixes

If the requirement was "single command launches X" and the workaround is "manually run two windows," that's **not a completed task**. Don't declare it done. Either:

- Make the single-command requirement actually work, **OR**
- Explicitly acknowledge the workaround as a workaround and propose what's needed to convert it to a real fix.

The user's **original requirement** is the bar, not what was easiest to achieve.

**How to apply:** before declaring a task done, re-read the original requirement. If your delivered solution requires the user to do something the spec said the system should do automatically, you have a workaround, not a fix.

---

### Group C — Hygiene (avoid silent foot-guns)

#### 6. Reference doc freshness

Whenever any consolidation, deletion, or significant restructuring of `docs/` happens (merging files, moving content, renaming docs), the **next action MUST be**:

1. **Audit all remaining reference docs** for paths to the moved/merged/deleted files.
2. **Update those references** to point to the new locations (with section anchors where helpful).
3. **Verify code paths and tool names** are still accurate — refactors invalidate doc paths just as readily.
4. **Commit the doc fixes in the same PR/session** as the consolidation, or immediately after.

**Why:** broken doc references are a defect equivalent to broken code. Stale docs cause Claude Code to follow phantom paths, miss current context, and waste session time recovering. **Stale docs are worse than no docs because they actively mislead.**

**How to apply:** when you finish any task that deletes or moves a `.md` file under `docs/`, immediately grep the rest of `docs/` and `CLAUDE.md` for the old basename. If hits exist, fix them before declaring the consolidation done.

This rule is not optional. It applies to every future consolidation, deletion, or doc restructure.

#### 7. Validate config patches actually load

When patching any config file (JSON, YAML, TOML, `.env`, `.mcp.json`, etc.), don't just write the file — **verify it actually parses and loads**. The Discord plugin BOM trap (commit `c25443f`) was caused by writing a patched `.mcp.json` that looked correct but had a UTF-8 BOM that the loader silently rejected. The plugin disappeared from `/mcp` with no visible error.

**Practice:**

- After writing a patched config, immediately parse it with the relevant parser (`json.loads`, `yaml.safe_load`, etc.) and verify success.
- For configs loaded by external tools, verify the tool actually picks up the patched version.
- **PowerShell trap:** `Set-Content -Encoding utf8` on Windows PowerShell 5.1 writes a UTF-8 BOM. **Never use it for files that other tools will parse.** Use `Out-File -Encoding utf8NoBOM`, write via Python, or use `[System.IO.File]::WriteAllText` (which is BOM-free by default).
- If silent rejection is suspected, write a smoketest that mimics the real loader and prints diagnostics.

#### 8. Check for existing instances before starting services

When starting a service that binds to a port, opens a singleton resource, or otherwise needs exclusive access:

- **Check if an existing instance is already running first** (port probe, PID lockfile, named mutex).
- Don't loop forever trying to start a second instance.
- Either: cleanly join the existing instance, **OR** exit with a clear error message.
- The port 5876 conflict (Ava's operator HTTP) was an example — fixed in commit `6446707` with port probe + PID lockfile + HTTP restart cap.

**How to apply:** any new service-launching code should follow the pattern in `avaagent.py`'s startup probe: socket connect-ex on the target port, PID file at `state/<service>.pid`, hard exit if either says "another instance is alive."

#### 9. Token and credential hygiene

Sensitive credentials (bot tokens, API keys, passwords, SSH keys, OAuth secrets) **must never:**

- Be echoed in chat output.
- Be written into commit messages.
- Appear in debug logs that get shared.
- Be pasted into transcript files visible to other sessions.

**Practice:**

- When handling tokens, mask them in any output (show first 6 chars + `…`).
- If asked to read a credential file, don't print its contents — print a masked confirmation.
- When writing tokens to `.env` files, write them silently and confirm with a masked summary.
- Treat all tokens like SSH keys.

#### 10. File consolidation — keep the repo navigable

When adding new code, prefer **adding to an existing related file** over creating a new small file. Many small files scattered across `brain/`, `tools/`, or `scripts/` make the repo harder to navigate, harder to grep, and harder to keep mental models of.

**Practice:**

- If new functionality is a few helper functions related to an existing module's purpose, add to that module — don't spin up `brain/foo_helpers.py` next to `brain/foo.py`.
- If a new file would be <100 lines and doesn't introduce a clean separation of concerns, fold it in.
- Counter-pressure: when consolidation produces complexity explosion (file >2000 lines, mixing fundamentally different concerns, circular imports), then split. The rule is "consolidate when reasonable," not "everything in one file."

**How to apply:** before creating a new file, ask "is there already a file whose purpose would naturally include this?" If yes, add there. If no, create with a clear single-purpose name.

#### 11. Desktop app paths — check before cu_open_app falls through

Most Steam apps and ML tools on this machine live at `C:\Users\Tzeke\OneDrive\Desktop`. OBS is there. Several other slow-launching apps are there. Standard `cu_open_app` strategies (PowerShell `Start-Process`, Win-search, Program Files walk) miss these.

**Practice:**

- When `cu_open_app` adds new search locations, include `C:\Users\Tzeke\OneDrive\Desktop` (and follow `.lnk` shortcuts there) in the direct-path strategy.
- When debugging "Ava can't find this app," check Desktop before assuming the app is missing.

**Caution:** Ava's own launch script (`start_ava.bat` / `start_ava_dev.bat`) lives nearby. The single-instance check in `avaagent.py` will reject a second launch, but **explicitly skip Ava's own launchers when scanning for apps to open** — don't accidentally trigger "open Ava" via cu_open_app and bounce off the single-instance lockout.

**How to apply:** any change to `brain/windows_use/retry_cascade.py` direct-path locations or to `brain/app_discoverer.py` scan roots should add the Desktop path and exclude Ava's launch scripts by name.

#### 12. ROADMAP + HISTORY discipline — keep docs in sync with reality

Every work order completion **must update both** `docs/ROADMAP.md` and `docs/HISTORY.md` before declaring the task done.

**ROADMAP.md** — mark items completed, add new findings discovered during the work, update or remove items whose framing turned out to be wrong.

**HISTORY.md** — add a phase entry summarizing this session's work: what landed, what was diagnosed, what's deferred. The phase entry is the future-self's way of knowing what was tried in this session without having to re-read commit logs.

**Why:** stale ROADMAP entries cause re-doing already-completed work. Stale HISTORY entries make sessions waste time re-discovering known dead ends. The 2026-05-04 dual-brain ROADMAP entry being three commits behind the actual code state was an example — the entry described `ava-gemma4` as the current default when `ava-personal:latest` had already been wired in. Cost a session of "fix the model preference" when the real blocker was elsewhere.

**How to apply:** before a session ends or a commit is made for a multi-task work order, grep the work-order touched files against ROADMAP/HISTORY and update entries that describe the now-changed state. Leave a note in the commit message if the doc updates are part of the commit.

---

**Rule application scope:** these rules apply to every Claude Code session in this repo, automatically, without needing to be quoted in individual prompts. They are part of the operating context.

---

## Key paths

| Path | Role |
|---|---|
| `avaagent.py` | Main agent runtime |
| `brain/` | All Python subsystems |
| `brain/startup.py` | Subsystem bootstrap (background daemon threads) |
| `brain/reply_engine.py` | `run_ava` — main turn pipeline + simple-question fast path |
| `brain/voice_loop.py` | passive / attentive / listening / thinking / speaking |
| `brain/voice_commands.py` | 40 built-in voice commands + custom |
| `brain/signal_bus.py` | Lightweight event bus (clipboard, window, faces, etc) |
| `brain/wake_word.py` | openWakeWord + Whisper-poll fallback |
| `brain/clap_detector.py` | Double-clap wake (floor 0.35) |
| `brain/tts_worker.py` | Kokoro neural TTS, OutputStream protected |
| `brain/stt_engine.py` | Whisper base + Silero VAD + Eva→Ava normalization |
| `brain/insight_face_engine.py` | InsightFace GPU buffalo_l |
| `brain/expression_calibrator.py` | Per-person expression baseline |
| `brain/app_discoverer.py` | Desktop / Start Menu / Steam / Epic scan |
| `apps/ava-control/src/` | Tauri React app source |
| `apps/ava-control/src/App.tsx` | Main UI (1900+ lines) |
| `apps/ava-control/src/components/OrbCanvas.tsx` | Three.js orb |
| `apps/ava-control/src/WidgetApp.tsx` | Floating widget |
| `state/` | All persisted state |
| `tools/` | Tier-1/2/3 tool registry |
| `docs/HISTORY.md` | Project history — phases 1-100 + post-100 + stabilization arcs + cross-phase bug fixes |
| `docs/ROADMAP.md` | Forward-looking roadmap (5 sections: Ready to ship → Long-term) |
| `docs/CONVERSATIONAL_DESIGN.md` | Voice naturalness architecture — streaming chunks, tier system, interrupt model |
| `docs/TRAIN_WAKE_WORD.md` | Custom hey_ava ONNX training |
| `models/wake_words/` | Optional custom wake-word ONNX models |

---

## Current model setup

| Role | Model |
|---|---|
| Social chat (foreground) | `ava-personal:latest` (fine-tuned) |
| Background stream B | `qwen2.5:14b` / `kimi-k2.6:cloud` (when online) |
| Deep reasoning | `qwen2.5:14b` |
| Maintenance / evaluation | `mistral:7b` |
| Embeddings | `nomic-embed-text` |
| Cloud fallbacks | `kimi-k2.6:cloud`, `qwen3.5:cloud`, `glm-5.1:cloud`, `minimax-m2.7:cloud` |
| Vision | InsightFace `buffalo_l` (GPU) |
| TTS | Kokoro `hexgrad/Kokoro-82M` (28 voices) |
| STT | `WhisperModel("base")` cuda+float16 (CPU int8 fallback) |
| Wake word | openWakeWord `hey_jarvis` (proxy) — `hey_ava.onnx` slot reserved |
| VAD | Silero VAD |

---

## Voice pipeline notes

```
clap / openWakeWord  →  Silero VAD  →  Whisper base  →  Eva→Ava normalize  →
  voice_command_router (40 builtins)  →  run_ava  →  Kokoro TTS  →  attentive 60s
```

**Wake sources:**
- `_wake_source = "clap"` → set by clap detector → `wake_detector` short-circuits to `(True, 1.0)`
- `_wake_source = "openwakeword"` → set by openWakeWord callback → same short-circuit
- Whisper-poll fallback (only if openWakeWord can't load) — runs full classification

**TTS protection:**
- `tts_worker` runs at `THREAD_PRIORITY_HIGHEST`
- Playback uses `sd.OutputStream` chunked at 2048 samples
- Mid-stream abort ONLY on `g["_tts_muted"]=True` (explicit user mute) or worker shutdown
- Window focus / mouse / other apps grabbing audio → ignored

**Custom commands / tabs:**
- `state/custom_commands.json` — Ava-built voice triggers (hot-reload on file change)
- `state/custom_tabs.json` — Ava-built UI tabs (web_embed / journal / stats / images)
- Both bootstrap-friendly: empty by default; populated as Ava decides what's useful

---

## InsightFace CUDA setup

ORT 1.25.1 needs CUDA 12 runtime libs from these pip packages:
```
nvidia-cublas-cu12, nvidia-cudnn-cu12, nvidia-cuda-runtime-cu12,
nvidia-cuda-nvrtc-cu12, nvidia-cufft-cu12, nvidia-curand-cu12,
nvidia-cusolver-cu12, nvidia-cusparse-cu12, nvidia-nvjitlink-cu12
```

`brain/insight_face_engine._add_cuda_paths()` registers each `site-packages/nvidia/*/bin/` with `os.add_dll_directory` BEFORE the ORT import. Verified: all 5 buffalo_l ONNX sessions report `Applied providers: ['CUDAExecutionProvider', 'CPUExecutionProvider']` on RTX 5060 (~41ms/frame steady-state).

First-run cudnn EXHAUSTIVE algorithm search takes 60–90s; cached afterward.

---

## Kokoro voice info

- 28 voices total — verified all loadable
- Default: `af_heart` (warm)
- Per-emotion mapping in `tts_worker._emotion_to_kokoro`:
  - `af_bella` for high-intensity expressive (excitement, anger, surprise, awe, love, joy)
  - `af_nicole` for soft / sad / shame / loneliness
  - `af_sky` for bright (joy, happiness, excitement, love, hope)
- Speed 0.7–1.3 scaled toward neutral by intensity
- Models cached at `~/.cache/huggingface/hub/`

---

## openWakeWord models location

- Bundled (auto-downloaded via `openwakeword.utils.download_models()`):
  - `alexa_v0.1.onnx`
  - `hey_jarvis_v0.1.onnx` ← **currently used as `hey_ava` proxy**
  - `hey_mycroft_v0.1.onnx`
  - `hey_rhasspy_v0.1.onnx`
  - `timer_v0.1.onnx`
  - `weather_v0.1.onnx`
- Custom (optional): `models/wake_words/hey_ava.onnx` — auto-loaded if present
- Training pipeline requires WSL2 — see `docs/TRAIN_WAKE_WORD.md`

**Phonetic benchmark on synthetic Kokoro "hey ava" samples (2026-04-29):**
- `hey_jarvis` peaks 0.917 on af_bella → viable proxy
- `hey_mycroft` peaks 0.000 → not viable
- `hey_rhasspy` peaks 0.019 → not viable

---

## Python packages — installation

Always use `py -3.11 -m pip install <name>` (no `--break-system-packages` needed on the user-installed Python 3.11).

Don't use `&&` in PowerShell — chain with `;` or use separate commands.

---

## Common issues and fixes

| Symptom | Fix |
|---|---|
| `mediapipe` errors with `MessageFactory` | `protobuf` got bumped — restore: `pip install "protobuf>=3.20,<4" --force-reinstall` |
| InsightFace runs on CPU not GPU | Verify `nvidia-*-cu12` packages installed; check `_add_cuda_paths` log line at startup |
| `cufft64_11.dll missing` | Install `nvidia-cufft-cu12` |
| Kokoro fails to init | Check internet on first run (downloads ~360MB), or fall back to pyttsx3 (auto) |
| Tauri build fails with `os error 5` | Stale `ava-control.exe` is locked — kill it before rebuild |
| Wake word fires too often | Raise `_DEFAULT_THRESHOLD` in `brain/wake_word.py` from 0.5 → 0.6 |
| Wake word never fires | Check clap detector floor (`brain/clap_detector.py:_MIN_THRESHOLD_FLOOR=0.35`); use clap as fallback wake |
| TTS interrupts mid-sentence | Should not happen post-`a740bcc`. If it does, check `tts_worker.stop()` logs for "ignoring (audio protected)" |
| `concept_graph.json.tmp` stuck | Auto-cleared at startup; if it persists, manually delete `state/concept_graph.json.tmp` |

---

## Design philosophy

- Sci-fi dark aesthetic throughout
- Three.js energy orb is the core UI element
- All 27 emotions have color + shape morphs
- Brain tab shows live 3D concept graph (3d-force-graph) — drag to rotate, right-drag to pan, scroll to zoom
- **Bootstrap-friendly:** Ava's preferences, wake patterns, expression baselines, custom commands, and curiosity topics emerge from her interactions with Zeke — never seeded with defaults

---

## Hot-reload dev mode

```bash
start_ava_dev.bat
```

Starts `avaagent.py` (operator HTTP at 5876) + watchdog + Vite HMR for frontend. Editing any `.tsx`/`.ts`/`.css` file refreshes instantly. Only Rust/`tauri.conf.json` changes need a full `tauri:build`.

---

## Push workflow

```bash
git add -A
git commit -m "feat: <what changed>"
git push origin master
```

The user reviews the diff in GitHub before merging. PRs are not needed for this repo.

For multi-line commit messages use a HEREDOC:
```bash
git commit -m "$(cat <<'EOF'
title line

body
EOF
)"
```
