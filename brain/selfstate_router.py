import re
from datetime import datetime

_PATTERNS = [
    r"\bhow are you feeling\b",
    r"\bhow are you doing\b",
    r"\bare you okay\b",
    r"\bself\s*test\b",
    r"\bsystem status\b",
    r"\bhow is your memory\b",
]


def is_selfstate_query(text: str) -> bool:
    low = (text or "").strip().lower()
    return any(re.search(p, low) for p in _PATTERNS)


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
    now = datetime.now().strftime("%I:%M %p")
    mood = {}
    if 'load_mood' in g:
        mood = _safe_call(g['load_mood']) or {}
    current_mood = mood.get('current_mood', 'steady')
    primary = mood.get('primary_emotions', []) or []
    blend = []
    for entry in primary[:2]:
        try:
            blend.append(f"{entry.get('name','steady')} {int(entry.get('percent', 0))}%")
        except Exception:
            pass
    blend_text = " / ".join(blend) if blend else current_mood

    checks = []
    vector_ok = bool(g.get('vectorstore') is not None)
    checks.append(("memory", vector_ok))
    checks.append(("personality", bool(g.get('PERSONALITY_PATH'))))
    checks.append(("mood", bool(mood)))

    face_status = None
    if 'detect_face' in g:
        face_status = _safe_call(g['detect_face'], image)
    recognized = None
    if 'recognize_face' in g:
        rec = _safe_call(g['recognize_face'], image)
        if isinstance(rec, tuple) and rec:
            recognized = rec[0]
    cam_ok = bool(face_status and "error" not in str(face_status).lower() and "no camera image" not in str(face_status).lower())
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
    if narrative_snippet:
        reply += f"\nI've been thinking: {narrative_snippet}"
    return reply
