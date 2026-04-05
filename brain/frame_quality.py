"""
Phase 4 — explicit frame quality scoring (OpenCV, local).
Phase 5 — dedicated blur detection (Laplacian variance) with labels and confidence scales.

Computes per-metric scores, an overall score **compatible with legacy camera gating**,
and labels ``usable`` | ``weak`` | ``unreliable``. Logs with prefix ``[frame_quality]``.

**Overall score** uses the same recipe as the former ``assess_frame_quality_basic``:
``0.55 * blur_norm + 0.45 * lum_comfort``, then ×0.82 if any ``reason_flags`` apply.
**Motion** / **occlusion** metrics are diagnostic only and do not change ``overall_quality_score``.

**Phase 5 blur** (tune only ``BLUR_VAR_*`` below):
- ``blur_label``: sharp | soft | blurry
- ``blur_layer_confidence_scales()`` → (recognition, expression, interpretation) multipliers
- Combined with overall quality label scales in ``perception_pipeline`` (multiply).

Future hooks: blur → scene summaries, recognition fallback, visual memory worthiness — see
``FrameQualityAssessment.meta`` and ``blur_reason_flags``.
"""
from __future__ import annotations

import time
from typing import Any, Optional

try:
    import cv2
    import numpy as np
except Exception:
    cv2 = None
    np = None

from .perception_types import FrameQualityAssessment

# Keep in sync with brain.camera.LOW_QUALITY_THRESHOLD for "weak" band lower bound.
WEAK_MIN_OVERALL = 0.28
USABLE_MIN_OVERALL = 0.50

# ---------------------------------------------------------------------------
# Phase 5 — blur thresholds (Laplacian variance, CV_64F). Single source of truth.
# ---------------------------------------------------------------------------
# blurry: var < BLUR_VAR_SOFT_MAX
# soft:   BLUR_VAR_SOFT_MAX <= var < BLUR_VAR_SHARP_MIN
# sharp:  var >= BLUR_VAR_SHARP_MIN
BLUR_VAR_SOFT_MAX = 45.0
BLUR_VAR_SHARP_MIN = 120.0

# blur_score for legacy overall only: min(1, var / BLUR_VAR_SCALE)
BLUR_VAR_SCALE = 180.0

_prev_gray_small: Optional[Any] = None


def classify_blur_laplacian_var(blur_var: float) -> tuple[str, list[str]]:
    """
    Map raw Laplacian variance to ``blur_label`` and ``blur_reason_flags``.

    Thresholds: :data:`BLUR_VAR_SOFT_MAX`, :data:`BLUR_VAR_SHARP_MIN`.
    """
    flags: list[str] = []
    if blur_var < BLUR_VAR_SOFT_MAX:
        return "blurry", ["blur_blurry"]
    if blur_var < BLUR_VAR_SHARP_MIN:
        return "soft", ["blur_soft"]
    return "sharp", []


def blur_layer_confidence_scales(blur_label: str) -> tuple[float, float, float]:
    """
    Multipliers for (recognition, expression, interpretation).

    Interpretation uses a **lighter** penalty than expression (salience / scene hooks).
    """
    if blur_label == "sharp":
        return 1.0, 1.0, 1.0
    if blur_label == "soft":
        return 0.92, 0.88, 0.96
    return 0.78, 0.72, 0.90


def _label_from_overall(overall: float) -> str:
    if overall >= USABLE_MIN_OVERALL:
        return "usable"
    if overall >= WEAK_MIN_OVERALL:
        return "weak"
    return "unreliable"


def confidence_scales_from_label(label: str) -> tuple[float, float]:
    """(recognition_scale, expression_scale) from overall quality label — Phase 4."""
    if label == "usable":
        return 1.0, 1.0
    if label == "weak":
        return 0.88, 0.82
    return 0.72, 0.65


def compute_frame_quality(frame: Any) -> FrameQualityAssessment:
    """
    Analyze ``frame`` (BGR). Safe on ``None`` or import failure.
    """
    global _prev_gray_small
    empty = FrameQualityAssessment(
        blur_value=0.0,
        blur_label="blurry",
        blur_confidence_scale=0.78,
        blur_recognition_scale=0.78,
        blur_expression_scale=0.72,
        blur_interpretation_scale=0.90,
        blur_reason_flags=["blur_blurry"],
        overall_quality_score=0.0,
        quality_label="unreliable",
        reason_flags=["no_frame"],
        meta={"ts": time.time()},
    )
    if frame is None or cv2 is None or np is None:
        print(
            "[frame_quality] blur_value=0.0 blur_score=0.000 blur_label=blurry "
            "blur_scales=(0.78,0.72,0.90) darkness=0.000 overexposure=0.000 "
            "overall=0.000 label=unreliable (no_frame_or_cv)"
        )
        return empty

    try:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blur_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        mean_lum = float(gray.mean()) / 255.0

        blur_label, blur_reason_flags = classify_blur_laplacian_var(blur_var)
        br, be, bi = blur_layer_confidence_scales(blur_label)

        reason_flags: list[str] = []
        if blur_var < BLUR_VAR_SOFT_MAX:
            reason_flags.append("blurry")
        if mean_lum < 0.07:
            reason_flags.append("very_dark")
        elif mean_lum < 0.12:
            reason_flags.append("low_light")
        if mean_lum > 0.93:
            reason_flags.append("overexposed")

        blur_score = min(1.0, blur_var / BLUR_VAR_SCALE)
        lum_comfort = 1.0 - min(1.0, abs(mean_lum - 0.42) * 2.0)
        darkness_score = min(1.0, mean_lum / 0.15)
        if mean_lum < 0.05:
            darkness_score = min(darkness_score, 0.15)
        overexposure_score = 1.0
        if mean_lum > 0.85:
            overexposure_score = max(0.0, 1.0 - (mean_lum - 0.85) / 0.15)

        # Legacy overall (matches former assess_frame_quality_basic).
        overall = 0.55 * blur_score + 0.45 * max(0.0, lum_comfort)
        if reason_flags:
            overall *= 0.82

        motion_smear_score = 1.0
        h, w = gray.shape[:2]
        scale = min(1.0, 160.0 / max(w, 1))
        small = cv2.resize(gray, (max(1, int(w * scale)), max(1, int(h * scale))))
        if _prev_gray_small is not None and _prev_gray_small.shape == small.shape:
            diff = np.mean(np.abs(small.astype(np.float32) - _prev_gray_small.astype(np.float32)))
            motion_smear_score = float(max(0.0, min(1.0, 1.0 - diff / 35.0)))
        _prev_gray_small = small.copy()

        occlusion_score = 1.0
        try:
            edges = cv2.Canny(gray, 50, 150)
            edge_density = float(np.mean(edges > 0))
            meta_occlusion = {"edge_density": round(edge_density, 4), "note": "provisional_occlusion_proxy"}
        except Exception:
            meta_occlusion = {"note": "occlusion_unavailable"}
            occlusion_score = 0.85

        label = _label_from_overall(overall)
        meta = {
            "blur_var": round(blur_var, 2),
            "mean_lum": round(mean_lum, 4),
            "blur_label": blur_label,
            **meta_occlusion,
        }

        print(
            f"[frame_quality] blur_value={blur_var:.1f} blur_score={blur_score:.3f} blur_label={blur_label} "
            f"blur_scales(rec,expr,interp)=({br:.2f},{be:.2f},{bi:.2f}) "
            f"darkness={darkness_score:.3f} overexposure={overexposure_score:.3f} "
            f"motion_smear={motion_smear_score:.3f} occlusion={occlusion_score:.3f} "
            f"overall={overall:.3f} label={label} flags={reason_flags}"
        )

        return FrameQualityAssessment(
            blur_value=blur_var,
            blur_label=blur_label,
            blur_confidence_scale=br,
            blur_recognition_scale=br,
            blur_expression_scale=be,
            blur_interpretation_scale=bi,
            blur_reason_flags=list(blur_reason_flags),
            blur_score=blur_score,
            darkness_score=darkness_score,
            overexposure_score=overexposure_score,
            motion_smear_score=motion_smear_score,
            occlusion_score=occlusion_score,
            overall_quality_score=overall,
            quality_label=label,
            reason_flags=reason_flags,
            meta=meta,
        )
    except Exception as e:
        br, be, bi = blur_layer_confidence_scales("soft")
        print(f"[frame_quality] compute failed: {e} — provisional soft blur scales")
        return FrameQualityAssessment(
            blur_value=-1.0,
            blur_label="soft",
            blur_confidence_scale=br,
            blur_recognition_scale=br,
            blur_expression_scale=be,
            blur_interpretation_scale=bi,
            blur_reason_flags=["blur_quality_unavailable"],
            blur_score=0.5,
            darkness_score=0.5,
            overexposure_score=0.5,
            motion_smear_score=0.5,
            occlusion_score=0.5,
            overall_quality_score=0.5,
            quality_label="weak",
            reason_flags=["quality_unavailable"],
            meta={"error": str(e)},
        )


def assess_frame_quality_basic(frame: Any) -> tuple[float, list[str]]:
    """Backward-compatible (score, reasons) for callers expecting the old API."""
    q = compute_frame_quality(frame)
    return q.overall_quality_score, list(q.reason_flags)
