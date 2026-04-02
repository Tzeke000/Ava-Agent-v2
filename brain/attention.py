from __future__ import annotations

from dataclasses import dataclass

from .perception import PerceptionState


@dataclass
class AttentionState:
    user_present: bool
    user_engaged: bool
    should_speak: bool
    suppression_reason: str


def compute_attention(perception: PerceptionState, seconds_since_last_message: float) -> AttentionState:
    """
    Decides whether Ava should speak right now based on what she sees.
    Called before choose_initiative_candidate().
    """
    if not perception.face_detected:
        return AttentionState(False, False, False, "no_face_detected")

    if seconds_since_last_message > 300:
        return AttentionState(True, False, False, "user_idle_too_long")

    em = (perception.face_emotion or "").lower()
    if em in ("angry", "disgust"):
        return AttentionState(True, True, False, "negative_expression_detected")

    engaged = seconds_since_last_message < 120
    return AttentionState(True, engaged, engaged, "clear")
