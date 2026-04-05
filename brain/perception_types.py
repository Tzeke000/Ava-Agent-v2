"""
Structured types for the Phase 3 perception pipeline (brain.perception_pipeline).

Each stage produces a small dataclass with :class:`StageResult` plus stage-specific fields.
Downstream code adapts a :class:`PerceptionPipelineBundle` to :class:`perception.PerceptionState`.

**Future extension points** (not all wired yet):
- **Frame quality** — see :class:`FrameQualityAssessment` and ``brain.frame_quality`` (Phase 4).
- **Salience** scoring beyond face + emotion heuristics.
- **Tracking / continuity** — multi-frame identity tracks (E4).
- **Scene summaries** — short-term visual memory text.
- **Interpretation** layer — LLM or rule-based scene narration (gated by trust).
- **Phase 5 blur** — scene summaries, recognition fallback, interpretation certainty, and visual memory-worthiness can read ``blur_label`` / ``blur_reason_flags`` from :class:`FrameQualityAssessment` or :class:`perception.PerceptionState` (hooks not all wired yet).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class FrameQualityAssessment:
    """
    Structured frame quality (Phase 4 + Phase 5 blur layer). Scores are in [0, 1] where
    higher is better except where noted. ``overall_quality_score`` matches the legacy
    camera aggregate used for ``ResolvedFrame.frame_quality`` / low-quality gating when
    computed via ``brain.frame_quality.compute_frame_quality``.

    **Phase 5 blur** (Laplacian variance): ``blur_value``, ``blur_label`` (sharp | soft | blurry),
    per-layer scales for recognition / expression / interpretation — see
    ``brain.frame_quality.blur_layer_confidence_scales``.
    """

    blur_value: float = 0.0
    blur_label: str = "sharp"
    blur_confidence_scale: float = 1.0
    blur_recognition_scale: float = 1.0
    blur_expression_scale: float = 1.0
    blur_interpretation_scale: float = 1.0
    blur_reason_flags: list[str] = field(default_factory=list)
    blur_score: float = 0.0
    darkness_score: float = 0.0
    overexposure_score: float = 0.0
    motion_smear_score: float = 1.0
    occlusion_score: float = 1.0
    overall_quality_score: float = 0.0
    quality_label: str = "unreliable"
    reason_flags: list[str] = field(default_factory=list)
    meta: dict = field(default_factory=dict)


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
    """Stage 2 — trust / staleness / structured quality (see ``FrameQualityAssessment``)."""

    stage: StageResult
    visual_truth_trusted: bool = False
    vision_status: str = "stable"
    frame_quality: float = 0.0
    frame_quality_reasons: list[str] = field(default_factory=list)
    is_fresh: bool = False
    recovery_state: str = "none"
    fresh_frame_streak: int = 0
    structured: Optional[FrameQualityAssessment] = None
    recognition_confidence_scale: float = 1.0
    expression_confidence_scale: float = 1.0
    # Phase 5 — blur layer (combined scales above = quality_label × blur)
    blur_value: float = 0.0
    blur_label: str = "sharp"
    blur_recognition_scale: float = 1.0
    blur_expression_scale: float = 1.0
    blur_interpretation_scale: float = 1.0
    quality_only_recognition_scale: float = 1.0
    quality_only_expression_scale: float = 1.0


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
