"""
brain/startup.py — Ava startup initialization sequence.

Extracted from avaagent.py. Call run_startup(globals()) from avaagent.py
after all module-level definitions are done.

g is avaagent's globals() dict — all avaagent functions and constants
are accessible through it. We write initialized objects back into g so
avaagent's global namespace sees them.

THREADING RULE: any call that invokes Ollama / LLM must run in a daemon
thread, never on the main startup thread. The main thread must reach the
operator_server startup within ~10 seconds of launch.
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any


def _bg(name: str, fn, *args, **kwargs) -> threading.Thread:
    """Spawn a daemon thread and start it immediately."""
    t = threading.Thread(target=fn, args=args, kwargs=kwargs, daemon=True, name=name)
    t.start()
    return t


def run_startup(g: dict[str, Any]) -> None:
    """Initialize all Ava subsystems. g = globals() from avaagent.py."""
    # Guard: prevent double-execution if the module is somehow imported twice
    if g.get("_STARTUP_COMPLETE"):
        print("[startup] already complete — skipping duplicate run")
        return

    BASE_DIR: Path = g["BASE_DIR"]
    STATE_DIR: Path = g["STATE_DIR"]

    # Clear any stale restart flag left from a previous session so the watchdog
    # doesn't see it and immediately launch a second avaagent instance.
    _restart_flag = BASE_DIR / "state" / "restart_requested.flag"
    try:
        if _restart_flag.is_file():
            _restart_flag.unlink()
            print("[startup] cleared stale restart_requested.flag")
    except Exception as _rf_e:
        print(f"[startup] could not clear restart flag: {_rf_e}")
    MOOD_PATH: Path = g["MOOD_PATH"]
    OWNER_PERSON_ID: str = g["OWNER_PERSON_ID"]
    print("[startup] step: identity + profiles")
    g["ensure_owner_profile"]()
    g["ensure_identity_files"]()

    print("[startup] step: tool registry")
    try:
        _tool_registry = g["ToolRegistry"]()
        g["_tool_registry"] = _tool_registry
        g["_desktop_tool_registry"] = _tool_registry
    except Exception as e:
        g["_tool_registry"] = None
        g["_desktop_tool_registry"] = None
        print(f"[tool_registry] startup skipped: {e}")

    print("[startup] step: visual memory")
    try:
        _vm = g["VisualMemory"](BASE_DIR)
        g["_visual_memory"] = _vm
        g["_visual_memory_summary"] = _vm.get_cluster_summary()
    except Exception as e:
        g["_visual_memory"] = None
        g["_visual_memory_summary"] = {"cluster_count": 0, "named_clusters": 0, "most_seen": ""}
        print(f"[visual_memory] startup skipped: {e}")

    print("[startup] step: connectivity monitor")
    try:
        from brain.connectivity import bootstrap_connectivity
        bootstrap_connectivity(g)
    except Exception as e:
        g["_is_online"] = False
        g["_connection_quality"] = "offline"
        g["_ollama_cloud_reachable"] = False
        g["_connectivity_changed"] = False
        print(f"[connectivity] bootstrap skipped: {e}")

    print("[startup] step: image generator")
    try:
        from tools.creative.image_generator import ImageGenerator
        g["_image_generator"] = ImageGenerator(g)
        print("[image_gen] ImageGenerator initialized")
    except Exception as e:
        g["_image_generator"] = None
        print(f"[image_gen] startup skipped: {e}")

    print("[startup] step: dual brain")
    try:
        from brain.dual_brain import bootstrap_dual_brain
        bootstrap_dual_brain(g)
    except Exception as e:
        g["_dual_brain"] = None
        print(f"[dual_brain] startup skipped: {e}")

    print("[startup] step: eye tracker")
    try:
        from brain.eye_tracker import bootstrap_eye_tracker
        bootstrap_eye_tracker(g)
    except Exception as e:
        g["_eye_tracker"] = None
        print(f"[eye_tracker] startup skipped: {e}")

    print("[startup] step: expression detector")
    try:
        from brain.expression_detector import bootstrap_expression_detector
        bootstrap_expression_detector(g)
    except Exception as e:
        g["_expression_detector"] = None
        print(f"[expression_detector] startup skipped: {e}")

    print("[startup] step: video memory")
    try:
        from brain.video_memory import bootstrap_video_memory
        bootstrap_video_memory(g)
    except Exception as e:
        g["_video_memory"] = None
        print(f"[video_memory] startup skipped: {e}")

    print("[startup] step: heartbeat bootstrap")
    try:
        from brain.heartbeat import bootstrap_heartbeat_runtime
        bootstrap_heartbeat_runtime(g)
    except Exception as e:
        print(f"[heartbeat] bootstrap skipped: {e}")

    print("[startup] step: startup resume")
    try:
        from brain.runtime_presence import bootstrap_startup_resume
        bootstrap_startup_resume(g)
    except Exception as e:
        print(f"[startup_resume] skipped: {e}")

    print("[startup] step: concern reconciliation")
    try:
        from brain.concern_reconciliation import run_startup_concern_reconciliation
        run_startup_concern_reconciliation(g)
    except Exception as e:
        print(f"[concern_reconciliation] startup skipped: {e}")

    print("[startup] step: curiosity topics bootstrap")
    try:
        g["bootstrap_curiosity_topics"](g)
    except Exception as e:
        print(f"[curiosity_topics] bootstrap skipped: {e}")

    # ── Concept graph: init object synchronously (file load only, no LLM) ────
    # bootstrap_from_existing_memory calls mistral:7b — runs in background thread
    print("[startup] step: concept graph init")
    try:
        from brain.concept_graph import ConceptGraph, bootstrap_from_existing_memory
        _concept_graph = ConceptGraph(BASE_DIR)
        g["_concept_graph"] = _concept_graph
        g["_concept_graph_bootstrap_nodes"] = 0

        _tmp_path = BASE_DIR / "state" / "concept_graph.json.tmp"
        if _tmp_path.is_file():
            # Another process left the .tmp locked — skip bootstrap this run
            # to avoid WinError 5 / 32. The graph loaded fine from the .json file.
            try:
                _tmp_path.unlink()
                print("[concept_graph] stale .tmp removed, bootstrap will run")
            except OSError:
                print("[concept_graph] .tmp still locked — skipping bootstrap this run")
                _bg("ava-cg-bootstrap", lambda: None)  # no-op placeholder
                _concept_graph.decay_unused_nodes(days_threshold=30)
                # Skip the real bootstrap block below
                raise RuntimeError("tmp_locked")

        def _bg_concept_bootstrap():
            try:
                _cg_boot = bootstrap_from_existing_memory(_concept_graph, g)
                if isinstance(_cg_boot, dict):
                    g["_concept_graph_bootstrap_nodes"] = int(_cg_boot.get("nodes_created") or 0)
                else:
                    g["_concept_graph_bootstrap_nodes"] = int(_cg_boot or 0)
                _concept_graph.decay_unused_nodes(days_threshold=30)
                print(f"[concept_graph] bootstrap complete nodes={g['_concept_graph_bootstrap_nodes']}")
            except Exception as e:
                print(f"[concept_graph] background bootstrap error: {e}")

        _bg("ava-cg-bootstrap", _bg_concept_bootstrap)
        print("[startup] step: concept graph bootstrap dispatched to background")
    except Exception as e:
        g["_concept_graph"] = None
        g["_concept_graph_bootstrap_nodes"] = 0
        print(f"[concept_graph] startup skipped: {e}")

    print("[startup] step: finetune pipeline")
    try:
        from brain.finetune_pipeline import FineTuneManager
        _finetune_manager = FineTuneManager(BASE_DIR)
        g["_finetune_manager"] = _finetune_manager
        g["_finetune_status"] = _finetune_manager._read_status()
        _finetune_manager.schedule_finetune(interval_days=7)
    except Exception as e:
        g["_finetune_manager"] = None
        g["_finetune_status"] = {"status": "idle", "error": str(e)}
        print(f"[finetune] startup skipped: {e}")

    print("[startup] step: deep self snapshot")
    try:
        from brain.deep_self import deep_self_snapshot
        g["_deep_self"] = deep_self_snapshot(g)
    except Exception as e:
        g["_deep_self"] = {}
        print(f"[deep_self] startup skipped: {e}")

    # ── Self model weekly update: calls qwen2.5:14b — background thread ───────
    print("[startup] step: self model update (background)")
    try:
        def _bg_self_model():
            try:
                g["update_self_model"](g)
                print("[self_model] weekly update complete")
            except Exception as e:
                print(f"[self_model] weekly update error: {e}")
        _bg("ava-self-model-update", _bg_self_model)
    except Exception as e:
        print(f"[self_model] weekly update skipped: {e}")

    print("[startup] step: inner monologue")
    try:
        from brain.inner_monologue import start_inner_monologue
        start_inner_monologue(g)
    except Exception as e:
        print(f"[inner_monologue] startup skipped: {e}")

    print("[startup] step: history manager")
    try:
        from brain.history_manager import AvaHistoryManager
        g["history_manager"] = AvaHistoryManager(BASE_DIR, target_context_length=8000)
    except Exception as e:
        g["history_manager"] = None
        print(f"[history_manager] startup skipped: {e}")

    print("[startup] step: pickup note")
    try:
        from brain.shutdown_ritual import load_pickup_note
        g["pickup_note"] = load_pickup_note()
    except Exception as e:
        g["pickup_note"] = None
        print(f"[shutdown_ritual] pickup note load skipped: {e}")

    print("[startup] step: profiles + identity")
    g["seed_default_profiles"]()
    from brain.identity_loader import load_ava_identity
    g["_AVA_IDENTITY_BLOCK"] = load_ava_identity()
    g["ensure_emotion_reference_file"]()
    g["_write_ava_pid_file"]()
    # Defer selftest until after vectorstore init (which runs in background)
    # so vector_memory check passes correctly
    def _delayed_selftest():
        time.sleep(15.0)  # wait for vectorstore init to complete
        try:
            from brain.health_runtime import print_startup_selftest
            print_startup_selftest(g)
        except Exception as _ste:
            print(f"[startup-selftest] error: {_ste}")
    _bg("ava-delayed-selftest", _delayed_selftest)

    print("[startup] step: self narrative")
    from brain.beliefs import SELF_NARRATIVE_PATH, save_self_narrative, load_self_narrative
    if not SELF_NARRATIVE_PATH.exists():
        save_self_narrative(load_self_narrative())
        print("[beliefs] self-narrative initialized")
    else:
        load_self_narrative()
        print("[beliefs] self-narrative loaded")

    print("[startup] step: goal system")
    g["load_goal_system"]()

    # ── Vectorstore: embed_query call blocks on nomic-embed-text — background ─
    print("[startup] step: vectorstore init (background)")
    try:
        def _bg_vectorstore():
            try:
                g["init_vectorstore"]()
            except Exception as e:
                print(f"[vectorstore] background init error: {e}")
        _bg("ava-vectorstore-init", _bg_vectorstore)
    except Exception as e:
        print(f"[vectorstore] background dispatch failed: {e}")

    print("[startup] step: memory decay tick")
    try:
        from brain.memory import decay_tick
        decay_tick(g)
        print("[memory] decay tick complete")
    except Exception as e:
        print(f"[memory] decay tick failed: {e}")

    print("[startup] step: life rhythm schedule")
    try:
        g["_schedule_life_rhythm_on_startup"]()
    except Exception as e:
        print(f"[life_rhythm] schedule failed: {e}")

    print("[startup] step: health check")
    try:
        from brain.health import run_system_health_check
        _health_state = run_system_health_check(g, kind="startup")
        print(f"Health: {_health_state.get('startup_summary', 'UNKNOWN')}")
    except Exception as e:
        print(f"[health] startup check failed: {e}")

    print("[startup] step: face labels")
    g["load_face_labels"]()

    # InsightFace GPU engine (additive — face_recognizer remains the fallback).
    # Init in a background thread because buffalo_l weights download can take
    # 30-60s on first run and we don't want to block startup.
    print("[startup] step: insight_face GPU engine (background)")
    try:
        def _bg_insight_face():
            try:
                from brain.insight_face_engine import bootstrap_insight_face
                bootstrap_insight_face(g)
            except Exception as e:
                print(f"[insight_face] background init error: {e!r}")
        _bg("ava-insight-face-init", _bg_insight_face)
    except Exception as e:
        g["_insight_face"] = None
        print(f"[insight_face] dispatch failed: {e}")

    print("[startup] step: mood init")
    if not MOOD_PATH.exists():
        g["save_mood"](g["enrich_mood_state"](g["default_mood"]()))
    else:
        g["save_mood"](g["load_mood"]())

    # Phase 65: mood carryover with decay
    try:
        _co_path = STATE_DIR / "mood_carryover.json"
        if _co_path.is_file():
            _co = json.loads(_co_path.read_text(encoding="utf-8"))
            _co_mood = _co.get("mood") or {}
            _co_ts = float(_co.get("shutdown_ts") or 0)
            _absent_hours = (time.time() - _co_ts) / 3600 if _co_ts > 0 else 999
            if _absent_hours < 72 and isinstance(_co_mood, dict):
                _decay = max(0.0, 1.0 - 0.20 * _absent_hours)
                if _absent_hours > 8:
                    _decay = max(0.30, _decay)
                _base_mood = g["load_mood"]()
                for _k, _v in _co_mood.items():
                    if isinstance(_v, float):
                        _co_mood[_k] = _v * _decay
                _base_mood.update({k: v for k, v in _co_mood.items() if k in _base_mood and isinstance(v, float)})
                g["save_mood"](g["enrich_mood_state"](_base_mood))
                print(f"[mood_carryover] applied decay={_decay:.2f} absent_hours={_absent_hours:.1f}")
    except Exception as e:
        print(f"[mood_carryover] skipped: {e}")

    print("[startup] step: state file init")
    ACTIVE_PERSON_PATH: Path = g["ACTIVE_PERSON_PATH"]
    SELF_MODEL_PATH: Path = g["SELF_MODEL_PATH"]
    INITIATIVE_STATE_PATH: Path = g["INITIATIVE_STATE_PATH"]
    SESSION_STATE_PATH: Path = g["SESSION_STATE_PATH"]
    EXPRESSION_STATE_PATH: Path = g["EXPRESSION_STATE_PATH"]

    if not ACTIVE_PERSON_PATH.exists():
        g["save_active_person_state"](OWNER_PERSON_ID, source="startup")
    if not SELF_MODEL_PATH.exists():
        g["save_self_model"](g["default_self_model"]())
    if not INITIATIVE_STATE_PATH.exists():
        g["save_initiative_state"](g["default_initiative_state"]())
    if not SESSION_STATE_PATH.exists():
        g["save_session_state"]({
            "total_message_count": 0,
            "session_start_at": g["now_iso"](),
            "last_session_end_at": "",
        })
    else:
        _boot_sess = g["load_session_state"]()
        _boot_sess["session_start_at"] = g["now_iso"]()
        g["save_session_state"](_boot_sess)
    if not EXPRESSION_STATE_PATH.exists():
        g["save_expression_state"](g["default_expression_state"]())

    print("[startup] step: TTS worker (COM-isolated thread)")
    try:
        from brain.tts_worker import get_tts_worker
        _tts_worker = get_tts_worker()
        g["_tts_worker"] = _tts_worker
        print(f"[tts_worker] available={_tts_worker.available} voice={_tts_worker.voice_name()}")
    except Exception as e:
        g["_tts_worker"] = None
        print(f"[tts_worker] startup skipped: {e}")

    print("[startup] step: TTS engine (wraps worker)")
    try:
        from brain.tts_engine import TTSEngine
        _tts = TTSEngine()
        g["tts_engine"] = _tts if _tts.is_available() else None
        g["tts_engine_name"] = _tts.engine_name() if _tts.is_available() else "none"
    except Exception:
        g["tts_engine"] = None
        g["tts_engine_name"] = "none"
    g["tts_enabled"] = True  # default ON now that worker is COM-safe

    print("[startup] step: STT engine (Whisper)")
    try:
        from brain.stt_engine import STTEngine
        _stt = STTEngine()
        if _stt.is_available():
            g["stt_engine"] = _stt
            print("[stt_engine] Whisper ready — voice input enabled")
        else:
            g["stt_engine"] = None
            print("[stt_engine] Whisper unavailable — voice input disabled")
    except Exception as _stt_e:
        g["stt_engine"] = None
        print(f"[stt_engine] startup skipped: {_stt_e}")

    print("[startup] step: wake word detector")
    try:
        from brain.wake_word import WakeWordDetector
        def _on_wake_word() -> None:
            g["_stt_listen_requested"] = True
        _wake_detector = WakeWordDetector(g, on_wake=_on_wake_word, base_dir=BASE_DIR)
        _wake_detector.start()
        g["_wake_word_detector"] = _wake_detector
        print(f"[wake_word] detector started backend={_wake_detector._backend}")
    except Exception as e:
        g["_wake_word_detector"] = None
        print(f"[wake_word] startup skipped: {e}")

    print("[startup] step: clap detector")
    try:
        from brain.clap_detector import ClapDetector
        def _on_clap() -> None:
            g["_stt_listen_requested"] = True
        _clap_detector = ClapDetector(g, on_clap=_on_clap)
        _clap_started = _clap_detector.start()
        g["_clap_detector"] = _clap_detector if _clap_started else None
        print(f"[clap_detect] started={_clap_started}")
    except Exception as e:
        g["_clap_detector"] = None
        print(f"[clap_detect] startup skipped: {e}")

    print("[startup] step: LLaVA vision check")
    try:
        from brain.scene_understanding import _pick_llava_model
        _llava_model = _pick_llava_model()
        if _llava_model:
            print(f"[llava] {_llava_model} available — scene understanding active")
            g["_llava_model_name"] = _llava_model
        else:
            print("[llava] no llava model found — scene understanding disabled")
            g["_llava_model_name"] = None
    except Exception as e:
        print(f"[llava] check failed: {e}")
        g["_llava_model_name"] = None

    print("[startup] step: voice loop")
    try:
        from brain.voice_loop import start_voice_loop
        _vl_ok = start_voice_loop(g)
        if _vl_ok:
            print("[voice_loop] started=True — passive listening active")
        else:
            # Diagnose exactly why voice loop didn't start
            _stt_obj = g.get("stt_engine")
            _tts_obj = g.get("tts_engine")
            _stt_ok = (
                _stt_obj is not None
                and callable(getattr(_stt_obj, "is_available", None))
                and _stt_obj.is_available()
            )
            _tts_ok = (
                _tts_obj is not None
                and callable(getattr(_tts_obj, "is_available", None))
                and _tts_obj.is_available()
            )
            print(
                f"[voice_loop] started=False — "
                f"stt={'ok' if _stt_ok else ('None' if _stt_obj is None else 'unavailable')} "
                f"tts={'ok' if _tts_ok else ('None' if _tts_obj is None else 'unavailable')}"
            )
    except Exception as e:
        print(f"[voice_loop] startup skipped: {e}")

    # ── Milestone 100: calls qwen2.5:14b — background thread, runs once ───────
    print("[startup] step: milestone 100 check (background)")
    try:
        def _bg_milestone():
            try:
                from brain.milestone_100 import run_milestone_if_needed
                run_milestone_if_needed(g)
            except Exception as e:
                print(f"[milestone_100] background error: {e}")
        _bg("ava-milestone-100", _bg_milestone)
    except Exception as e:
        print(f"[milestone_100] dispatch skipped: {e}")

    # ── Background ticks: heartbeat + video capture daemons ───────────────────
    print("[startup] step: background tick threads")
    try:
        from brain.background_ticks import bootstrap_background_ticks
        bootstrap_background_ticks(g)
    except Exception as e:
        print(f"[background_ticks] startup skipped: {e}")

    g["_STARTUP_COMPLETE"] = True
    print("Ava running...")
    print(f"Base dir: {BASE_DIR}")
    print(f"Profiles dir: {g['PROFILES_DIR']}")
    print(f"Memory dir: {g['MEMORY_DIR']}")
    print(f"Self reflection dir: {g['SELF_REFLECTION_DIR']}")
    print(f"Workbench dir: {g['WORKBENCH_DIR']}")
    print(f"Emotion reference: {g['EMOTION_REFERENCE_PATH']}")
    print(f"Active person: {g['get_active_person_id']()}")
