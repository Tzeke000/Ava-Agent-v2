"""
Phase 6 — structured visual salience (faces, scene cues, future objects).

Computes ranked :class:`SalienceResult` with per-item factor breakdowns. Intended for
scene summaries, interpretation prioritization, memory-worthiness, and initiative hooks.

Keeps a **combined_scalar** compatible with legacy ``perception_utils.compute_salience`` by
blending geometric / motion / recognition factors with the existing engagement heuristic.
"""
from __future__ import annotations

from typing import Any, Optional

from .perception_types import SalientItem, SalienceResult
from .perception_utils import compute_salience

# Tunable weights for primary face (sum ~1.0)
W_CENTER = 0.26
W_PROMINENCE = 0.22
W_MOTION = 0.14
W_RECOGNITION = 0.20
W_ENGAGEMENT = 0.18

# Blend legacy engagement vs structured primary (when a face item exists)
LEGACY_BLEND = 0.38
STRUCTURED_BLEND = 0.62


def _center_score(cx: float, cy: float, w: int, h: int) -> float:
    if w <= 0 or h <= 0:
        return 0.35
    nx = abs(cx - w / 2.0) / max(w / 2.0, 1.0)
    ny = abs(cy - h / 2.0) / max(h / 2.0, 1.0)
    d = (nx * nx + ny * ny) ** 0.5 / (2.0**0.5)
    return float(max(0.0, min(1.0, 1.0 - d)))


def _prominence_score(area: float, frame_area: float) -> float:
    if frame_area <= 0:
        return 0.2
    r = area / frame_area
    return float(max(0.0, min(1.0, r**0.55 * 4.2)))


def _recognition_relevance(face_identity: Optional[str], face_detected: bool) -> float:
    if face_identity:
        return 1.0
    if face_detected:
        return 0.72
    return 0.35


def _pick_primary_rect(
    rects: list[tuple[int, int, int, int]], fw: int, fh: int
) -> Optional[tuple[int, int, int, int]]:
    if not rects:
        return None
    best = None
    best_key = -1.0
    fa = float(max(fw * fh, 1))
    for x, y, rw, rh in rects:
        area = float(max(rw * rh, 1))
        cx = x + rw / 2.0
        cy = y + rh / 2.0
        c = _center_score(cx, cy, fw, fh)
        p = _prominence_score(area, fa)
        key = 0.55 * c + 0.45 * p
        if key > best_key:
            best_key = key
            best = (x, y, rw, rh)
    return best


def _face_item_score(
    *,
    center: float,
    prominence: float,
    motion_attention: float,
    recognition: float,
    engagement: float,
) -> float:
    raw = (
        W_CENTER * center
        + W_PROMINENCE * prominence
        + W_MOTION * motion_attention
        + W_RECOGNITION * recognition
        + W_ENGAGEMENT * engagement
    )
    return float(max(0.0, min(1.0, raw)))


def build_salience_result(
    *,
    frame_shape: Optional[tuple[int, ...]],
    face_rects: list[tuple[int, int, int, int]],
    face_detected: bool,
    person_count: int,
    face_identity: Optional[str],
    face_emotion: Optional[str],
    user_text: str,
    motion_smear_score: float = 1.0,
) -> SalienceResult:
    """
    Build ranked salient items and a combined scalar for the interpretation stage.

    **Implemented factors:** centeredness, prominence, motion attention (from motion smear),
    recognition relevance, legacy emotion/user_text engagement.

    **Placeholders (zero or minimal score):** hand-held object bias, scene-change delta —
    exposed as items or factors for future wiring.
    """
    ut = user_text or ""
    legacy = compute_salience(face_detected, face_emotion, ut)
    motion_attention = float(max(0.0, min(1.0, 1.0 - motion_smear_score)))
    items: list[SalientItem] = []

    fh, fw = 0, 0
    if frame_shape is not None and len(frame_shape) >= 2:
        fh, fw = int(frame_shape[0]), int(frame_shape[1])

    engagement = legacy if face_detected else legacy

    if face_detected and face_rects and fw > 0 and fh > 0:
        primary = _pick_primary_rect(face_rects, fw, fh)
        if primary is not None:
            x, y, rw, rh = primary
            area = float(max(rw * rh, 1))
            fa = float(max(fw * fh, 1))
            cx, cy = x + rw / 2.0, y + rh / 2.0
            center = _center_score(cx, cy, fw, fh)
            prominence = _prominence_score(area, fa)
            recog = _recognition_relevance(face_identity, True)
            score = _face_item_score(
                center=center,
                prominence=prominence,
                motion_attention=motion_attention,
                recognition=recog,
                engagement=engagement,
            )
            label = face_identity or "unknown_face"
            fac = {
                "centeredness": round(center, 3),
                "prominence": round(prominence, 3),
                "motion_attention": round(motion_attention, 3),
                "recognition_relevance": round(recog, 3),
                "engagement": round(engagement, 3),
            }
            items.append(
                SalientItem(
                    item_type="face",
                    label=label,
                    score=score,
                    factors=fac,
                    is_top=False,
                )
            )

        if person_count > 1 and len(face_rects) > 1:
            sec_score = 0.0
            for x, y, rw, rh in face_rects:
                if primary and (x, y, rw, rh) == primary:
                    continue
                area = float(max(rw * rh, 1))
                fa = float(max(fw * fh, 1))
                cx, cy = x + rw / 2.0, y + rh / 2.0
                c = _center_score(cx, cy, fw, fh)
                p = _prominence_score(area, fa)
                recog = 0.55
                s = 0.82 * _face_item_score(
                    center=c,
                    prominence=p,
                    motion_attention=motion_attention,
                    recognition=recog,
                    engagement=0.55,
                )
                sec_score = max(sec_score, s)
            if sec_score > 0.08:
                items.append(
                    SalientItem(
                        item_type="face",
                        label="additional_face",
                        score=sec_score,
                        factors={"secondary": 1.0, "motion_attention": round(motion_attention, 3)},
                        is_top=False,
                    )
                )
    elif face_detected:
        # Cascade reported faces but no rects — single-face fallback
        recog = _recognition_relevance(face_identity, True)
        center = 0.55
        prominence = 0.45 if person_count <= 1 else 0.38
        score = _face_item_score(
            center=center,
            prominence=prominence,
            motion_attention=motion_attention,
            recognition=recog,
            engagement=engagement,
        )
        label = face_identity or "unknown_face"
        items.append(
            SalientItem(
                item_type="face",
                label=label,
                score=score,
                factors={
                    "centeredness": center,
                    "prominence": prominence,
                    "motion_attention": round(motion_attention, 3),
                    "recognition_relevance": recog,
                    "engagement": round(engagement, 3),
                    "fallback": 1.0,
                },
                is_top=False,
            )
        )

    # Scene cue: sudden motion / instability
    if motion_attention >= 0.28:
        mscore = float(min(1.0, 0.25 + 0.9 * motion_attention))
        items.append(
            SalientItem(
                item_type="scene_cue",
                label="motion_spike",
                score=mscore,
                factors={"motion_attention": round(motion_attention, 3)},
                is_top=False,
            )
        )

    future_hooks: dict[str, Any] = {
        "hand_held_object": "unwired",
        "scene_change_delta": 0.0,
    }

    items.sort(key=lambda it: it.score, reverse=True)
    top_threshold = 0.08
    top_idx = next((i for i, it in enumerate(items) if it.score >= top_threshold), None)
    for i, it in enumerate(items):
        it.is_top = top_idx is not None and i == top_idx

    struct_scalar = items[top_idx].score if top_idx is not None else legacy
    if face_detected and items and items[0].item_type == "face":
        combined = LEGACY_BLEND * legacy + STRUCTURED_BLEND * struct_scalar
    else:
        combined = 0.55 * legacy + 0.45 * struct_scalar if items else legacy

    combined = float(max(0.15, min(1.0, combined)))

    for it in items:
        facs = ", ".join(f"{k}={v}" for k, v in sorted(it.factors.items())[:6])
        print(f"[salience] item={it.item_type}:{it.label} score={it.score:.2f} factors={{{facs}}} top={it.is_top}")

    return SalienceResult(
        items=items,
        combined_scalar=combined,
        legacy_engagement_scalar=legacy,
        future_hooks=future_hooks,
    )


def salience_items_as_dicts(items: list[SalientItem]) -> list[dict[str, Any]]:
    """JSON-friendly list for :class:`perception.PerceptionState` / UI."""
    return [
        {
            "item_type": it.item_type,
            "label": it.label,
            "score": round(float(it.score), 4),
            "factors": dict(it.factors),
            "is_top": bool(it.is_top),
        }
        for it in items
    ]
