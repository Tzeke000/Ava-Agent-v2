# Ava Agent v2 — Repository history

**Last updated:** April 27, 2026  
**Repo:** `Tzeke000/Ava-Agent-v2` (public)  
**Companion doc:** [`AVA_ROADMAP.md`](AVA_ROADMAP.md) — vision, shipped phases, future direction.

---

## How to read this file

- **`AVA_ROADMAP.md`** = what Ava is for, **what is shipped**, and **what comes next**.
- **`AVA_HISTORY.md`** (this file) = **what changed over time**, major milestones, and **honest supersessions** when later work replaced an earlier snapshot.

---

## What this repo is (current)

A **local-first** Ava agent (`avaagent.py`) with direct imports from **`brain/`** (no overlay stack). Runtime combines **LLM reasoning**, **camera perception**, **vector memory**, **profiles**, **goals**, **initiative**, **reflection**, and a **staged perception pipeline** (`brain/perception_pipeline.py`) feeding **`PerceptionState`** via **`brain/perception_state_adapter.py`**. **Workbench** flows include **proposals**, **supervised execution** (Phase 16.5), and **approval/commands** (Phase 16.6). **`ava_core/`** holds **IDENTITY.md**, **SOUL.md**, **USER.md**, and **BOOTSTRAP.md** (first-run scaffolding); continuity layers treat the first three as **primary anchors** (see roadmap Phase 29).

---

## Chronological timeline (factual; month-level unless noted)

### Early v2 direction — clean architecture

The codebase was rewritten away from a **monolithic overlay** model toward **direct `brain/` imports**, stable **`BASE_DIR`**, and a single **`run_ava`** path. That direction remains the backbone of the repo.

### April 2026 — Full repository audit & documentation reset

A deep **repository audit** produced the first **`AVA_HISTORY.md`** snapshot (file counts, directory layout, “what runs” vs legacy local files). That audit was **valuable and dated**: it recorded **Stage 7 and identity_loader as “not wired”** and **`IDENTITY_DIR` risks** at **that moment in time**.

### Supersession — Stage 7, profiles, and `ava_core` (later 2026)

**Do not use the old audit alone for current wiring.** As of the **Phase 1–30 baseline**, `avaagent.py` **imports and uses** `brain/trust_manager.py`, `brain/persona_switcher.py`, `brain/profile_store.py`, and `brain/identity_loader.py`. **`IDENTITY_DIR`** in `identity_loader.py` resolves to the repo’s **`ava_core/`** via `Path(__file__).resolve().parent.parent / "ava_core"` — **not** a legacy hardcoded `D:/AvaAgent` path.

This is an intentional **historical correction**: architecture ownership and wiring **evolved after** the April 2026 audit text was frozen.

### 2026 — “Better eyes” / perception pipeline expansion (Phases 3–15)

Incremental delivery of **frame store / acquisition freshness**, **quality & blur**, **structured salience**, **continuity & identity fallback**, **scene summary**, **interpretation layer**, **perception memory output**, **memory importance scoring**, **pattern learning**, **proactive triggers**, and **self-tests** — each stage logged and tolerant of partial failure. See roadmap sections **Perception — Phase 3** through **Phase 15**.

### 2026 — Phase 19: `bundle_to_perception_state` ownership

Mapping **`PerceptionPipelineBundle` → `PerceptionState`** was **centralized** in **`brain/perception_state_adapter.py`** so the pipeline stays orchestration-only and the adapter owns flat field copies. This was a **deliberate modular cleanup** (roadmap Phase 19); earlier inline mapping in the pipeline is **obsolete**.

### 2026 — Phase 20 — `config/ava_tuning.py`

Centralized tuning knobs to avoid scattering magic numbers across modules.

### 2026 — Workbench Phases 16 / 16.5 / 16.6

- **16:** Repair **proposals** from diagnostics (`brain/workbench.py`) — reviewable, not auto-applied.  
- **16.5:** **Supervised execution** (`brain/workbench_execute.py`) — explicit approval posture.  
- **16.6:** **Commands / queue / approval surface** (`brain/workbench_commands.py`).

### 2026 — Reflection, contemplation, calibration (Phases 17–18, 21)

**Reflection** and **contemplation** modules produce structured, bounded outputs; **calibration** (`brain/calibration.py`) observability was added without silent auto-retuning.

### 2026 — Voice, social continuity, memory refinement (Phases 22–24)

**Voice conversation** timing hints; **relationship / social continuity**; **memory refinement** layered on prior scoring — all advisory.

### 2026 — Model routing, curiosity, outcomes, nuance (Phases 25–28)

**Ollama model routing** with continuity preserved across “reasoning engines”; **curiosity**; **outcome learning**; **conversational nuance** — guidance-only, no autonomous personality rewrite.

### 2026 — Multi-session continuity & supervised improvement (Phases 29–30)

- **Phase 29 (`brain/session_continuity.py`):** Bounded **cross-session carryover**, with **`ava_core` identity anchors** loaded **first**; **BOOTSTRAP.md** only when core identity is not yet established.  
- **Phase 30 (`brain/self_improvement_loop.py`):** **Supervised self-improvement loop** snapshot linking self-tests, workbench, execution/rollback hooks in **`g`**, reflection, outcome learning, and strategic continuity — **no auto-approve / auto-execute**.

Together, **Phases 1–30** (including **16.5** and **16.6**) form the **completed** staged roadmap described in **`AVA_ROADMAP.md`**.

---

## Scale snapshot (approximate)

- **`brain/`** — on the order of **70+** Python modules (grows as phases add files); treat counts as approximate between commits.  
- **`avaagent.py`** — large single entry (Gradio UI + orchestration); perception and cognition remain modular under **`brain/`**.

---

## Ambiguous or environment-specific notes

- **Line counts** and **exact file sizes** in any old audit change every commit—use the repo, not static prose, for precision.  
- **“Private vs public”** repo label may differ by fork; **roadmap header** is authoritative for this workspace.  
- Some **future roadmap** items (e.g. **prospective memory / calendar**, **debug panel**) remain **additive**—they are **not** missing phases 1–30.

---

## Archived reference

An older, line-by-line audit narrative (April 2026) remains useful for **git archaeology** but **must not** override this file or the roadmap for **current** wiring—especially for **Stage 7**, **`ava_core` paths**, and **perception pipeline** completion. When in doubt, **`grep`** `avaagent.py` and read **`brain/perception_pipeline.py`**.
