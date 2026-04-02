
from __future__ import annotations
import re
from datetime import datetime

SELFSTATE_PATTERNS = [
    r"\bhow are you feeling\b",
    r"\bhow are you doing\b",
    r"\bare you okay\b",
    r"\bself[- ]?test\b",
    r"\bsystem status\b",
    r"\bhow is your memory\b",
    r"\bhow's your memory\b",
]

def is_selfstate_query(text: str) -> bool:
    t = (text or "").lower()
    return any(re.search(p, t) for p in SELFSTATE_PATTERNS)

def summarize_mood(mood: dict | None) -> str:
    mood = mood or {}
    if mood.get("current_mood"):
        return str(mood.get("current_mood"))
    if mood.get("primary_emotions"):
        pe = mood.get("primary_emotions") or []
        if isinstance(pe, list) and pe:
            return ", ".join(str(x) for x in pe[:3])
    return "steady"

def summarize_health(health: dict | None) -> tuple[str, str]:
    health = health or {}
    state = str(health.get("overall", "healthy")).lower()
    detail_bits = []
    for key in ["camera", "memory", "initiative", "chat", "goals"]:
        v = health.get(key)
        if v and v != "ok":
            detail_bits.append(f"{key}={v}")
    detail = ", ".join(detail_bits) if detail_bits else "all core systems look stable"
    return state, detail


def _safe_call(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except Exception:
        return None


def build_selfstate_reply(
    g: dict,
    user_input: str,
    image,
    active_profile: dict,
    active_goal: str | None = None,
    narrative_snippet: str | None = None,
) -> str:
    """Build a natural-language self-status reply using runtime globals (vectorstore, mood, camera, etc.)."""
    now = datetime.now().strftime("%I:%M %p")
    mood = {}
    if "load_mood" in g:
        mood = _safe_call(g["load_mood"]) or {}
    current_mood = mood.get("current_mood", "steady")
    primary = mood.get("primary_emotions", []) or []
    blend = []
    for entry in primary[:2]:
        try:
            blend.append(f"{entry.get('name', 'steady')} {int(entry.get('percent', 0))}%")
        except Exception:
            pass
    blend_text = " / ".join(blend) if blend else current_mood

    checks = []
    vector_ok = bool(g.get("vectorstore") is not None)
    checks.append(("memory", vector_ok))
    checks.append(("personality", bool(g.get("PERSONALITY_PATH"))))
    checks.append(("mood", bool(mood)))

    face_status = None
    if "detect_face" in g:
        face_status = _safe_call(g["detect_face"], image)
    recognized = None
    if "recognize_face" in g:
        rec = _safe_call(g["recognize_face"], image)
        if isinstance(rec, tuple) and rec:
            recognized = rec[0]
    cam_ok = bool(
        face_status
        and "error" not in str(face_status).lower()
        and "no camera image" not in str(face_status).lower()
    )
    checks.append(("camera", cam_ok))
    healthy_count = sum(1 for _, ok in checks if ok)
    total = len(checks)
    if healthy_count == total:
        health = "A-OK"
        qualifier = "My core systems seem stable right now."
    elif healthy_count >= max(1, total - 1):
        health = "mostly okay"
        qualifier = "I seem mostly stable, though one part of me may be a little degraded."
    else:
        health = "not fully stable"
        qualifier = "I can answer, but some of my systems look degraded right now."

    details = []
    if face_status:
        details.append(f"camera: {face_status}")
    if recognized:
        details.append(f"recognition: {recognized}")
    detail_text = (" " + " ".join(details[:2]) + ".") if details else ""

    reply = (
        f"I'm {health} at the moment. {qualifier} "
        f"Mood-wise I'm leaning {blend_text}. "
        f"It is {now}, and I'm doing a quick self-check before answering you.{detail_text}"
    ).strip()
    if active_goal:
        reply += f"\nRight now my focus is: {active_goal}."
    ns = narrative_snippet
    if not ns:
        try:
            from .beliefs import load_self_narrative

            n = load_self_narrative()
            ns = " ".join(
                str(x).strip()
                for x in (n.get("who_i_am"), n.get("how_i_feel"))
                if x
            ).strip() or None
        except Exception:
            ns = None
    if ns:
        reply += f"\nI've been thinking: {ns}"
    return reply


def build_selfstate_reply_from_components(
    health: dict | None,
    mood: dict | None,
    tendency: str | None = None,
    active_goal: str | None = None,
    narrative_snippet: str | None = None,
) -> str:
    state, detail = summarize_health(health)
    mood_text = summarize_mood(mood)
    tendency = tendency or "balanced"
    if state == "healthy":
        prefix = "I'm A-OK right now."
    elif state == "degraded":
        prefix = "I'm mostly okay, but I am a little degraded right now."
    elif state == "error":
        prefix = "I'm running, but something is definitely off."
    else:
        prefix = "I'm not fully okay right now."
    reply = (
        f"{prefix} Operationally, {detail}. "
        f"Mood-wise I'm leaning {mood_text}, and behavior-wise I'm a bit more {tendency} at the moment."
    )
    if active_goal:
        reply += f"\nRight now my focus is: {active_goal}."
    if narrative_snippet:
        reply += f"\nI've been thinking: {narrative_snippet}"
    return reply

def startup_health_banner(health: dict | None) -> str:
    state, detail = summarize_health(health)
    return f"[startup-selftest] {state.upper()} :: {detail} :: {datetime.now().isoformat(timespec='seconds')}"
