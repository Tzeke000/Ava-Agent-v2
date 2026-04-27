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
- **Phase 6 salience** — :class:`SalientItem`, :class:`SalienceResult`, ``brain.salience.build_salience_result``; ranked items on :class:`InterpretationOutput` / :class:`perception.PerceptionState` for summaries, memory-worthiness, and initiative (see roadmap).
- **Phase 7 continuity** — :class:`ContinuityResult` (identity_state, temporal match factors); ``brain.continuity.update_continuity``.
- **Phase 8 identity** — :class:`IdentityResolutionResult` (raw vs resolved identity); ``brain.identity_fallback.resolve_identity_fallback``.
- **Phase 9 scene** — :class:`SceneSummaryResult`; ``brain.scene_summary.build_scene_summary``.
- **Phase 10 interpretation** — :class:`InterpretationLayerResult` (semantic events); ``brain.interpretation.build_interpretation_layer``.
- **Phase 11 perception memory** — :class:`PerceptionMemoryEvent`, :class:`PerceptionMemoryOutput`; ``brain.perception_memory.build_perception_memory_output``.
- **Phase 12 memory scoring** — :class:`MemoryDecisionResult`, :class:`MemoryImportanceResult`; ``brain.memory_scoring.score_memory_importance``.
- **Phase 13 pattern learning** — :class:`PatternSignal`, :class:`PatternLearningResult`; ``brain.pattern_learning.learn_pattern_signals``.
- **Phase 14 proactive triggers** — :class:`ProactiveTriggerCandidate`, :class:`ProactiveTriggerResult`; ``brain.proactive_triggers.evaluate_proactive_triggers``.
- **Phase 15 self-tests** — :class:`SelfTestCheckResult`, :class:`SelfTestRunResult`, :class:`HealthSummaryResult`; ``brain.selftests``.
- **Phase 16 workbench proposals** — :class:`RepairProposal`, :class:`WorkbenchProposalResult`; ``brain.workbench.build_workbench_proposals``.
- **Phase 16.5 supervised execution** — :class:`WorkbenchExecutionRequest`, :class:`WorkbenchExecutionResult`, :class:`FileChangePlan`, :class:`FileChangeRecord`; ``brain.workbench_execute``.
- **Phase 16.6 command layer** — :class:`WorkbenchCommandRequest`, :class:`WorkbenchCommandResult`, :class:`WorkbenchProposalView`, :class:`WorkbenchQueueState`; ``brain.workbench_commands``.
- **Phase 17 reflection** — :class:`ReflectionObservation`, :class:`SelfModelSnapshot`, :class:`ReflectionResult`; ``brain.reflection.build_reflection_result``.
- **Phase 18 contemplation** — :class:`ContemplationPrompt`, :class:`InternalPriorityView`, :class:`ContemplationResult`; ``brain.contemplation.build_contemplation_result``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class SalientItem:
    """One ranked salience candidate (Phase 6)."""

    item_type: str  # "face" | "object" | "scene_cue"
    label: str
    score: float
    factors: dict[str, float] = field(default_factory=dict)
    is_top: bool = False


@dataclass
class SalienceResult:
    """Ranked salience output; ``combined_scalar`` feeds legacy ``InterpretationOutput.salience``."""

    items: list[SalientItem] = field(default_factory=list)
    combined_scalar: float = 0.2
    legacy_engagement_scalar: float = 0.2
    future_hooks: dict[str, Any] = field(default_factory=dict)


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
    # Phase 6 — salience geometry (BGR frame pixels, x y w h)
    face_rects: list[tuple[int, int, int, int]] = field(default_factory=list)


@dataclass
class RecognitionOutput:
    """Stage 4 — LBPH recognition (skipped when vision not trusted)."""

    stage: StageResult
    recognized_text: str = ""
    face_identity: Optional[str] = None
    identity_confidence: float = 0.0


@dataclass
class ContinuityResult:
    """Phase 7 — structured temporal continuity (lightweight frame memory, not a full tracker)."""

    identity_state: str = "no_face"
    # confirmed_recognition | likely_identity_by_continuity | unknown_face | no_face
    continuity_confidence: float = 0.0
    prior_identity: Optional[str] = None
    current_identity: Optional[str] = None
    matched_factors: dict[str, float] = field(default_factory=dict)
    matched_notes: list[str] = field(default_factory=list)
    frame_gap: int = 0
    seconds_since_prior: float = -1.0
    suppress_flip: bool = False
    last_stable_identity: Optional[str] = None


@dataclass
class IdentityResolutionResult:
    """Phase 8 — public identity hierarchy (raw LBPH separate from resolved/stable)."""

    identity_state: str = "no_face"
    # confirmed_recognition | likely_identity_by_continuity | unknown_face | no_face
    raw_identity: Optional[str] = None
    resolved_identity: Optional[str] = None
    stable_identity: Optional[str] = None
    identity_confidence: float = 0.0
    fallback_source: str = "none"  # recognition | continuity | none
    fallback_notes: list[str] = field(default_factory=list)


@dataclass
class SceneSummaryResult:
    """Phase 9 — compact stable scene description for reasoning, memory, and UI."""

    face_presence: str = "unknown"  # none | unknown_face | single_face | multiple_faces
    face_count_estimate: int = 0
    primary_identity_summary: str = ""
    key_entities: list[str] = field(default_factory=list)
    lighting_summary: str = ""
    blur_summary: str = ""
    scene_change_summary: str = ""
    entrant_summary: str = ""
    overall_scene_state: str = "uncertain"  # stable | changed | uncertain
    compact_text_summary: str = ""
    summary_confidence: float = 0.5
    notes: list[str] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class InterpretationLayerResult:
    """Phase 10 — semantic events inferred from structured perception (not raw pixels, not user text gen)."""

    event_types: list[str] = field(default_factory=list)
    event_confidence: float = 0.5
    event_priority: float = 0.5
    interpreted_subject: Optional[str] = None
    interpreted_identity: Optional[str] = None
    interpretation_notes: list[str] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)
    no_meaningful_change: bool = True
    primary_event: str = "uncertain_visual_state"


@dataclass
class PerceptionMemoryEvent:
    """Phase 11 — one memory-ready perception record (no persistence in this phase)."""

    wall_time: float = 0.0
    frame_seq: int = 0
    event_type: str = ""
    event_confidence: float = 0.0
    event_priority: float = 0.0
    identity_state: str = ""
    resolved_identity: Optional[str] = None
    stable_identity: Optional[str] = None
    relevant_entities: list[str] = field(default_factory=list)
    scene_summary_snippet: str = ""
    interpretation_primary_event: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)
    memory_worthy_candidate: bool = False
    notes: list[str] = field(default_factory=list)
    suppressed_duplicate: bool = False


@dataclass
class PerceptionMemoryOutput:
    """Phase 11 — optional primary event + duplicate-suppression metadata."""

    event: Optional[PerceptionMemoryEvent] = None
    skipped: bool = False
    skip_reason: str = ""


@dataclass
class MemoryDecisionResult:
    """Phase 12 — scored decision for one memory-ready perception event (still no persistence)."""

    event_type: str = ""
    importance_score: float = 0.0
    importance_label: str = "ignore"  # ignore | low | medium | high
    memory_worthy: bool = False
    # transient_context | episodic_candidate | pattern_candidate | preference_candidate | ignore
    memory_class: str = "ignore"
    decision_reason: str = ""
    novelty_score: float = 0.0
    relevance_score: float = 0.0
    uncertainty_penalty: float = 0.0
    evidence: dict[str, Any] = field(default_factory=dict)
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class MemoryImportanceResult:
    """Phase 12 — wrapper with skip metadata around :class:`MemoryDecisionResult`."""

    decision: MemoryDecisionResult = field(default_factory=MemoryDecisionResult)
    skipped: bool = False
    skip_reason: str = ""


@dataclass
class PatternSignal:
    """Phase 13 — one lightweight probabilistic pattern signal."""

    pattern_detected: bool = False
    pattern_type: str = ""  # identity_presence_pattern | scene_stability_pattern | ...
    pattern_subject: str = ""
    pattern_strength: float = 0.0
    familiarity_score: float = 0.0
    unusualness_score: float = 0.0
    recurrence_count: int = 0
    recurrence_score: float = 0.0
    recent_transition_pattern: str = ""
    pattern_candidate: bool = False
    suggested_memory_class: str = "ignore"
    notes: list[str] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class PatternLearningResult:
    """Phase 13 — wrapper for all pattern-learning signals in one tick."""

    primary_signal: PatternSignal = field(default_factory=PatternSignal)
    signals: list[PatternSignal] = field(default_factory=list)
    skipped: bool = False
    skip_reason: str = ""
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProactiveTriggerCandidate:
    """Phase 14 — one proactive trigger candidate (recommendation-only)."""

    trigger_type: str = "no_trigger"
    trigger_score: float = 0.0
    trigger_priority: float = 0.0
    trigger_reason: str = ""
    suggested_action: str = "wait"
    caution_flags: list[str] = field(default_factory=list)
    supporting_evidence: dict[str, Any] = field(default_factory=dict)
    suppressed: bool = False
    suppression_reason: str = ""
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProactiveTriggerResult:
    """Phase 14 — proactive trigger recommendation output for this tick."""

    should_trigger: bool = False
    trigger_type: str = "no_trigger"
    trigger_score: float = 0.0
    trigger_priority: float = 0.0
    trigger_reason: str = ""
    suppression_reason: str = ""
    suggested_action: str = "wait"
    caution_flags: list[str] = field(default_factory=list)
    supporting_evidence: dict[str, Any] = field(default_factory=dict)
    candidates: list[ProactiveTriggerCandidate] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class SelfTestCheckResult:
    """Phase 15 — one subsystem self-test check result."""

    check_name: str = ""
    status: str = "skipped"  # ok | warning | failed | skipped
    severity: str = "info"  # info | warning | critical
    passed: bool = False
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: float = 0.0
    recommended_next_step: str = ""


@dataclass
class HealthSummaryResult:
    """Phase 15 — summarized health status across checks."""

    overall_status: str = "ok"  # ok | warning | failed
    overall_severity: str = "info"  # info | warning | critical
    failed_checks: list[str] = field(default_factory=list)
    warning_checks: list[str] = field(default_factory=list)
    passed_checks: list[str] = field(default_factory=list)
    skipped_checks: list[str] = field(default_factory=list)
    message: str = ""
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class SelfTestRunResult:
    """Phase 15 — startup/recurring self-test run output."""

    run_type: str = "recurring"  # startup | recurring | on_demand
    checks: list[SelfTestCheckResult] = field(default_factory=list)
    summary: HealthSummaryResult = field(default_factory=HealthSummaryResult)
    timestamp: float = 0.0
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class RepairProposal:
    """Phase 16 — reviewable repair proposal (no automatic execution)."""

    proposal_id: str = ""
    proposal_type: str = "no_action_needed"
    title: str = ""
    problem_detected: str = ""
    likely_cause: str = ""
    recommended_action: str = ""
    risk_level: str = "low"  # low | medium | high
    requires_human_review: bool = True
    confidence: float = 0.0
    source_checks: list[str] = field(default_factory=list)
    priority: str = "low"  # low | medium | high | urgent
    notes: list[str] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkbenchProposalResult:
    """Phase 16 — proposal bundle generated from self-tests/runtime evidence."""

    has_proposal: bool = False
    top_proposal: RepairProposal = field(default_factory=RepairProposal)
    proposals: list[RepairProposal] = field(default_factory=list)
    summary: str = ""
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class FileChangePlan:
    """Phase 16.5 — requested file action plan for supervised execution."""

    action_type: str = "write_patch_plan"
    target_path: str = ""
    content: str = ""
    patch_text: str = ""
    append_text: str = ""
    reason: str = ""
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class FileChangeRecord:
    """Phase 16.5 — recorded file action outcome for one path."""

    target_path: str = ""
    action_type: str = ""
    success: bool = False
    backup_path: str = ""
    created: bool = False
    modified: bool = False
    diff_summary: str = ""
    error_message: str = ""
    notes: list[str] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkbenchExecutionRequest:
    """Phase 16.5 — supervised execution request (requires approval for mutations)."""

    execution_id: str = ""
    proposal_id: str = ""
    approved: bool = False
    elevated_approval: bool = False
    execution_mode: str = "dry_run"  # dry_run | staged | apply
    action_type: str = "write_patch_plan"
    target_paths: list[str] = field(default_factory=list)
    change_plans: list[FileChangePlan] = field(default_factory=list)
    rejection_reason: str = ""
    requested_by: str = "system"
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkbenchExecutionResult:
    """Phase 16.5 — supervised execution result (no implicit auto-execution)."""

    execution_id: str = ""
    proposal_id: str = ""
    approved: bool = False
    execution_mode: str = "dry_run"
    action_type: str = ""
    success: bool = False
    blocked: bool = False
    denial_reason: str = ""
    requires_elevated_approval: bool = False
    target_paths: list[str] = field(default_factory=list)
    created_files: list[str] = field(default_factory=list)
    modified_files: list[str] = field(default_factory=list)
    backup_paths: list[str] = field(default_factory=list)
    diff_summary: list[str] = field(default_factory=list)
    rollback_available: bool = False
    rollback_hint: str = ""
    error_message: str = ""
    file_records: list[FileChangeRecord] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkbenchProposalView:
    """Phase 16.6 — compact proposal view for command/list operations."""

    proposal_id: str = ""
    proposal_type: str = "no_action_needed"
    title: str = ""
    priority: str = "low"
    risk_level: str = "low"
    confidence: float = 0.0
    requires_human_review: bool = True
    summary: str = ""
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkbenchQueueState:
    """Phase 16.6 — current in-memory workbench proposal/selection state."""

    has_proposals: bool = False
    proposal_count: int = 0
    selected_proposal_id: str = ""
    top_proposal_id: str = ""
    top_proposal_type: str = "no_action_needed"
    top_proposal_title: str = ""
    top_proposal_priority: str = "low"
    top_proposal_risk: str = "low"
    approval_needed: bool = True
    last_execution_info: dict[str, Any] = field(default_factory=dict)
    last_rollback_info: dict[str, Any] = field(default_factory=dict)
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkbenchCommandRequest:
    """Phase 16.6 — structured request for proposal review/approval commands."""

    command_name: str = "show_workbench_status"
    proposal_id: str = ""
    execution_mode: str = "dry_run"  # dry_run | staged | apply
    approved: bool = False
    elevated_approval: bool = False
    requested_by: str = "operator"
    notes: list[str] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkbenchCommandResult:
    """Phase 16.6 — result of executing one workbench command request."""

    command_name: str = ""
    proposal_id: str = ""
    execution_mode: str = "dry_run"
    approved: bool = False
    elevated_approval: bool = False
    success: bool = False
    summary: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    blocked_reason: str = ""
    execution_result: Optional[WorkbenchExecutionResult] = None
    available_proposals: list[WorkbenchProposalView] = field(default_factory=list)
    queue_state: WorkbenchQueueState = field(default_factory=WorkbenchQueueState)
    last_execution_info: dict[str, Any] = field(default_factory=dict)
    last_rollback_info: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class ReflectionObservation:
    """Phase 17 — one grounded observation used for reflection."""

    source: str = ""
    key: str = ""
    value: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0


@dataclass
class SelfModelSnapshot:
    """Phase 17 — soft operational self-model tags and state."""

    self_model_tags: list[str] = field(default_factory=list)
    current_operational_state: str = "uncertain_state"
    confidence: float = 0.0
    notes: list[str] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class ReflectionResult:
    """Phase 17 — evidence-based reflection output (no direct behavior override)."""

    reflection_category: str = "uncertain_state_reflection"
    reflection_summary: str = ""
    recent_outcome: str = ""
    outcome_quality: str = "mixed"  # good | mixed | poor
    detected_issue: str = ""
    detected_success: str = ""
    suggested_adjustment: str = ""
    confidence: float = 0.0
    observations: list[ReflectionObservation] = field(default_factory=list)
    self_model: SelfModelSnapshot = field(default_factory=SelfModelSnapshot)
    notes: list[str] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class ContemplationPrompt:
    """Phase 18 — bounded contemplation input framing."""

    contemplation_theme: str = "certainty_vs_usefulness"
    prompt_text: str = ""
    evidence_keys: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class InternalPriorityView:
    """Phase 18 — soft internal priorities (guidance only)."""

    observe: float = 0.5
    clarify: float = 0.5
    remember: float = 0.5
    adapt: float = 0.5
    maintain: float = 0.5
    engage: float = 0.5
    remain_silent: float = 0.5
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class ContemplationResult:
    """Phase 18 — bounded internal contemplation output."""

    contemplation_theme: str = "certainty_vs_usefulness"
    contemplation_summary: str = ""
    contemplation_question: str = ""
    contemplation_position: str = ""
    contemplation_confidence: float = 0.0
    guiding_principles: list[str] = field(default_factory=list)
    priority_weights: InternalPriorityView = field(default_factory=InternalPriorityView)
    caution_notes: list[str] = field(default_factory=list)
    evidence_basis: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class ContinuityOutput:
    """Stage 5 — identity continuity / tracking + Phase 7 structured result."""

    stage: StageResult
    last_stable_identity: Optional[str] = None
    continuity_confidence: float = 0.0
    tracking_note: str = ""
    structured: Optional[ContinuityResult] = None


@dataclass
class InterpretationOutput:
    """Stage 6 — emotion + salience (scene / LLM interpretation is a future hook)."""

    stage: StageResult
    face_emotion: Optional[str] = None
    salience: float = 0.2
    scene_summary_hint: str = ""
    # Phase 6 — structured salience (ranked items); salience scalar blends with legacy engagement
    salience_structured: Optional[SalienceResult] = None


@dataclass
class PackageOutput:
    """Stage 7 — final bundle marker (logging + adapter input)."""

    stage: StageResult


@dataclass
class PerceptionPipelineBundle:
    """All stage outputs for one tick; :func:`brain.perception_state_adapter.bundle_to_perception_state` maps to ``PerceptionState``."""

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
    # Phase 8 — after continuity
    identity_resolution: Optional[IdentityResolutionResult] = None
    # Phase 9 — after identity resolution
    scene_summary: Optional[SceneSummaryResult] = None
    # Phase 10 — after scene summary (semantic events; separate from emotion/salience stage above)
    interpretation_layer: Optional[InterpretationLayerResult] = None
    # Phase 11 — after interpretation layer
    perception_memory: Optional[PerceptionMemoryOutput] = None
    # Phase 12 — after perception memory output
    memory_importance: Optional[MemoryImportanceResult] = None
    # Phase 13 — after memory importance scoring
    pattern_learning: Optional[PatternLearningResult] = None
    # Phase 14 — after pattern learning
    proactive_trigger: Optional[ProactiveTriggerResult] = None
    # Phase 15 — startup/recurring health diagnostics
    selftests: Optional[SelfTestRunResult] = None
    # Phase 16 — repair workbench proposal generation
    workbench: Optional[WorkbenchProposalResult] = None
    # Phase 17 — reflection and self-model synthesis
    reflection: Optional[ReflectionResult] = None
    # Phase 18 — bounded philosophical/internal contemplation
    contemplation: Optional[ContemplationResult] = None
