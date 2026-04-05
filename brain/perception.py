"""
Unified perception from camera + user text.

Phase 3: building :class:`PerceptionState` goes through :mod:`brain.perception_pipeline`
(staged acquisition → quality → detection → recognition → continuity → interpretation → package).

Vision gating: identity, emotion, and present-tense scene claims require ``visual_truth_trusted``
(camera layer: stable after fresh frames / recovery — see ``brain.camera``).

Manual test plan matches ``brain.camera`` (obstruction → recovering → stable).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .perception_pipeline import bundle_to_perception_state, run_perception_pipeline
from .perception_utils import compute_salience, lbph_distance_to_identity_confidence
from .shared import now_ts

# Backward-compatible names for any legacy imports
_lbph_distance_to_identity_confidence = lbph_distance_to_identity_confidence


@dataclass
class PerceptionState:
    frame: Any = None
    face_detected: bool = False
    face_identity: str | None = None
    face_emotion: str | None = None
    gaze_present: bool = False
    person_count: int = 0
    user_text: str = ""
    salience: float = 0.2
    timestamp: float = field(default_factory=now_ts)
    face_status: str = "No camera image"
    recognized_text: str = ""
    # Better Eyes E1 — first-class vision / trust (see brain/camera.py)
    vision_status: str = "stable"
    frame_ts: float = 0.0
    frame_age_ms: float = -1.0
    frame_source: str = "none"
    frame_seq: int = 0
    is_fresh: bool = False
    fresh_frame_streak: int = 0
    visual_truth_trusted: bool = True
    frame_quality: float = 0.0
    frame_quality_reasons: list[str] = field(default_factory=list)
    recovery_state: str = "none"
    last_stable_identity: str | None = None
    identity_confidence: float = 0.0
    continuity_confidence: float = 0.0
    # Phase 2 — acquisition layer (see brain.frame_store)
    acquisition_freshness: str = "unavailable"
    # Phase 4 — structured quality (brain.frame_quality + perception_pipeline quality stage)
    quality_label: str = "unreliable"
    blur_quality_score: float = 0.0
    darkness_quality_score: float = 0.0
    overexposure_quality_score: float = 0.0
    motion_smear_quality_score: float = 1.0
    occlusion_quality_score: float = 1.0
    recognition_quality_scale: float = 1.0
    expression_quality_scale: float = 1.0


def _compute_salience(state: PerceptionState) -> float:
    return compute_salience(state.face_detected, state.face_emotion, state.user_text or "")


def build_perception(camera_manager, image, g: dict, user_text: str = "") -> PerceptionState:
    """
    Build PerceptionState from camera + user input.
    When vision is not stable, do not treat identity/emotion as current truth.
    """
    bundle = run_perception_pipeline(camera_manager, image, g, user_text or "")
    return bundle_to_perception_state(bundle, user_text or "")
