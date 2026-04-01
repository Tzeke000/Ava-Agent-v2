
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

def build_selfstate_reply(health: dict | None, mood: dict | None, tendency: str | None = None) -> str:
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
    return (
        f"{prefix} Operationally, {detail}. "
        f"Mood-wise I'm leaning {mood_text}, and behavior-wise I'm a bit more {tendency} at the moment."
    )

def startup_health_banner(health: dict | None) -> str:
    state, detail = summarize_health(health)
    return f"[startup-selftest] {state.upper()} :: {detail} :: {datetime.now().isoformat(timespec='seconds')}"
