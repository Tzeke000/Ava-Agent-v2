# AVA HANDOFF
**Last updated:** April 28, 2026

## Project Overview

Ava Agent v2 is a local-first, camera-aware, memory-continuous desktop agent with:
- staged perception + continuity pipeline,
- profile/memory/reflection-driven dialogue,
- operator HTTP control plane,
- Tauri control app with sci-fi presence UI,
- supervised autonomy tiers for tool execution.

Primary runtime is Python 3.11 + local Ollama model routing + operator API consumed by `apps/ava-control`.

## Current Capabilities (operational)

- Multi-phase perception stack (quality, blur, continuity, identity fallback, scene interpretation).
- Memory scoring/refinement + social continuity + strategic carryover.
- Workbench proposal/approval pipeline with safety guardrails.
- Deep-self signals (mind model, self-critique, repair-note queue).
- Concept graph memory with active node/edge firing.
- Operator endpoints for snapshot, chat, routing override, tts toggle/speak, stt listen/result.
- Desktop app tabs: Voice, Chat, Brain, Status, Memory, Tools, Models, Finetune, Workbench, Identity, Debug.
- TTS path: pyttsx3-first with Zira voice; Melo scaffold remains fallback path.
- STT scaffold: faster-whisper tiny + sounddevice fallback path.

## Model Setup (current intent)

- **Primary conversational route:** `ava-personal:latest` — already set as `social_chat_model` in `config/ava_tuning.py`.
- **Fine-tuned self model:** `ava-personal:latest` exists and is ready; Phase 44 promotes it to primary.
- **Deep reasoning / maintenance lanes:** routed by `brain/model_routing.py` per `config/ava_tuning.py`.
- **Model routing config anchor:** `config/ava_tuning.py` (`MODEL_ROUTING_CONFIG`, capability profiles).

## Key File Paths

- Core runtime entry: `avaagent.py`
- Operator API: `brain/operator_server.py`
- TTS engine: `brain/tts_engine.py`
- STT engine: `brain/stt_engine.py`
- Model routing: `brain/model_routing.py`
- Deep self layer: `brain/deep_self.py`
- Tool layer: `brain/desktop_tool_orchestrator.py`, `brain/desktop_tools.py`, `brain/desktop_tool_policies.py`
- Frontend app: `apps/ava-control/src/App.tsx`
- Frontend styles: `apps/ava-control/src/styles.css`
- Tauri config/runtime: `apps/ava-control/src-tauri/`
- Identity anchors: `ava_core/IDENTITY.md`, `ava_core/SOUL.md`, `ava_core/USER.md`

## Start Ava

- Standard launch: run `start.bat` from repo root.
- Desktop shortcut path is environment-specific; canonical script target remains `start.bat`.
- Operator API default endpoint: `http://127.0.0.1:5876`.
- If UI is needed, run/build Tauri app in `apps/ava-control`.

## Push to GitHub

- Preferred flow: run `push_to_github.bat` from repo root.
- Manual fallback:
  - `git add -A`
  - `git commit -m "<message>"`
  - `git push origin master`

## Current Known Issues

- Tauri frontend bundle is large (Rollup warning >500 kB); needs chunking optimization.
- STT is scaffold-level: no robust VAD/session management yet.
- MeloTTS quality path not production-ready yet; pyttsx3 is active default.
- **FAST PATH ROUTING BUG (Phase 44 fix target):** In `avaagent.py` `run_ava()` around line 7437, `use_fast_path` calls `_pick_fast_model_fallback()` first, which hardcodes `mistral:7b`. This overrides the Phase 25 routing result (`_route_model`) even when it correctly selects `ava-personal:latest` for social chat. The fix: check `_route_model` first, fall back to `_pick_fast_model_fallback()` only if empty.
- Operator transport is still polling-heavy; WebSocket migration planned (Phase 63).
- Concept graph lifecycle needs decay/associative recall wiring (Phase 45).

## Session Notes (April 28, 2026)

### What was explored this session

Full codebase audit was done in preparation for executing phases 44–68. Key files read:

- `config/ava_tuning.py` — full ModelRoutingConfig and capability profiles
- `brain/model_routing.py` — full routing logic including `_score_modes`, `build_model_routing_result`, `_resolve_warm_model_for_mode`, stickiness/cooldown logic
- `avaagent.py` — imports, globals, `run_ava()` response generation path (lines ~7400–7515), `_pick_fast_model_fallback()`, `_pick_deep_model_fallback()`
- `brain/deep_self.py` — `self_critique_async`, `ZekeMindModel`, mind model update
- `brain/operator_server.py` — `build_snapshot`, `build_debug_export`, routing fields in snapshot

### Key discoveries

1. **`social_chat_model = "ava-personal:latest"` is ALREADY set** in `config/ava_tuning.py` line 538. Phase 44 config change is already done.

2. **`ava-personal:latest` capability profile is already registered** with `fallback_priority=3` — best priority of all registered models for social/memory/deep modes.

3. **Fast path routing bug:** `_pick_fast_model_fallback()` (line 7144) returns `mistral:7b` first unconditionally. The `_route_model` from workspace state (the Phase 25 routing result, which correctly selects ava-personal for social chat) is only used as `elif` fallback after `_pick_fast_model_fallback()`. So most social chat turns go through mistral instead of ava-personal. Fix is a 3-line swap at line 7437.

4. **Deep path works correctly:** The deep path checks `_route_model` after the deep model fallback — but `_pick_deep_model_fallback()` returns `qwen2.5:14b` for reasoning tasks, which is correct.

5. **`LLM_MODEL = "llama3.1:8b"`** (line 172) is the baseline global tag used when no routing applies.

## Phase 44 — Implementation Plan (not yet executed)

### Changes required

**1. `avaagent.py` — fix fast path routing (3-line change at ~line 7437)**

Current code:
```python
if use_fast_path:
    _fast_model = _pick_fast_model_fallback()
    if _fast_model:
        _invoke_llm = ChatOllama(model=_fast_model, temperature=0.45)
        print(f"[run_ava] fast_path_model={_fast_model}")
    elif _route_model and _route_model != LLM_MODEL:
        _invoke_llm = ChatOllama(model=_route_model, temperature=0.5)
```

Fix (swap priority):
```python
if use_fast_path:
    # Phase 44: respect Phase 25 routing result first (ava-personal for social chat)
    if _route_model and _route_model != LLM_MODEL:
        _invoke_llm = ChatOllama(model=_route_model, temperature=0.45)
        print(f"[run_ava] fast_path_routed_model={_route_model}")
    else:
        _fast_model = _pick_fast_model_fallback()
        if _fast_model:
            _invoke_llm = ChatOllama(model=_fast_model, temperature=0.45)
            print(f"[run_ava] fast_path_model={_fast_model}")
```

**2. `brain/model_evaluator.py` — new file (bootstrap self-evaluator)**

Create `brain/model_evaluator.py` with `ModelSelfEvaluator` class:
- Loads/saves `state/model_eval_p44.json`
- `submit_for_evaluation(prompt, response, model_used)` — async; background thread
- Background worker: queries `mistral:7b` with same prompt as shadow, scores both via LLM judge
- After 5+ comparison pairs: writes decision — `confirmed_primary` (win_rate ≥ 0.60) or `flagged_for_review` (win_rate < 0.40 after 10+ samples)
- Scoring: LLM judge prompt scores both responses 0–1 on naturalness, helpfulness, personality
- Heuristic fallback scoring if judge model unavailable
- Module-level singleton: `get_evaluator(base_dir)` → `ModelSelfEvaluator`

State file schema (`state/model_eval_p44.json`):
```json
{
  "status": "evaluating | confirmed_primary | flagged_for_review",
  "ava_model": "ava-personal:latest",
  "challenger_model": "mistral:7b",
  "total_samples": 0,
  "ava_wins": 0,
  "challenger_wins": 0,
  "ties": 0,
  "decision_ts": 0.0,
  "decision_reason": "",
  "samples": []
}
```

**3. `avaagent.py` — wire evaluator**

After `raw_reply = getattr(result, "content", str(result)).strip()` (line ~7455):
- Check if `_invoke_llm.model` contains `"ava-personal"` to identify social chat response
- If so: `get_evaluator(BASE_DIR).submit_for_evaluation(user_input, raw_reply, _invoke_llm.model)`

Add to operator snapshot: expose `get_evaluator().get_status()` as `p44_eval` block.

**4. `docs/AVA_ROADMAP.md` — complete new roadmap**

Full roadmap with phases 1–43 (COMPLETE), 44–68 (PLANNED), and Long Term Vision (70–71) needs to be written. Phase 68+1 skipped per instructions.

### Execution commands

```bash
# Compile check
py -3.11 -m py_compile brain/model_evaluator.py avaagent.py

# Push
git add -A
git commit -m "phase 44: ava-personal as primary brain + bootstrap self-evaluator"
git push origin master
```

## Next Priorities (phases 44–68 roadmap)

Full phase specifications are in the roadmap the user provided. The new roadmap (phases 44–68) was about to be written to `docs/AVA_ROADMAP.md` when the session was interrupted. Phases diverge significantly from the old planned phases 44–50:

| Phase | New Title |
|---|---|
| 44 | Ava-personal as primary brain + self-evaluation |
| 45 | Concept graph decay + strengthen + prompt injection |
| 46 | Hot-reload tool registry |
| 47 | Watchdog restart system |
| 48 | Desktop widget orb |
| 49 | Screen pointer behavior |
| 50 | Audio visualization on orb |
| 51 | UI accessibility tree tool |
| 52 | Smart screenshot management |
| 53 | PyAutoGUI computer control |
| 54 | System stats monitoring |
| 55 | Drag and drop file input |
| 56 | Expanded orb expressions |
| 57 | Wake word detection |
| 58 | Boredom autonomous leisure |
| 59 | Chrome Dino game |
| 60 | Minecraft bot via mineflayer |
| 61 | Playing Minecraft with Zeke |
| 62 | MeloTTS voice upgrade |
| 63 | WebSocket real-time transport |
| 64 | Persistent episodic memory |
| 65 | Emotional continuity |
| 66 | Ava's own goals |
| 67 | Relationship arc stages |
| 68 | True self modification |

Phase 69 (Horizon Zero Dawn) skipped per instructions.

## Bootstrap Philosophy (critical rule for all phases 44+)

**NEVER choose Ava's personal preferences for her.** Every phase involving Ava's preferences, style, or identity must include a bootstrap mechanism — a system that lets Ava discover and form that aspect of herself through experience. Build the mechanism, not the default value. Her goals, hobbies, communication style, and emotional baseline all emerge from her experience, not from our decisions.

## Debug Export Interpretation Guide

`GET /api/v1/debug/export` emits a compact textual bundle derived from snapshot/runtime:

- **Ribbon / live summary:** high-signal operator strip (heartbeat mode, routing model, readiness, issues).
- **Heartbeat/runtime:** presence mode, summaries, learning focus, carryover readiness.
- **Model routing:** selected/fallback model, reason/confidence, overrides, available models.
- **Strategic continuity/memory:** thread carryover, relationship continuity, refinement class/priority.
- **Workbench:** proposal presence, execution readiness, last execution/command summaries.
- **Self-improvement loop:** active stage, awaiting approval, active issue.
- **Concerns diagnostics:** top concern and reconciliation status.
- **Reply path meta:** fast/deep route metadata and decision rationale.
- **Runtime self snapshot:** warm state fields persisted across ticks.
- **Startup resume block:** last startup continuity payload.
- **Workbench index preview:** compact proposal list/metadata.
- **Full snapshot JSON (truncated):** canonical machine-readable state dump used by operator UI.
