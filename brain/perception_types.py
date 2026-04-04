"""
Structured types for the Phase 3 perception pipeline (brain.perception_pipeline).

Each stage produces a small dataclass with :class:`StageResult` plus stage-specific fields.
Downstream code adapts a :class:`PerceptionPipelineBundle` to :class:`perception.PerceptionState`.

**Future extension points** (not all wired yet):
- Richer **quality** scoring (blur, exposure) — partially in ``camera.assess_frame_quality_basic``.
- **Salience** scoring beyond face + emotion heuristics.
- **Tracking / continuity** — multi-frame identity tracks (E4).
- **Scene summaries** — short-term visual memory text.
- **Interpretation** layer — LLM or rule-based scene narration (gated by trust).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class StageResult:
    """Success/failure wrapper for one pipeline stage (always safe defaults on failure)."""

    ok: bool
    skipped: bool = False
    error: Optional[str] = None
    confidence: Optional[float] = None
    meta: dict = field(default_factory=dict)


@dataclass
class AcquisitionOutput:
    """Stage 1 — frame resolution (delegates to ``CameraManager.resolve_frame_detailed``)."""

    stage: StageResult
    resolved: Any = None  # ResolvedFrame | None


@dataclass
class QualityOutput:
    """Stage 2 — trust / staleness / quality gate (from ``ResolvedFrame``; no duplicate CV here)."""

    stage: StageResult
    visual_truth_trusted: bool = False
    vision_status: str = "stable"
    frame_quality: float = 0.0
    frame_quality_reasons: list[str] = field(default_factory=list)
    is_fresh: bool = False
    recovery_state: str = "none"
    fresh_frame_streak: int = 0


@dataclass
class DetectionOutput:
    """Stage 3 — face detection (Haar cascade + status line)."""

    stage: StageResult
    face_detected: bool = False
    person_count: int = 0
    face_status: str = "No camera image"
    gaze_present: bool = False


@dataclass
class RecognitionOutput:
    """Stage 4 — LBPH recognition (skipped when vision not trusted)."""

    stage: StageResult
    recognized_text: str = ""
    face_identity: Optional[str] = None
    identity_confidence: float = 0.0


@dataclass
class ContinuityOutput:
    """Stage 5 — identity continuity / tracking (placeholder + ``note_trusted_identity`` hook)."""

    stage: StageResult
    last_stable_identity: Optional[str] = None
    continuity_confidence: float = 0.0
    tracking_note: str = ""


@dataclass
class InterpretationOutput:
    """Stage 6 — emotion + salience (scene / LLM interpretation is a future hook)."""

    stage: StageResult
    face_emotion: Optional[str] = None
    salience: float = 0.2
    scene_summary_hint: str = ""


@dataclass
class PackageOutput:
    """Stage 7 — final bundle marker (logging + adapter input)."""

    stage: StageResult


@dataclass
class PerceptionPipelineBundle:
    """All stage outputs for one tick; :func:`bundle_to_perception_state` maps to ``PerceptionState``."""

    acquisition: AcquisitionOutput
    quality: QualityOutput
    detection: DetectionOutput
    recognition: RecognitionOutput
    continuity: ContinuityOutput
    interpretation: InterpretationOutput
    package: PackageOutput
    # Raw resolved frame reference for adapter (frame + timestamps)
    resolved: Any = None
    user_text: str = ""
