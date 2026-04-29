---
name: Ava architecture notes from Phase 44-68 implementation
description: Non-obvious architectural facts discovered while implementing phases 44-68
type: project
---

**Fast-path routing bypass (FIXED in Phase 44):** avaagent.py `run_ava()` line ~7437 originally had `_pick_fast_model_fallback()` running BEFORE checking `_route_model` (Phase 25 routing result). This meant ava-personal:latest was never used for social chat despite being configured. Fixed by swapping priority.

**Why:** Phase 25 routing correctly selects ava-personal for social chat via `workspace.state.perception.routing_selected_model`, but the fast-path hardcoded mistral:7b first.
**How to apply:** If routing seems to not be working, check whether the fast/deep path fallback functions are overriding the workspace routing result.

**Two build_prompt paths exist:** `build_prompt()` (deep) and `build_prompt_fast()` (fast). Both inject the `_AVA_IDENTITY_BLOCK` via the same persona injection block at the end. When editing prompts, changes to `build_prompt` alone may not affect fast-path turns.

**Heartbeat receives globals dict `g`:** The `_run_heartbeat_tick` function receives the full avaagent globals dict as `g`. This is how heartbeat triggers leisure checks, concept decay, etc. — via `g.get("_concept_graph")`.

**ava_style.json already existed** in state/ with `orb_base_size`, `orb_ring_count`, `preferred_idle_color` etc. Phase 56 added `emotion_shape_mappings` field. Tools write to it; frontend reads it for compound emotion display.
