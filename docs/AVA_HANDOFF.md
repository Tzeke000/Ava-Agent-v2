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

- **Primary conversational route:** `mistral:7b` for social chat mode (routing stability fix, target 0.85 score lane).
- **Fine-tuned self model:** `ava-personal:latest` exists and is ready; Phase 44 is promoting it to primary.
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
- Operator transport is still polling-heavy; WebSocket migration planned (Phase 47).
- Concept graph lifecycle needs future decay/associative recall wiring (Phase 45).

## Next Priorities

1. Promote `ava-personal:latest` as primary route (Phase 44).
2. Add concept-graph decay + retrieval injection into prompts (Phase 45).
3. Plan Emil integration boundary/contracts (Phase 46).
4. Replace polling with WebSocket streams for snapshot/active events (Phase 47).
5. Add autonomous phase-proposal loop (Phase 48).
6. Upgrade voice quality to Melo female lane (Phase 49).
7. Add clap-detection hands-free activation (Phase 50).

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
